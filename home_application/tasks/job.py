import logging

from celery import shared_task
from django.db import transaction
from opentelemetry import trace

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

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


def get_esb_client(bk_token):
    return component_client.ComponentClient(APP_CODE, SECRET_KEY, common_args={"bk_token": bk_token})


@shared_task(
    bind=True,
    max_retries=MAX_ATTEMPTS,
)
def poll_job_status(self, job_instance_id, bk_biz_id, bk_token):
    """轮询作业执行状态，返回作业元数据"""
    with tracer.start_as_current_span(
        "poll_job_status_task",
        attributes={
            "job.instance_id": str(job_instance_id),
            "job.bk_biz_id": bk_biz_id,
        },
    ) as span:
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

            span.set_attribute("job.step_status", step_status)
            span.set_attribute("job.step_instance_id", str(step_instance_id))

            if step_status == WAITING_CODE:
                span.add_event("job_still_running")
                # 手动实现指数退避: countdown = min(base * 2^retries, max)
                countdown = min(JOB_RESULT_ATTEMPTS_INTERVAL * (2**self.request.retries), JOB_RETRY_BACKOFF_MAX)
                raise self.retry(
                    exc=Exception(f"Job {job_instance_id} is still running"),
                    countdown=countdown,
                )

            is_success = step_status == SUCCESS_CODE
            span.set_attribute("job.is_success", is_success)

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

            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            span.record_exception(e)

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
            raise self.retry(exc=e, countdown=countdown)


@shared_task
def fetch_job_logs(job_status_result, host_id_list, bk_token):
    """批量获取所有主机的执行日志"""
    job_instance_id = job_status_result.get("job_instance_id")

    with tracer.start_as_current_span(
        "fetch_job_logs_task",
        attributes={
            "job.instance_id": str(job_instance_id),
            "job.host_count": len(host_id_list),
        },
    ) as span:
        if not job_status_result.get("success"):
            logger.warning(
                "[获取日志] 上游任务失败，跳过日志获取",
                extra={
                    "job_instance_id": job_instance_id,
                    "error": job_status_result.get("error"),
                },
            )
            span.set_attribute("job.upstream_failed", True)
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

        span.set_attribute("job.step_instance_id", str(step_instance_id))
        span.set_attribute("job.is_success", is_success)

        if not is_success:
            span.add_event("job_execution_failed")
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

            span.set_attribute("job.results_count", len(results))

            return {
                "success": True,
                "is_job_success": True,
                "job_instance_id": job_instance_id,
                "results": results,
            }

        except Exception as e:
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            span.record_exception(e)
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

    with tracer.start_as_current_span(
        "process_backup_results_task",
        attributes={
            "job.instance_id": str(job_instance_id),
        },
    ) as span:
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
            span.set_status(trace.Status(trace.StatusCode.ERROR, "BackupJob不存在"))
            return {"success": False, "error": "BackupJob不存在"}

        if not fetch_logs_result.get("success"):
            error_type = fetch_logs_result.get("error_type")
            error_msg = fetch_logs_result.get("error")

            span.set_attribute("job.error_type", str(error_type))
            span.set_attribute("job.error_msg", error_msg)

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

            span.set_status(trace.Status(trace.StatusCode.ERROR, error_msg))
            return {"success": False, "error_type": error_type, "error": error_msg}

        is_job_success = fetch_logs_result.get("is_job_success")
        results = fetch_logs_result.get("results", [])

        span.set_attribute("job.is_job_success", is_job_success)
        span.set_attribute("job.results_count", len(results))

        if not is_job_success:
            backup_job.mark_failed()
            logger.info(
                "[处理结果] 作业执行失败",
                extra={"job_instance_id": job_instance_id},
            )
            span.add_event("job_marked_failed")
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

        span.set_attribute("job.success_hosts", success_hosts)
        span.set_attribute("job.failed_hosts", failed_hosts)
        span.set_attribute("job.total_files", total_files)

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

        return {
            "success": True,
            "job_status": "completed",
            "success_hosts": success_hosts,
            "failed_hosts": failed_hosts,
            "total_files": total_files,
        }
