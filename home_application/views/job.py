import json
import time

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from blueking.component.shortcuts import get_client_by_request
from core.middleware import logger
from home_application.constants import WEB_SUCCESS_CODE, JOB_BK_BIZ_ID, SEARCH_FILE_PLAN_ID, MAX_ATTEMPTS, WAITING_CODE, \
    JOB_RESULT_ATTEMPTS_INTERVAL, SUCCESS_CODE, BACKUP_FILE_PLAN_ID, BK_JOB_HOST, CALLBACK_URL
from home_application.models import BackupJob

class SearchFileAPIView(APIView):
    """搜索文件API"""
    def get(self, request):
        """根据主机IP、文件目录和文件后缀查询文件"""
        host_id_list_str = request.query_params.get("host_id_list")
        host_id_list = [int(bk_host_id) for bk_host_id in host_id_list_str.split(",")]

        kwargs = {
            "bk_scope_type": "biz",
            "bk_scope_id": JOB_BK_BIZ_ID,
            "job_plan_id": SEARCH_FILE_PLAN_ID,
            "global_var_list": [
                {
                    "name": "host_list",
                    "server": {
                        "host_id_list": host_id_list,
                    },
                },
                {
                    "name": "search_path",
                    "value": request.query_params.get("search_path"),
                },
                {
                    "name": "suffix",
                    "value": request.query_params.get("suffix"),
                },
            ],
        }

        client = get_client_by_request(request)
        job_instance_id = client.jobv3.execute_job_plan(**kwargs).get("data").get("job_instance_id")

        kwargs = {
            "bk_scope_type": "biz",
            "bk_scope_id": JOB_BK_BIZ_ID,
            "job_instance_id": job_instance_id,
        }

        # 轮询执行状态
        attempts = 0
        while attempts < MAX_ATTEMPTS:
            step_instance_list = client.jobv3.get_job_instance_status(**kwargs).get("data").get("step_instance_list")
            if step_instance_list[0].get("status") == WAITING_CODE:
                time.sleep(JOB_RESULT_ATTEMPTS_INTERVAL)
            elif step_instance_list[0].get("status") != SUCCESS_CODE:
                return Response({
                    "result": False,
                    "code": WEB_SUCCESS_CODE,
                    "message": "search failed",
                })
            elif step_instance_list[0].get("status") == SUCCESS_CODE:
                break
            attempts += 1

        if attempts == MAX_ATTEMPTS:
            return Response({
                "result": False,
                "code": WEB_SUCCESS_CODE,
                "message": "查询超时",
            })

        step_instance_id = step_instance_list[0].get("step_instance_id")

        # 获取执行日志
        log_list = []
        for bk_host_id in host_id_list:
            data = {
                "bk_scope_type": "biz",
                "bk_scope_id": JOB_BK_BIZ_ID,
                "job_instance_id": job_instance_id,
                "step_instance_id": step_instance_id,
                "bk_host_id": bk_host_id,
            }

            response = client.jobv3.get_job_instance_ip_log(**data).get("data")
            step_res = response.get("log_content")
            json_step_res = json.loads(step_res)
            json_step_res["bk_host_id"] = response.get("bk_host_id")
            log_list.append(json_step_res)

        return Response({
            "result": True,
            "code": WEB_SUCCESS_CODE,
            "data": log_list,
        })


