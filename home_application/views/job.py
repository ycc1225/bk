import json

from blueapps.utils import ok_data
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from blueking.component.shortcuts import get_client_by_request
from core.middleware import logger
from home_application.constants import (
    BACKUP_FILE_PLAN_ID,
    CALLBACK_URL,
    JOB_BK_BIZ_ID,
    SEARCH_FILE_PLAN_ID,
    SUCCESS_CODE,
)
from home_application.exceptions.job import JobParameterError
from home_application.models import BackupJob
from home_application.permission import IsDevOrAbove, IsOpsOrAbove
from home_application.serializers.job import (
    BackupJobSubmitSerializer,
    SearchFileSubmitSerializer,
)
from home_application.services.job import BackupJobService, JobExecutionService


class SearchFileAPIView(APIView):
    """搜索文件API"""

    permission_classes = [IsDevOrAbove]

    def get(self, request):
        """根据主机IP、文件目录和文件后缀查询文件"""
        # 提取查询参数
        host_id_list_str = request.query_params.get("host_id_list", "")
        search_path = request.query_params.get("search_path", "")
        suffix = request.query_params.get("suffix", "")

        # 构建数据用于序列化器验证
        try:
            host_list = [int(bk_host_id.strip()) for bk_host_id in host_id_list_str.split(",") if bk_host_id.strip()]
        except ValueError:
            raise JobParameterError("主机ID必须是整数")

        data = {"host_list": host_list, "search_path": search_path, "suffix": suffix}

        # 使用序列化器进行参数校验
        serializer = SearchFileSubmitSerializer(data=data)
        if not serializer.is_valid():
            raise JobParameterError(f"参数校验失败: {serializer.errors}")

        validated_data = serializer.validated_data

        # 使用 Service 层执行业务逻辑
        client = get_client_by_request(request)
        job_service = JobExecutionService(client=client, bk_biz_id=JOB_BK_BIZ_ID)

        log_list = job_service.execute_search_file(
            host_id_list=validated_data["host_list"],
            search_path=validated_data["search_path"],
            suffix=validated_data["suffix"],
            plan_id=SEARCH_FILE_PLAN_ID,
        )

        return Response(ok_data(data=log_list))


class BackupFileAPIView(APIView):
    """
    备份文件API

    POST参数：
        host_list (list, 必填): 主机ID列表
        search_path (str, 必填): 搜索路径
        suffix (str, 必填): 文件后缀
        backup_path (str, 必填): 备份路径

    返回：
        job_instance_id: 作业实例ID，可用于查询作业状态
    """

    permission_classes = [IsOpsOrAbove]

    def post(self, request):
        """备份文件到指定目录（异步处理）"""
        # 使用序列化器进行参数校验
        serializer = BackupJobSubmitSerializer(data=request.data)
        if not serializer.is_valid():
            raise JobParameterError(f"参数校验失败: {serializer.errors}")

        validated_data = serializer.validated_data

        # 使用 Service 层执行 Job 作业
        client = get_client_by_request(request)
        job_service = JobExecutionService(client=client, bk_biz_id=JOB_BK_BIZ_ID)

        job_instance_id, bk_job_link = job_service.execute_backup_file(
            host_id_list=validated_data["host_list"],
            search_path=validated_data["search_path"],
            suffix=validated_data["suffix"],
            backup_path=validated_data["backup_path"],
            plan_id=BACKUP_FILE_PLAN_ID,
            callback_url=CALLBACK_URL,
        )

        # 使用 Service 层创建备份作业记录
        backup_job = BackupJobService.create_backup_job(
            job_instance_id=job_instance_id,
            operator=request.user.username,
            search_path=validated_data["search_path"],
            suffix=validated_data["suffix"],
            backup_path=validated_data["backup_path"],
            bk_job_link=bk_job_link,
            host_count=len(validated_data["host_list"]),
        )

        # 从 request 中提取 bk_token
        bk_token = request.COOKIES.get("bk_token", "")

        # 使用 Service 层启动异步任务链
        BackupJobService.start_async_processing(
            job_instance_id=job_instance_id,
            host_id_list=validated_data["host_list"],
            bk_biz_id=JOB_BK_BIZ_ID,
            bk_token=bk_token,
        )

        # 立即返回作业ID，前端可通过 backup-job-detail/{id}/ 轮询状态
        return Response(ok_data(data={"id": backup_job.id, "job_instance_id": job_instance_id}))


class BackupJobCallbackAPIView(APIView):
    """
    备份作业回调API

    JOB平台会在作业完成时调用此接口，更新作业状态
    """

    permission_classes = [AllowAny]
    authentication_classes = []  # 回调接口豁免认证

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
        step_status = step_instances[0].get("status") if step_instances else None

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
