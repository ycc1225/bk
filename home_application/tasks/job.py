import logging

from celery import shared_task
from django.db import transaction

from blueking.component import client as component_client
from config import APP_CODE, SECRET_KEY
from home_application.constants import (
    JOB_RESULT_ATTEMPTS_INTERVAL,
    MAX_ATTEMPTS,
    SUCCESS_CODE,
    WAITING_CODE,
)
from home_application.exceptions.job import TaskErrorType
from home_application.models import BackupJob, BackupRecord
from home_application.utils.job_utils import batch_get_job_logs

logger = logging.getLogger(__name__)


def get_esb_client(bk_token):
    """
    获取 ESB Client
    """
    return component_client.ComponentClient(APP_CODE, SECRET_KEY, common_args={"bk_token": bk_token})


@shared_task(
    bind=True,
    max_retries=MAX_ATTEMPTS,
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def poll_job_status(self, job_instance_id, bk_biz_id, bk_token):
    """
    通用任务：轮询作业执行状态
    返回作业的基本元数据，不涉及具体业务处理

    返回格式：
    - 成功: {"success": True, "is_finished": True, "is_success": bool, ...}
    - 失败: {"success": False, "error": str, "error_type": TaskErrorType, "job_instance_id": str}
    """
    client = get_esb_client(bk_token)

    kwargs = {
        "bk_scope_type": "biz",
        "bk_scope_id": bk_biz_id,
        "job_instance_id": job_instance_id,
    }

    try:
        response = client.jobv3.get_job_instance_status(**kwargs)
        step_instance_list = response.get("data", {}).get("step_instance_list", [])

        if not step_instance_list:
            logger.warning(f"作业状态返回空: job_instance_id={job_instance_id}")
            raise Exception("Empty step_instance_list")

        step_status = step_instance_list[0].get("status")
        step_instance_id = step_instance_list[0].get("step_instance_id")

        if step_status == WAITING_CODE:
            # 作业正在运行中，进行重试
            raise self.retry(
                exc=Exception(f"Job {job_instance_id} is still running"),
                countdown=JOB_RESULT_ATTEMPTS_INTERVAL,
                max_retries=MAX_ATTEMPTS,
            )

        is_success = step_status == SUCCESS_CODE

        return {
            "success": True,
            "is_finished": True,
            "is_success": is_success,
            "job_instance_id": job_instance_id,
            "step_instance_id": step_instance_id,
            "bk_biz_id": bk_biz_id,
            "status": step_status,
        }

    except Exception as e:
        # 如果是重试异常，继续抛出
        if isinstance(e, self.Retry):
            raise e

        # 达到最大重试次数或其他异常，返回错误状态而不是抛出异常
        logger.error(f"查询作业状态失败: job_instance_id={job_instance_id}, error={str(e)}")
        return {
            "success": False,
            "error": f"查询作业状态失败: {str(e)}",
            "error_type": TaskErrorType.POLL_STATUS_ERROR,
            "job_instance_id": job_instance_id,
        }


@shared_task
def fetch_job_logs(job_status_result, host_id_list, bk_token):
    """
    通用任务：批量获取所有主机的执行日志

    返回格式：
    - 成功: {"success": True, "is_job_success": bool, "job_instance_id": str, "results": list}
    - 失败: {"success": False, "error": str, "error_type": TaskErrorType, "job_instance_id": str}
    """
    # 检查上游任务是否成功
    if not job_status_result.get("success"):
        logger.warning(f"上游任务失败，跳过日志获取: {job_status_result.get('error')}")
        return {
            "success": False,
            "error": job_status_result.get("error", "上游任务失败"),
            "error_type": TaskErrorType.UPSTREAM_ERROR,
            "job_instance_id": job_status_result.get("job_instance_id"),
            "results": [],
        }

    job_instance_id = job_status_result.get("job_instance_id")
    step_instance_id = job_status_result.get("step_instance_id")
    bk_biz_id = job_status_result.get("bk_biz_id")
    is_success = job_status_result.get("is_success")

    # 如果作业本身失败，传递失败状态但不算错误
    if not is_success:
        return {
            "success": True,
            "is_job_success": False,
            "job_instance_id": job_instance_id,
            "results": [],
        }

    try:
        client = get_esb_client(bk_token)

        # 调用公共函数
        results = batch_get_job_logs(
            client=client,
            job_instance_id=job_instance_id,
            step_instance_id=step_instance_id,
            host_id_list=host_id_list,
            bk_biz_id=bk_biz_id,
        )

        return {
            "success": True,
            "is_job_success": True,
            "job_instance_id": job_instance_id,
            "results": results,
        }

    except Exception as e:
        logger.error(f"获取作业日志失败: job_instance_id={job_instance_id}, error={str(e)}")
        return {
            "success": False,
            "error": f"获取作业日志失败: {str(e)}",
            "error_type": TaskErrorType.FETCH_LOGS_ERROR,
            "job_instance_id": job_instance_id,
            "results": [],
        }


@shared_task
def process_backup_results(fetch_logs_result):
    """
    业务任务：处理备份作业结果
    保存所有记录（成功/失败）用于排查，使用 bulk_create 优化性能

    根据不同的错误类型执行不同的处理逻辑
    """
    job_instance_id = fetch_logs_result.get("job_instance_id")

    logger.info(f"开始处理备份作业结果: job_instance_id={job_instance_id}")

    try:
        backup_job = BackupJob.objects.get(job_instance_id=job_instance_id)
    except BackupJob.DoesNotExist:
        logger.error(f"BackupJob不存在: {job_instance_id}")
        return {"success": False, "error": "BackupJob不存在"}

    # 处理上游任务失败的情况
    if not fetch_logs_result.get("success"):
        error_type = fetch_logs_result.get("error_type")
        error_msg = fetch_logs_result.get("error")

        logger.error(f"任务链执行失败: job_instance_id={job_instance_id}, error_type={error_type}, error={error_msg}")

        # 根据不同的错误类型执行不同的处理逻辑
        if error_type == TaskErrorType.POLL_STATUS_ERROR:
            # 轮询状态失败：可能是网络问题或Job平台异常
            backup_job.status = BackupJob.Status.FAILED
            backup_job.error_message = f"查询作业状态失败: {error_msg}"
            backup_job.save()
            logger.warning(f"作业状态查询失败，已标记为失败: {job_instance_id}")

        elif error_type == TaskErrorType.FETCH_LOGS_ERROR:
            # 获取日志失败：作业可能已完成，但无法获取结果
            backup_job.status = BackupJob.Status.FAILED
            backup_job.error_message = f"获取执行日志失败: {error_msg}"
            backup_job.save()
            logger.warning(f"日志获取失败，已标记为失败: {job_instance_id}")

        elif error_type == TaskErrorType.UPSTREAM_ERROR:
            # 上游任务失败
            backup_job.status = BackupJob.Status.FAILED
            backup_job.error_message = f"上游任务失败: {error_msg}"
            backup_job.save()

        else:
            # 未知错误类型
            backup_job.mark_failed()
            logger.error(f"未知错误类型: {error_type}")

        return {"success": False, "error_type": error_type, "error": error_msg}

    # 正常处理逻辑
    is_job_success = fetch_logs_result.get("is_job_success")
    results = fetch_logs_result.get("results", [])

    # 作业整体失败，直接标记退出
    if not is_job_success:
        backup_job.mark_failed()
        logger.info(f"作业执行失败: {job_instance_id}")
        return {"success": True, "job_status": "failed"}

    records_to_create = []
    success_hosts = 0
    failed_hosts = 0

    for res in results:
        bk_host_id = res.get("bk_host_id")
        parsed_data = res.get("parsed_data")
        is_host_success = res.get("is_success", False)

        # 主机执行失败或无解析数据
        if not is_host_success or not parsed_data:
            records_to_create.append(
                BackupRecord(
                    backup_job=backup_job,
                    bk_host_id=bk_host_id,
                    status="failed",
                    bk_backup_name="文件备份失败",
                )
            )
            failed_hosts += 1
            continue

        # 直接使用已解析的数据
        if isinstance(parsed_data, dict):
            json_step_res = [parsed_data]
        else:
            json_step_res = parsed_data

        # 每个文件创建一条记录
        for step_res in json_step_res:
            records_to_create.append(
                BackupRecord(
                    backup_job=backup_job,
                    bk_host_id=bk_host_id,
                    status="success",
                    bk_backup_name=step_res.get("bk_backup_name", "unknown"),
                )
            )

        success_hosts += 1

    # 批量创建记录并更新作业状态
    with transaction.atomic():
        if records_to_create:
            BackupRecord.objects.bulk_create(records_to_create, batch_size=1000)

        total_files = len(records_to_create)

        # 更新作业最终状态
        if failed_hosts == 0 and success_hosts > 0:
            backup_job.mark_success(file_count=total_files)
        elif success_hosts == 0:
            backup_job.mark_failed()
        else:
            backup_job.mark_partial(file_count=total_files)

    logger.info(
        f"作业处理完成: job={job_instance_id}, success={success_hosts}, failed={failed_hosts}, files={total_files}"
    )

    return {
        "success": True,
        "job_status": "completed",
        "success_hosts": success_hosts,
        "failed_hosts": failed_hosts,
        "total_files": total_files,
    }
