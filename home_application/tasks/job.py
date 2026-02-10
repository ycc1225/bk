import logging

from celery import shared_task
from django.db import transaction

from blueking.component import client as component_client
from config import APP_CODE, SECRET_KEY
from home_application.constants import (
    JOB_RESULT_ATTEMPTS_INTERVAL,
    JOB_RETRY_BACKOFF_MAX,
    MAX_ATTEMPTS,
    SUCCESS_CODE,
    WAITING_CODE,
)
from home_application.exceptions.job import TaskErrorType
from home_application.models import BackupJob, BackupRecord
from home_application.utils.job_utils import batch_get_job_logs
from home_application.utils.tracing import (
    add_trace_attrs,
    add_trace_event,
    mark_trace_error,
)
from home_application.views.metrics import celery_tasks_total, job_execution_status

logger = logging.getLogger(__name__)


def get_esb_client(bk_token):
    return component_client.ComponentClient(APP_CODE, SECRET_KEY, common_args={"bk_token": bk_token})


@shared_task(
    bind=True,
    max_retries=MAX_ATTEMPTS,
)
def poll_job_status(self, job_instance_id, bk_biz_id, bk_token):
    """轮询作业执行状态，返回作业元数据"""
    add_trace_attrs(
        job_instance_id=job_instance_id,
        job_bk_biz_id=bk_biz_id,
    )

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
            logger.warning(
                "[轮询状态] 作业状态返回空", extra={"job_instance_id": job_instance_id, "bk_biz_id": bk_biz_id}
            )
            raise Exception("Empty step_instance_list")

        step_status = step_instance_list[0].get("status")
        step_instance_id = step_instance_list[0].get("step_instance_id")

        add_trace_attrs(
            job_step_status=step_status,
            job_step_instance_id=step_instance_id,
        )

        if step_status == WAITING_CODE:
            add_trace_event("job_still_running", retry_count=self.request.retries)
            # 手动实现指数退避: countdown = min(base * 2^retries, max)
            countdown = min(JOB_RESULT_ATTEMPTS_INTERVAL * (2**self.request.retries), JOB_RETRY_BACKOFF_MAX)
            raise self.retry(
                exc=Exception(f"Job {job_instance_id} is still running"),
                countdown=countdown,
            )

        is_success = step_status == SUCCESS_CODE
        add_trace_attrs(job_is_success=is_success)

        # 指标埋点：轮询完成
        celery_tasks_total.labels(task_name="poll_job_status", status="success").inc()

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
        if isinstance(e, self.Retry):
            raise e

        mark_trace_error(e)

        # 手动实现指数退避: countdown = min(base * 2^retries, max)
        countdown = min(JOB_RESULT_ATTEMPTS_INTERVAL * (2**self.request.retries), JOB_RETRY_BACKOFF_MAX)

        logger.warning(
            "[轮询状态] 查询失败，准备重试",
            extra={
                "job_instance_id": job_instance_id,
                "bk_biz_id": bk_biz_id,
                "error": str(e),
                "retry_count": self.request.retries,
                "max_retries": self.max_retries,
                "countdown": countdown,
            },
        )
        # 指标埋点：轮询重试（仅在最终重试耗尽时记录失败）
        if self.request.retries >= self.max_retries:
            celery_tasks_total.labels(task_name="poll_job_status", status="failure").inc()
        raise self.retry(exc=e, countdown=countdown)


@shared_task
def fetch_job_logs(job_status_result, host_id_list, bk_token):
    """批量获取所有主机的执行日志"""
    job_instance_id = job_status_result.get("job_instance_id")

    add_trace_attrs(
        job_instance_id=job_instance_id,
        job_host_count=len(host_id_list),
    )

    if not job_status_result.get("success"):
        add_trace_attrs(job_upstream_failed=True)
        logger.warning(
            "[获取日志] 上游任务失败，跳过日志获取",
            extra={
                "job_instance_id": job_instance_id,
                "error": job_status_result.get("error"),
            },
        )
        return {
            "success": False,
            "error": job_status_result.get("error", "上游任务失败"),
            "error_type": TaskErrorType.UPSTREAM_ERROR,
            "job_instance_id": job_instance_id,
            "results": [],
        }

    step_instance_id = job_status_result.get("step_instance_id")
    bk_biz_id = job_status_result.get("bk_biz_id")
    is_success = job_status_result.get("is_success")

    add_trace_attrs(
        job_step_instance_id=step_instance_id,
        job_is_success=is_success,
    )

    if not is_success:
        add_trace_event("job_execution_failed")
        return {
            "success": True,
            "is_job_success": False,
            "job_instance_id": job_instance_id,
            "results": [],
        }

    try:
        client = get_esb_client(bk_token)

        results = batch_get_job_logs(
            client=client,
            job_instance_id=job_instance_id,
            step_instance_id=step_instance_id,
            host_id_list=host_id_list,
            bk_biz_id=bk_biz_id,
        )

        add_trace_attrs(job_results_count=len(results))

        # 指标埋点：日志获取成功
        celery_tasks_total.labels(task_name="fetch_job_logs", status="success").inc()

        return {
            "success": True,
            "is_job_success": True,
            "job_instance_id": job_instance_id,
            "results": results,
        }

    except Exception as e:
        # 指标埋点：日志获取失败
        celery_tasks_total.labels(task_name="fetch_job_logs", status="failure").inc()
        mark_trace_error(e)
        logger.error(
            "[获取日志] 获取作业日志失败",
            extra={
                "job_instance_id": job_instance_id,
                "step_instance_id": step_instance_id,
                "bk_biz_id": bk_biz_id,
                "error": str(e),
            },
        )
        return {
            "success": False,
            "error": f"获取作业日志失败: {str(e)}",
            "error_type": TaskErrorType.FETCH_LOGS_ERROR,
            "job_instance_id": job_instance_id,
            "results": [],
        }


