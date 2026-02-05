import json
import logging
import time

from celery import chain

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

logger = logging.getLogger(__name__)


def batch_get_job_logs(client, job_instance_id, step_instance_id, host_id_list, bk_biz_id):
    """
    公共函数：批量获取作业日志
    供 Task 和 View 共用，避免逻辑重复和解析不一致
    """
    results = []
    try:
        data = {
            "bk_scope_type": "biz",
            "bk_scope_id": bk_biz_id,
            "job_instance_id": job_instance_id,
            "step_instance_id": step_instance_id,
            "host_id_list": host_id_list,
        }

        response = client.jobv3.batch_get_job_instance_ip_log(**data)

        # 调试日志
        logger.info(
            f"batch_get_job_instance_ip_log response keys:"
            f"{response.keys() if isinstance(response, dict) else type(response)}"
        )

        response_data = response.get("data")
        logs_list = response_data.get("script_task_logs")

        if logs_list is None:
            logs_list = []

        for log_item in logs_list:
            if not isinstance(log_item, dict):
                continue

            bk_host_id = log_item.get("host_id")
            log_content = log_item.get("log_content")

            # 严格校验并解析 JSON
            is_success = False
            parsed_data = None

            if log_content:
                try:
                    parsed = json.loads(log_content)
                    # 确保解析结果是列表或字典（符合预期的数据结构）/ 防止任务执行失败但返回了非 JSON 数据，比如打印的错误信息
                    if isinstance(parsed, (list, dict)):
                        is_success = True
                        parsed_data = parsed
                    else:
                        logger.warning(f"日志内容格式不符合预期: host={bk_host_id}, type={type(parsed)}")
                except json.JSONDecodeError:
                    logger.warning(f"日志内容不是有效的 JSON: host={bk_host_id}, content={log_content[:100]}")

            results.append(
                {
                    "bk_host_id": bk_host_id,
                    "is_success": is_success,
                    "log_content": log_content,
                    "parsed_data": parsed_data,
                }
            )

    except Exception as e:
        logger.error(f"批量获取日志异常: job={job_instance_id}, error={e}")
        # 抛出异常或返回空列表，视需求而定，这里返回空列表让上层处理

    return results


class JobExecutionService:
    """Job 执行服务，封装与 Job 平台交互的业务逻辑"""

    def __init__(self, client, bk_biz_id: int):
        """
        初始化服务

        Args:
            client: ESB Client 实例
            bk_biz_id: 业务 ID
        """
        self.client = client
        self.bk_biz_id = bk_biz_id

    def execute_search_file(
        self,
        host_id_list: list[int],
        search_path: str,
        suffix: str,
        plan_id: int,
    ) -> list[dict]:
        """
        执行文件搜索作业（同步等待结果）

        Args:
            host_id_list: 主机 ID 列表
            search_path: 搜索路径
            suffix: 文件后缀
            plan_id: 作业计划 ID

        Returns:
            dict: 包含每个主机的搜索结果

        Raises:
            JobExecutionError: 作业执行失败
            JobTimeoutError: 作业执行超时
            JobStatusError: 作业状态异常
        """
        # 1. 执行作业计划
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

        if not job_instance_id:
            raise JobExecutionError("执行作业失败，未返回 job_instance_id")

        # 2. 轮询作业状态
        kwargs = {
            "bk_scope_type": "biz",
            "bk_scope_id": self.bk_biz_id,
            "job_instance_id": job_instance_id,
        }

        attempts = 0
        step_instance_list = None

        while attempts < MAX_ATTEMPTS:
            status_response = self.client.jobv3.get_job_instance_status(**kwargs)
            step_instance_list = status_response.get("data", {}).get("step_instance_list", [])

            if not step_instance_list:
                raise JobStatusError("未获取到步骤实例信息")

            status_code = step_instance_list[0].get("status")

            if status_code == WAITING_CODE:
                time.sleep(JOB_RESULT_ATTEMPTS_INTERVAL)
                attempts += 1
            elif status_code in (SUCCESS_CODE, FAILED_CODE):
                break
            else:
                raise JobStatusError(f"作业状态异常: {status_code}")

        if attempts == MAX_ATTEMPTS:
            raise JobTimeoutError("作业执行超时")

        step_instance_id = step_instance_list[0].get("step_instance_id")

        # 3. 获取执行日志
        results = batch_get_job_logs(
            client=self.client,
            job_instance_id=job_instance_id,
            step_instance_id=step_instance_id,
            host_id_list=host_id_list,
            bk_biz_id=self.bk_biz_id,
        )

        # 4. 格式化返回结果
        log_list = []
        for res in results:
            bk_host_id = res["bk_host_id"]
            if res["is_success"]:
                parsed_data = res["parsed_data"]
            else:
                parsed_data = {"message": res["log_content"] or "日志内容为空"}
            parsed_data["bk_host_id"] = bk_host_id
            log_list.append(parsed_data)

        return log_list

    def execute_backup_file(
        self,
        host_id_list: list[int],
        search_path: str,
        suffix: str,
        backup_path: str,
        plan_id: int,
        callback_url: str,
    ) -> tuple[str, str] | None:
        """
        执行文件备份作业（异步，不等待结果）

        Args:
            host_id_list: 主机 ID 列表
            search_path: 搜索路径
            suffix: 文件后缀
            backup_path: 备份路径
            plan_id: 作业计划 ID
            callback_url: 回调 URL

        Returns:
            tuple: (job_instance_id, bk_job_link)

        Raises:
            JobExecutionError: 作业执行失败
        """
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

            # 生成作业链接
            bk_job_link = f"{BK_JOB_HOST}/biz/{self.bk_biz_id}/execute/task/{job_instance_id}"

            return str(job_instance_id), bk_job_link

        except Exception as e:
            logger.error(f"执行备份作业异常: {str(e)}")
            if isinstance(e, JobExecutionError):
                raise JobExecutionError(f"执行作业失败: {str(e)}")


class BackupJobService:
    """备份作业服务，封装备份作业的业务逻辑"""

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
        """
        创建备份作业记录

        Args:
            job_instance_id: 作业实例 ID
            operator: 操作人
            search_path: 搜索路径
            suffix: 文件后缀
            backup_path: 备份路径
            bk_job_link: 作业链接
            host_count: 主机数量

        Returns:
            BackupJob: 创建的备份作业实例
        """
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
        """
        启动异步任务链处理备份作业

        Args:
            job_instance_id: 作业实例 ID
            host_id_list: 主机 ID 列表
            bk_biz_id: 业务 ID
            bk_token: 用户 token
        """
        # 局部导入避免循环依赖（tasks.job 导入了 services.job）
        from home_application.tasks.job import (
            fetch_job_logs,
            poll_job_status,
            process_backup_results,
        )

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