class BackupFileAPIView(APIView):
    """
    备份文件API

    POST参数：
        host_id_list (str, 必填): 主机ID列表，逗号分隔
        search_path (str, 必填): 搜索路径
        suffix (str, 必填): 文件后缀
        backup_path (str, 必填): 备份路径

    返回：
        job_instance_id: 作业实例ID，可用于查询作业状态
    """

    def post(self, request):
        """备份文件到指定目录（异步处理）"""
        host_id_list_str = request.data.get("host_id_list")
        host_id_list = [int(bk_host_id) for bk_host_id in host_id_list_str.split(",")]
        search_path = request.data.get("search_path")
        suffix = request.data.get("suffix")
        backup_path = request.data.get("backup_path")

        # 执行作业计划
        kwargs = {
            "bk_scope_type": "biz",
            "bk_scope_id": JOB_BK_BIZ_ID,
            "job_plan_id": BACKUP_FILE_PLAN_ID,
            "global_var_list": [
                {
                    "name": "host_list",
                    "server": {
                        "host_id_list": host_id_list,
                    },
                },
                {
                    "name": "search_path",
                    "value": search_path
                },
                {
                    "name": "suffix",
                    "value": suffix
                },
                {
                    "name": "backup_path",
                    "value": backup_path,
                },
            ],
            "callback_url": CALLBACK_URL
        }

        try:
            client = get_client_by_request(request)
            job_response = client.jobv3.execute_job_plan(**kwargs)
            job_instance_id = job_response.get("data", {}).get("job_instance_id")

            if not job_instance_id:
                return Response({
                    "result": False,
                    "code": WEB_SUCCESS_CODE,
                    "message": "执行作业失败，未返回job_instance_id",
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            logger.error(f"执行作业异常: {str(e)}")
            return Response({
                "result": False,
                "code": WEB_SUCCESS_CODE,
                "message": f"执行作业失败: {str(e)}",
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 生成作业链接
        bk_job_link = "{}/biz/{}/execute/task/{}".format(
            BK_JOB_HOST,
            JOB_BK_BIZ_ID,
            job_instance_id,
        )

        # 创建备份作业记录（状态为pending）
        backup_job = BackupJob.objects.create(
            job_instance_id=str(job_instance_id),
            operator=request.user.username,
            search_path=search_path,
            suffix=suffix,
            backup_path=backup_path,
            bk_job_link=bk_job_link,
            status="pending",
            host_count=len(host_id_list),
            file_count=0,
        )

        # 从 request 中提取 bk_token
        bk_token = request.COOKIES.get("bk_token", "")

        # 启动异步任务处理作业（传递 bk_token 而非 bk_username）
        from home_application.tasks import process_backup_job_task
        process_backup_job_task.delay(
            job_instance_id=str(job_instance_id),
            bk_token=bk_token,  # 使用 bk_token
            operator=request.user.username,  # 只用于记录操作者
            host_id_list=host_id_list,
        )

        # 立即返回，不阻塞等待作业完成
        return Response({
            "result": True,
            "data": "备份作业已提交，正在后台处理",
            "code": WEB_SUCCESS_CODE,
        })

class BackupJobCallbackAPIView(APIView):
    """
    备份作业回调API

    JOB平台会在作业完成时调用此接口，更新作业状态
    """

    def post(self, request):
        """处理JOB平台的回调通知"""
        data = request.data

        # 兼容"JSON 被当成 key"的情况
        if isinstance(data, dict) and len(data) == 1:
            key = next(iter(data.keys()))
            try:
                data = json.loads(key)
            except json.JSONDecodeError:
                logger.warning(f"无效的回调数据格式: {key}")
                return Response(
                    {"error": "invalid callback payload"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        job_instance_id = data.get("job_instance_id")
        status_code = data.get("status")
        step_instances = data.get("step_instances", [])
        step_status = step_instances[0].get("status")


        if not job_instance_id or not status_code:
            logger.warning(f"回调缺少必要参数: job_instance_id={job_instance_id}, status={status_code}")
            return Response(
                {"error": "missing required parameters"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            backup_job = BackupJob.objects.get(job_instance_id=str(job_instance_id))

            # 只更新未完成的作业
            if backup_job.status == "pending" or backup_job.status == "processing":
                new_status = "success" if (int(status_code) == SUCCESS_CODE and step_status == SUCCESS_CODE) else "failed"
                backup_job.status = new_status
                backup_job.save()

                logger.info(
                    f"回调更新作业状态: job_instance_id={job_instance_id}, "
                    f"new_status={new_status}"
                )
            else:
                logger.info(
                    f"作业状态已处理，跳过回调更新: job_instance_id={job_instance_id}, "
                    f"current_status={backup_job.status}"
                )

            return Response({"result": True, "message": "callback received"})

        except BackupJob.DoesNotExist:
            logger.error(f"备份作业不存在: job_instance_id={job_instance_id}")
            return Response(
                {"error": "backup job not found"},
                status=status.HTTP_404_NOT_FOUND
            )