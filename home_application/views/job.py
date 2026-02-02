import json
import time

from blueapps.utils import ok_data
from celery import chain
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from blueking.component.shortcuts import get_client_by_request
from core.middleware import logger
from home_application.constants import (
    ALLOW_FILE_SUFFIX,
    ALLOW_PATH_PREFIX,
    BACKUP_FILE_PLAN_ID,
    BK_JOB_HOST,
    CALLBACK_URL,
    FAILED_CODE,
    JOB_BK_BIZ_ID,
    JOB_RESULT_ATTEMPTS_INTERVAL,
    MAX_ATTEMPTS,
    SEARCH_FILE_PLAN_ID,
    SUCCESS_CODE,
    WAITING_CODE,
)
from home_application.exceptions.job import (
    JobExecutionError,
    JobParameterError,
    JobStatusError,
    JobTimeoutError,
)
from home_application.models import BackupJob
from home_application.services.job import batch_get_job_logs
from home_application.tasks.job import (
    fetch_job_logs,
    poll_job_status,
    process_backup_results,
)


class SearchFileAPIView(APIView):
    """搜索文件API"""

    def get(self, request):
        """根据主机IP、文件目录和文件后缀查询文件"""
        host_id_list_str = request.query_params.get("host_id_list")
        host_id_list = [int(bk_host_id) for bk_host_id in host_id_list_str.split(",")]
        search_path = request.query_params.get("search_path")
        suffix = request.query_params.get("suffix")

        # 校验参数
        if suffix not in ALLOW_FILE_SUFFIX:
            raise JobParameterError("文件后缀不合法")
        if not search_path.startswith(tuple(ALLOW_PATH_PREFIX)) or ".." in search_path:
            raise JobParameterError("搜索路径不合法")

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
                    "value": search_path,
                },
                {
                    "name": "suffix",
                    "value": suffix,
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
            status = step_instance_list[0].get("status")
            if status == WAITING_CODE:
                time.sleep(JOB_RESULT_ATTEMPTS_INTERVAL)
            elif status == SUCCESS_CODE or status == FAILED_CODE:
                break
            else:  # 既不是 WAITING 也不是 SUCCESS，就是失败
                raise JobStatusError("查询失败")
            attempts += 1

        if attempts == MAX_ATTEMPTS:
            raise JobTimeoutError("查询超时")

        step_instance_id = step_instance_list[0].get("step_instance_id")

        # 获取执行日志
        # 使用公共函数批量获取日志，替代原有的循环单机查询，提高效率并复用逻辑
        results = batch_get_job_logs(
            client=client,
            job_instance_id=job_instance_id,
            step_instance_id=step_instance_id,
            host_id_list=host_id_list,
            bk_biz_id=JOB_BK_BIZ_ID,
        )

        log_list = []
        for res in results:
            bk_host_id = res["bk_host_id"]
            if res["is_success"]:
                parsed_data = res["parsed_data"]
            else:
                if res["log_content"] is None:
                    res["log_content"] = "日志内容为空"
                parsed_data = {"message": res["log_content"]}
            parsed_data["bk_host_id"] = bk_host_id
            log_list.append(parsed_data)

        return Response(ok_data(data=log_list))


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

        # 校验参数
        if suffix not in ALLOW_FILE_SUFFIX:
            raise JobParameterError("文件后缀不合法")
        if not search_path.startswith(tuple(ALLOW_PATH_PREFIX)) or ".." in search_path:
            raise JobParameterError("搜索路径不合法")
        if not backup_path.startswith(tuple(ALLOW_PATH_PREFIX)) or ".." in backup_path:
            raise JobParameterError("备份路径不合法")

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
                {"name": "search_path", "value": search_path},
                {"name": "suffix", "value": suffix},
                {
                    "name": "backup_path",
                    "value": backup_path,
                },
            ],
            "callback_url": CALLBACK_URL,
        }

        try:
            client = get_client_by_request(request)
            job_response = client.jobv3.execute_job_plan(**kwargs)
            job_instance_id = job_response.get("data", {}).get("job_instance_id")

            if not job_instance_id:
                raise JobExecutionError("执行作业失败，未返回job_instance_id")
        except Exception as e:
            logger.error(f"执行作业异常: {str(e)}")
            if isinstance(e, (JobExecutionError, JobParameterError)):
                raise e
            raise JobExecutionError(f"执行作业失败: {str(e)}")

        # 生成作业链接
        bk_job_link = "{}/biz/{}/execute/task/{}".format(
            BK_JOB_HOST,
            JOB_BK_BIZ_ID,
            job_instance_id,
        )

        # 创建备份作业记录（状态为pending）
        BackupJob.objects.create(
            job_instance_id=str(job_instance_id),
            operator=request.user.username,
            search_path=search_path,
            suffix=suffix,
            backup_path=backup_path,
            bk_job_link=bk_job_link,
            status=BackupJob.Status.PENDING,
            host_count=len(host_id_list),
            file_count=0,
        )

        # 从 request 中提取 bk_token
        bk_token = request.COOKIES.get("bk_token", "")

        # 启动异步任务处理作业（传递 bk_token 而非 bk_username）
        # 使用 Celery Chain 编排任务：轮询状态 -> 获取日志 -> 处理结果
        chain(
            poll_job_status.s(job_instance_id=str(job_instance_id), bk_biz_id=JOB_BK_BIZ_ID, bk_token=bk_token),
            fetch_job_logs.s(host_id_list=host_id_list, bk_token=bk_token),
            process_backup_results.s(),
        ).apply_async()

        # 立即返回，不阻塞等待作业完成
        return Response(ok_data(data="备份作业已提交，正在后台处理"))


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
                return Response({"error": "invalid callback payload"}, status=status.HTTP_400_BAD_REQUEST)

        job_instance_id = data.get("job_instance_id")
        status_code = data.get("status")
        step_instances = data.get("step_instances", [])
        step_status = step_instances[0].get("status")

        if not job_instance_id or not status_code:
            logger.warning(f"回调缺少必要参数: job_instance_id={job_instance_id}, status={status_code}")
            return Response({"error": "missing required parameters"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            backup_job = BackupJob.objects.get(job_instance_id=str(job_instance_id))

            # 只更新未完成的作业
            if backup_job.status in [BackupJob.Status.PENDING, BackupJob.Status.PROCESSING]:
                if int(status_code) == SUCCESS_CODE and step_status == SUCCESS_CODE:
                    backup_job.mark_success()
                    new_status = BackupJob.Status.SUCCESS
                else:
                    backup_job.mark_failed()
                    new_status = BackupJob.Status.FAILED

                logger.info(f"回调更新作业状态: job_instance_id={job_instance_id}, " f"new_status={new_status}")
            else:
                logger.info(
                    f"作业状态已处理，跳过回调更新: job_instance_id={job_instance_id}, "
                    f"current_status={backup_job.status}"
                )

            return Response({"result": True, "message": "callback received"})

        except BackupJob.DoesNotExist:
            logger.error(f"备份作业不存在: job_instance_id={job_instance_id}")
            return Response({"error": "backup job not found"}, status=status.HTTP_404_NOT_FOUND)
