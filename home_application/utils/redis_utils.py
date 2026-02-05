import logging
import time

import redis
from django.conf import settings

logger = logging.getLogger(__name__)

_redis_client = None


def get_redis_client():
    """
    获取 Redis 客户端实例
    """
    global _redis_client
    if _redis_client is None:
        try:
            # 尝试从 settings.BROKER_URL 解析 Redis 配置
            broker_url = getattr(settings, "BROKER_URL", "redis://localhost:6379/0")
            _redis_client = redis.from_url(broker_url)
        except Exception as e:
            logger.error(f"Failed to create redis client: {e}")
            return None
    return _redis_client


API_STATS_KEY = "bk_api_request_stats"


def increment_api_count(category, name, date, is_error=False):
    """
    增加 API 请求计数到 Redis
    :param date: 日期对象或字符串 (YYYY-MM-DD)
    """
    client = get_redis_client()
    if not client:
        logger.warning("Redis client not available, skipping api count increment")
        return

    try:
        # Field 格式: date:category:name:type
        # type: req (总请求), err (错误请求)
        field_suffix = "err" if is_error else "req"
        date_str = str(date)
        field = f"{date_str}:{category}:{name}:{field_suffix}"

        # 使用 HINCRBY 原子增加
        client.hincrby(API_STATS_KEY, field, 1)
    except Exception as e:
        logger.error(f"Failed to increment api count in redis: {e}")


def fetch_api_counts_and_rename():
    """
    获取并重命名 Redis 中的 API 计数 Key，以便后续处理
    返回: (data, temp_key)
    data 格式: { (date, category, name): {'req': count, 'err': count}, ... }
    temp_key: 重命名后的临时 Key，处理完成后需调用 delete_redis_key 删除
    """
    client = get_redis_client()
    if not client:
        return {}, None

    # 使用 RENAME 原子性地将当前统计 Key 重命名，以便处理
    # 这样在处理期间的新写入会进入新的 Key
    temp_key = f"{API_STATS_KEY}_processing_{int(time.time())}"
    # 如果不存在，则直接返回空数据
    if not client.exists(API_STATS_KEY):
        return {}, None
    try:
        client.rename(API_STATS_KEY, temp_key)
    except Exception as e:
        logger.error(f"Failed to rename redis key: {e}")
        return {}, None

    try:
        # 获取所有数据
        raw_data = client.hgetall(temp_key)
    except Exception as e:
        logger.error(f"Failed to fetch redis data: {e}")
        return {}, None

    # 解析数据
    parsed_data = {}
    for field_bytes, count_bytes in raw_data.items():
        try:
            field = field_bytes.decode("utf-8")
            count = int(count_bytes)

            # field 格式: date:category:name:type
            parts = field.rsplit(":", 1)
            if len(parts) != 2:
                continue

            identifier, type_suffix = parts
            # identifier 是 date:category:name

            # 分割 date, category, name
            # 注意：category 或 name 中可能包含冒号吗？假设没有，或者我们限制了它们。
            # 但为了安全，我们假设 date 是 YYYY-MM-DD，没有冒号。
            # 我们可以限制 split 次数

            id_parts = identifier.split(":", 2)
            if len(id_parts) != 3:
                continue

            date_str, category, name = id_parts

            key = (date_str, category, name)
            if key not in parsed_data:
                parsed_data[key] = {"req": 0, "err": 0}

            if type_suffix == "req":
                parsed_data[key]["req"] += count
            elif type_suffix == "err":
                parsed_data[key]["req"] += count
                parsed_data[key]["err"] += count

        except Exception as e:
            logger.error(f"Error parsing redis data field {field_bytes}: {e}")
            continue

    return parsed_data, temp_key


def delete_redis_key(key):
    """
    删除 Redis Key
    """
    client = get_redis_client()
    if not client or not key:
        return

    try:
        client.delete(key)
    except Exception as e:
        logger.error(f"Failed to delete redis key {key}: {e}")


LAST_SYNC_TIME_KEY = "cmdb_last_sync_time"


def set_last_sync_time(timestamp_str):
    """
    设置上次成功同步时间
    :param timestamp_str: 时间字符串
    """
    client = get_redis_client()
    if not client:
        return

    try:
        client.set(LAST_SYNC_TIME_KEY, timestamp_str)
    except Exception as e:
        logger.error(f"Failed to set last sync time: {e}")


def get_last_sync_time():
    """
    获取上次成功同步时间
    :return: 时间字符串 or None
    """
    client = get_redis_client()
    if not client:
        return None

    try:
        val = client.get(LAST_SYNC_TIME_KEY)
        return val.decode("utf-8") if val else None
    except Exception as e:
        logger.error(f"Failed to get last sync time: {e}")
        return None


# 保留旧函数名以兼容（如果其他地方用到），但建议使用新的拆分逻辑
def fetch_and_clear_api_counts():
    """
    (已弃用，建议使用 fetch_api_counts_and_rename + delete_redis_key)
    获取并清除 Redis 中的 API 计数
    """
    data, temp_key = fetch_api_counts_and_rename()
    if temp_key:
        delete_redis_key(temp_key)
    return data
