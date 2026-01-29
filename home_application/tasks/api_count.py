from celery import shared_task
from django.db.models import F

from home_application.models import ApiRequestCount
from home_application.utils.redis_utils import fetch_api_counts_and_rename, delete_redis_key

import logging

logger = logging.getLogger(__name__)

@shared_task
def record_api_request_task(username, api_category, api_name, is_error=False, date=None):
    """
    异步记录 API 请求次数 (保留作为备用或单次记录使用)
    """
    try:
        from django.utils import timezone
        if date is None:
            date = timezone.now().date()

        # 根据 api_category, api_name 和 date 记录请求次数
        api_request_count, created = ApiRequestCount.objects.get_or_create(
            api_category=api_category,
            api_name=api_name,
            date=date
        )

        if is_error:
            # 增加错误计数
            api_request_count.error_count = F("error_count") + 1
        else:
            # 增加正常请求计数
            api_request_count.request_count = F("request_count") + 1

        api_request_count.save()
    except Exception as e:
        logger.error(
            f"异步记录用户行为失败: 用户={username}, 类别={api_category}, "
            f"接口={api_name}, 错误={str(e)}"
        )
        pass


@shared_task
def sync_api_counts_task():
    """
    定时任务：从 Redis 同步 API 计数到数据库
    """
    try:
        # 获取并重命名 Redis 中的计数 Key
        data, temp_key = fetch_api_counts_and_rename()

        if not data:
            # 如果有 temp_key 但没有解析出数据（可能是空的），也应该删除它
            if temp_key:
                delete_redis_key(temp_key)
            return "No data to sync"

        count = 0
        try:
            for (date_str, category, name), stats in data.items():
                req_count = stats.get('req', 0)
                err_count = stats.get('err', 0)

                if req_count == 0 and err_count == 0:
                    continue

                # 更新数据库
                # 使用 update_or_create 或者 get_or_create + F 表达式

                obj, created = ApiRequestCount.objects.get_or_create(
                    api_category=category,
                    api_name=name,
                    date=date_str
                )

                # 使用 F 表达式原子更新
                if req_count > 0:
                    obj.request_count = F('request_count') + req_count
                if err_count > 0:
                    obj.error_count = F('error_count') + err_count

                obj.save()
                count += 1

            # 只有在所有数据都成功处理后，才删除 Redis 中的临时 Key
            if temp_key:
                delete_redis_key(temp_key)

            logger.info(f"Successfully synced {count} api request records from redis")
            return f"Synced {count} records"

        except Exception as e:
            # 如果 DB 更新失败，不删除 temp_key，这样数据保留在 Redis 中（虽然可能会导致下次任务无法处理它，除非有恢复机制）
            # 但至少数据没丢。我们可以记录日志，或者考虑后续的手动恢复。
            # 注意：如果不删除，这个 temp_key 会一直占用内存。
            # 更好的策略可能是：对于部分成功的，我们无法回滚。
            # 鉴于这是统计数据，我们可以选择：
            # 1. 无论如何都删除（可能会丢数据）
            # 2. 保留（可能会内存泄漏）
            # 这里选择保留并 Log Error，以便排查。
            logger.error(f"Failed to sync api counts to DB: {e}. Redis key {temp_key} NOT deleted.")
            return f"Failed: {e}"

    except Exception as e:
        logger.error(f"Failed to sync api counts: {e}")
        return f"Failed: {e}"
