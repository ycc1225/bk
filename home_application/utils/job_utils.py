"""
Job 相关工具函数

提供 Job 平台交互的通用工具函数，供 Service 和 Task 层共用
"""

import json
import logging

from home_application.utils.tracing import add_trace_attrs, mark_trace_error

logger = logging.getLogger(__name__)


def batch_get_job_logs(client, job_instance_id, step_instance_id, host_id_list, bk_biz_id):
    """
    批量获取作业日志（通用工具函数）

    供 Service 和 Task 层共用，避免逻辑重复和解析不一致

    Args:
        client: ESB Client 实例
        job_instance_id: 作业实例 ID
        step_instance_id: 步骤实例 ID
        host_id_list: 主机 ID 列表
        bk_biz_id: 业务 ID

    Returns:
        list[dict]: 每个主机的日志解析结果
            [
                {
                    "bk_host_id": int,
                    "is_success": bool,
                    "log_content": str,
                    "parsed_data": dict | list | None
                },
                ...
            ]
    """

    add_trace_attrs(
        util_job_instance_id=job_instance_id,
        util_step_instance_id=step_instance_id,
        util_host_count=len(host_id_list),
        util_bk_biz_id=bk_biz_id,
    )

    results = []

    try:
        # API 调用
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

        # 数据解析
        response_data = response.get("data")
        logs_list = response_data.get("script_task_logs")

        if logs_list is None:
            logs_list = []

        success_count = 0
        failed_count = 0
        json_parse_errors = 0
        total_log_size = 0

        for log_item in logs_list:
            if not isinstance(log_item, dict):
                continue

            bk_host_id = log_item.get("host_id")
            log_content = log_item.get("log_content")

            if log_content:
                total_log_size += len(log_content)

            # 严格校验并解析 JSON
            is_success = False
            parsed_data = None

            if log_content:
                try:
                    parsed = json.loads(log_content)
                    # 确保解析结果是列表或字典（符合预期的数据结构）
                    # 防止任务执行失败但返回了非 JSON 数据，比如打印的错误信息
                    if isinstance(parsed, (list, dict)):
                        is_success = True
                        parsed_data = parsed
                        success_count += 1
                    else:
                        logger.warning(f"日志内容格式不符合预期: host={bk_host_id}, type={type(parsed)}")
                        failed_count += 1
                except json.JSONDecodeError:
                    logger.warning(
                        f"日志内容不是有效的 JSON: host={bk_host_id}, step={job_instance_id}-{step_instance_id}"
                    )
                    json_parse_errors += 1
                    failed_count += 1

            results.append(
                {
                    "bk_host_id": bk_host_id,
                    "is_success": is_success,
                    "log_content": log_content,
                    "parsed_data": parsed_data,
                }
            )

        # 添加统计信息到追踪
        add_trace_attrs(
            util_total_results=len(results),
            util_success_count=success_count,
            util_failed_count=failed_count,
            util_json_parse_errors=json_parse_errors,
            util_total_log_size_bytes=total_log_size,
        )

    except Exception as e:
        mark_trace_error(e)
        logger.error(f"批量获取日志异常: job={job_instance_id}, error={e}")
        # 返回空列表让上层处理

    return results
