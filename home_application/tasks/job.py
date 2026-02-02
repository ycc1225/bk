import logging

from celery import shared_task

from blueking.component import client as component_client
from config import APP_CODE, SECRET_KEY
from home_application.constants import (
    JOB_RESULT_ATTEMPTS_INTERVAL,
    MAX_ATTEMPTS,
    SUCCESS_CODE,
    WAITING_CODE,
)
from home_application.models import BackupJob, BackupRecord
from home_application.services.job import batch_get_job_logs

logger = logging.getLogger(__name__)


def get_esb_client(bk_token):
    """
    获取 ESB Client
    """
    return component_client.ComponentClient(APP_CODE, SECRET_KEY, common_args={"bk_token": bk_token})


@shared_task(bind=True)
def poll_job_status(self, job_instance_id, bk_biz_id, bk_token):
    """
    通用任务：轮询作业执行状态
    返回作业的基本元数据，不涉及具体业务处理
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
        logger.error(f"查询作业状态异常: job_instance_id={job_instance_id}, error={str(e)}")
        raise self.retry(exc=e, countdown=JOB_RESULT_ATTEMPTS_INTERVAL, max_retries=MAX_ATTEMPTS)


@shared_task
def fetch_job_logs(job_status_result, host_id_list, bk_token):
    """
    通用任务：批量获取所有主机的执行日志
    """
    job_instance_id = job_status_result.get("job_instance_id")
    step_instance_id = job_status_result.get("step_instance_id")
    bk_biz_id = job_status_result.get("bk_biz_id")
    is_success = job_status_result.get("is_success")

    # 如果作业本身失败，直接传递失败状态
    if not is_success:
        return {"is_job_success": False, "job_instance_id": job_instance_id, "results": []}

    client = get_esb_client(bk_token)

    # 调用公共函数
    results = batch_get_job_logs(
        client=client,
        job_instance_id=job_instance_id,
        step_instance_id=step_instance_id,
        host_id_list=host_id_list,
        bk_biz_id=bk_biz_id,
    )

    return {"is_job_success": True, "job_instance_id": job_instance_id, "results": results}


@shared_task
def process_backup_results(fetch_logs_result):
    """
    业务任务：处理备份作业结果
    """
    job_instance_id = fetch_logs_result.get("job_instance_id")
    is_job_success = fetch_logs_result.get("is_job_success")
    results = fetch_logs_result.get("results", [])

    logger.info(f"开始处理备份作业结果: job_instance_id={job_instance_id}, result_count={len(results)}")

    try:
        backup_job = BackupJob.objects.get(job_instance_id=job_instance_id)
    except BackupJob.DoesNotExist:
        logger.error(f"BackupJob不存在: {job_instance_id}")
        return

    if not is_job_success:
        backup_job.mark_failed()
        return

    total_files = 0
    success_hosts = 0
    failed_hosts = 0

    for res in results:
        bk_host_id = res.get("bk_host_id")
        parsed_data = res.get("parsed_data")

        if not res.get("is_success") or not parsed_data:
            failed_hosts += 1
            continue

        # 直接使用已解析的数据
        if isinstance(parsed_data, dict):
            json_step_res = [parsed_data]
        else:
            json_step_res = parsed_data

        for step_res in json_step_res:
            BackupRecord.objects.create(
                backup_job=backup_job,
                bk_host_id=bk_host_id,
                status="success",
                bk_backup_name=step_res.get("bk_backup_name", "unknown"),
            )
            total_files += 1

        success_hosts += 1

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
