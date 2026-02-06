import logging
import time

from celery import chain
from opentelemetry import trace

from home_application.constants import (
    BK_JOB_HOST,
    FAILED_CODE,
    JOB_RESULT_ATTEMPTS_INTERVAL,
    MAX_ATTEMPTS,
    SUCCESS_CODE,
    WAITING_CODE,
)
from home_application.exceptions.job import (
    JobExecutionError,
    JobStatusError,
    JobTimeoutError,
)
from home_application.models import BackupJob
from home_application.tasks.job import (
    fetch_job_logs,
    poll_job_status,
    process_backup_results,
)
from home_application.utils.job_utils import batch_get_job_logs

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


class JobExecutionService:
    """Job 执行服务"""

    def __init__(self, client, bk_biz_id: int):
        self.client = client
        self.bk_biz_id = bk_biz_id

    def execute_search_file(
        self,
        host_id_list: list[int],
        search_path: str,
        suffix: str,
        plan_id: int,
    ) -> list[dict]:
        """执行文件搜索作业（同步等待结果）"""
        with tracer.start_as_current_span(
            "execute_search_file",
            attributes={
                "job.host_count": len(host_id_list),
                "job.search_path": search_path,
                "job.suffix": suffix,
                "job.plan_id": plan_id,
            },
        ) as parent_span:
            job_instance_id = None

            try:
                with tracer.start_as_current_span(
                    "execute_job_plan",
                    attributes={
                        "job.bk_biz_id": self.bk_biz_id,
                        "job.plan_id": plan_id,
                    },
                ) as span:
                    kwargs = {
                        "bk_scope_type": "biz",
                        "bk_scope_id": self.bk_biz_id,
                        "job_plan_id": plan_id,
                        "global_var_list": [
                            {
                                "name": "host_list",
                                "server": {
                                    "host_id_list": host_id_list,
                                },
                            },
                            {"name": "search_path", "value": search_path},
                            {"name": "suffix", "value": suffix},
                        ],
                    }

                    response = self.client.jobv3.execute_job_plan(**kwargs)
                    job_instance_id = response.get("data", {}).get("job_instance_id")

                    span.set_attribute("job.instance_id", str(job_instance_id))

                    if not job_instance_id:
                        span.set_status(trace.Status(trace.StatusCode.ERROR, "未返回 job_instance_id"))
                        raise JobExecutionError("执行作业失败，未返回 job_instance_id")

                parent_span.set_attribute("job.instance_id", str(job_instance_id))

                with tracer.start_as_current_span(
                    "poll_job_status",
                    attributes={
                        "job.instance_id": str(job_instance_id),
                        "job.max_attempts": MAX_ATTEMPTS,
                    },
                ) as span:
                    kwargs = {
                        "bk_scope_type": "biz",
                        "bk_scope_id": self.bk_biz_id,
                        "job_instance_id": job_instance_id,
                    }

                    attempts = 0
                    step_instance_list = None
                    total_api_time = 0

                    while attempts < MAX_ATTEMPTS:
                        api_start = time.time()
                        status_response = self.client.jobv3.get_job_instance_status(**kwargs)
                        api_duration = time.time() - api_start
                        total_api_time += api_duration

                        step_instance_list = status_response.get("data", {}).get("step_instance_list", [])

                        if not step_instance_list:
                            span.set_status(trace.Status(trace.StatusCode.ERROR, "未获取到步骤实例信息"))
                            raise JobStatusError("未获取到步骤实例信息")

                        status_code = step_instance_list[0].get("status")

                        span.add_event(
                            f"poll_attempt_{attempts + 1}",
                            attributes={
                                "attempt": attempts + 1,
                                "status_code": status_code,
                                "api_duration_ms": int(api_duration * 1000),
                            },
                        )

                        if status_code == WAITING_CODE:
                            time.sleep(JOB_RESULT_ATTEMPTS_INTERVAL)
                            attempts += 1
                        elif status_code in (SUCCESS_CODE, FAILED_CODE):
                            break
                        else:
                            span.set_status(trace.Status(trace.StatusCode.ERROR, f"作业状态异常: {status_code}"))
                            raise JobStatusError(f"作业状态异常: {status_code}")

                    if attempts == MAX_ATTEMPTS:
                        span.set_status(trace.Status(trace.StatusCode.ERROR, "作业执行超时"))
                        raise JobTimeoutError("作业执行超时")

                    sleep_time = attempts * JOB_RESULT_ATTEMPTS_INTERVAL * 1000

                    span.set_attribute("job.poll_attempts", attempts + 1)
                    span.set_attribute("job.final_status", status_code)
                    span.set_attribute("job.poll_api_time_ms", int(total_api_time * 1000))
                    span.set_attribute("job.poll_sleep_time_ms", sleep_time)

                step_instance_id = step_instance_list[0].get("step_instance_id")

                with tracer.start_as_current_span(
                    "fetch_job_logs",
                    attributes={
                        "job.instance_id": str(job_instance_id),
                        "job.step_instance_id": str(step_instance_id),
                        "job.host_count": len(host_id_list),
                    },
                ):
                    results = batch_get_job_logs(
                        client=self.client,
                        job_instance_id=job_instance_id,
                        step_instance_id=step_instance_id,
                        host_id_list=host_id_list,
                        bk_biz_id=self.bk_biz_id,
                    )

                with tracer.start_as_current_span("format_results") as span:
                    log_list = []
                    success_count = 0
                    failed_count = 0

                    for res in results:
                        bk_host_id = res["bk_host_id"]
                        if res["is_success"]:
                            parsed_data = res["parsed_data"]
                            success_count += 1
                        else:
                            parsed_data = {"message": res["log_content"] or "日志内容为空"}
                            failed_count += 1
                        parsed_data["bk_host_id"] = bk_host_id
                        log_list.append(parsed_data)

                    span.set_attribute("job.success_hosts", success_count)
                    span.set_attribute("job.failed_hosts", failed_count)

                parent_span.set_attribute("job.total_hosts", len(host_id_list))
                parent_span.set_attribute("job.success_hosts", success_count)
                parent_span.set_attribute("job.failed_hosts", failed_count)

                return log_list

            except Exception as e:
                parent_span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                parent_span.record_exception(e)
                raise

    def execute_backup_file(
        self,
        host_id_list: list[int],
        search_path: str,
        suffix: str,
        backup_path: str,
        plan_id: int,
        callback_url: str,
    ) -> tuple[str, str] | None:
        """执行文件备份作业（异步，不等待结果）"""
        kwargs = {
            "bk_scope_type": "biz",
            "bk_scope_id": self.bk_biz_id,
            "job_plan_id": plan_id,
            "global_var_list": [
                {
                    "name": "host_list",
                    "server": {
                        "host_id_list": host_id_list,
                    },
                },
                {"name": "search_path", "value": search_path},
                {"name": "suffix", "value": suffix},
                {"name": "backup_path", "value": backup_path},
            ],
            "callback_url": callback_url,
        }

        try:
            response = self.client.jobv3.execute_job_plan(**kwargs)
            job_instance_id = response.get("data", {}).get("job_instance_id")

            if not job_instance_id:
                raise JobExecutionError("执行作业失败，未返回 job_instance_id")

            bk_job_link = f"{BK_JOB_HOST}/biz/{self.bk_biz_id}/execute/task/{job_instance_id}"

            return str(job_instance_id), bk_job_link

        except Exception as e:
            logger.error(f"执行备份作业异常: {str(e)}")
            if isinstance(e, JobExecutionError):
                raise JobExecutionError(f"执行作业失败: {str(e)}")


class BackupJobService:
    """备份作业服务"""

    @staticmethod
    def create_backup_job(
        job_instance_id: str,
        operator: str,
        search_path: str,
        suffix: str,
        backup_path: str,
        bk_job_link: str,
        host_count: int,
    ) -> BackupJob:
        return BackupJob.objects.create(
            job_instance_id=job_instance_id,
            operator=operator,
            search_path=search_path,
            suffix=suffix,
            backup_path=backup_path,
            bk_job_link=bk_job_link,
            status=BackupJob.Status.PENDING,
            host_count=host_count,
            file_count=0,
        )

    @staticmethod
    def start_async_processing(
        job_instance_id: str,
        host_id_list: list[int],
        bk_biz_id: int,
        bk_token: str,
    ):
        """启动异步任务链处理备份作业"""
        try:
            chain(
                poll_job_status.s(
                    job_instance_id=job_instance_id,
                    bk_biz_id=bk_biz_id,
                    bk_token=bk_token,
                ),
                fetch_job_logs.s(host_id_list=host_id_list, bk_token=bk_token),
                process_backup_results.s(),
            ).apply_async()
        except Exception as e:
            logger.error(f"启动异步任务链失败: {str(e)}")