@shared_task
def process_backup_results(fetch_logs_result):
    """处理备份作业结果，保存所有记录"""
    job_instance_id = fetch_logs_result.get("job_instance_id")

    add_trace_attrs(job_instance_id=job_instance_id)

    logger.info(
        "[处理结果] 开始处理备份作业结果",
        extra={"job_instance_id": job_instance_id},
    )

    try:
        backup_job = BackupJob.objects.get(job_instance_id=job_instance_id)
    except BackupJob.DoesNotExist:
        logger.error(
            "[处理结果] BackupJob不存在",
            extra={"job_instance_id": job_instance_id},
        )
        mark_trace_error(Exception("BackupJob不存在"))
        return {"success": False, "error": "BackupJob不存在"}

    if not fetch_logs_result.get("success"):
        error_type = fetch_logs_result.get("error_type")
        error_msg = fetch_logs_result.get("error")

        add_trace_attrs(
            job_error_type=str(error_type),
            job_error_msg=error_msg,
        )

        logger.error(
            "[处理结果] 任务链执行失败",
            extra={
                "job_instance_id": job_instance_id,
                "error_type": str(error_type),
                "error": error_msg,
            },
        )

        if error_type == TaskErrorType.POLL_STATUS_ERROR:
            backup_job.status = BackupJob.Status.FAILED
            backup_job.error_message = f"查询作业状态失败: {error_msg}"
            backup_job.save()
            logger.warning(
                "[处理结果] 作业状态查询失败，已标记为失败",
                extra={"job_instance_id": job_instance_id, "error": error_msg},
            )

        elif error_type == TaskErrorType.FETCH_LOGS_ERROR:
            backup_job.status = BackupJob.Status.FAILED
            backup_job.error_message = f"获取执行日志失败: {error_msg}"
            backup_job.save()
            logger.warning(
                "[处理结果] 日志获取失败，已标记为失败",
                extra={"job_instance_id": job_instance_id, "error": error_msg},
            )

        elif error_type == TaskErrorType.UPSTREAM_ERROR:
            backup_job.status = BackupJob.Status.FAILED
            backup_job.error_message = f"上游任务失败: {error_msg}"
            backup_job.save()

        else:
            backup_job.mark_failed()
            logger.error(
                "[处理结果] 未知错误类型",
                extra={"job_instance_id": job_instance_id, "error_type": str(error_type)},
            )

        mark_trace_error(Exception(error_msg))
        # 指标埋点：任务失败
        celery_tasks_total.labels(task_name="process_backup_results", status="failure").inc()
        job_execution_status.labels(job_name=f"backup_{job_instance_id}").set(0)
        return {"success": False, "error_type": error_type, "error": error_msg}

    is_job_success = fetch_logs_result.get("is_job_success")
    results = fetch_logs_result.get("results", [])

    add_trace_attrs(
        job_is_job_success=is_job_success,
        job_results_count=len(results),
    )

    if not is_job_success:
        backup_job.mark_failed()
        logger.info(
            "[处理结果] 作业执行失败",
            extra={"job_instance_id": job_instance_id},
        )
        add_trace_event("job_marked_failed")
        # 指标埋点：JOB 执行失败
        celery_tasks_total.labels(task_name="process_backup_results", status="failure").inc()
        job_execution_status.labels(job_name=f"backup_{job_instance_id}").set(0)
        return {"success": True, "job_status": "failed"}

    records_to_create = []
    success_hosts = 0
    failed_hosts = 0

    for res in results:
        bk_host_id = res.get("bk_host_id")
        parsed_data = res.get("parsed_data")
        is_host_success = res.get("is_success", False)

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

        if isinstance(parsed_data, dict):
            json_step_res = [parsed_data]
        else:
            json_step_res = parsed_data

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

    with transaction.atomic():
        if records_to_create:
            BackupRecord.objects.bulk_create(records_to_create, batch_size=1000)

        total_files = len(records_to_create)

        if failed_hosts == 0 and success_hosts > 0:
            backup_job.mark_success(file_count=total_files)
        elif success_hosts == 0:
            backup_job.mark_failed()
        else:
            backup_job.mark_partial(file_count=total_files)

    add_trace_attrs(
        job_success_hosts=success_hosts,
        job_failed_hosts=failed_hosts,
        job_total_files=total_files,
    )

    add_trace_event("job_processing_completed", final_status=backup_job.status)

    logger.info(
        "[处理结果] 作业处理完成",
        extra={
            "job_instance_id": job_instance_id,
            "success_hosts": success_hosts,
            "failed_hosts": failed_hosts,
            "total_files": total_files,
            "final_status": backup_job.status,
        },
    )

    # 指标埋点：任务完成
    celery_tasks_total.labels(task_name="process_backup_results", status="success").inc()
    job_execution_status.labels(job_name=f"backup_{job_instance_id}").set(1 if failed_hosts == 0 else 0)

    return {
        "success": True,
        "job_status": "completed",
        "success_hosts": success_hosts,
        "failed_hosts": failed_hosts,
        "total_files": total_files,
    }
