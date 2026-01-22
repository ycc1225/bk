# -*- coding: utf-8 -*-
import redis
import logging
from django.conf import settings
from urllib.parse import urlparse

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
            broker_url = getattr(settings, 'BROKER_URL', 'redis://localhost:6379/0')
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

def fetch_and_clear_api_counts():
    """
    获取并清除 Redis 中的 API 计数
    返回格式: { (date, category, name): {'req': count, 'err': count}, ... }
    """
    client = get_redis_client()
    if not client:
        return {}

    # 使用 RENAME 原子性地将当前统计 Key 重命名，以便处理
    # 这样在处理期间的新写入会进入新的 Key
    import time
    temp_key = f"{API_STATS_KEY}_processing_{int(time.time())}"
    
    try:
        client.rename(API_STATS_KEY, temp_key)
    except redis.exceptions.ResponseError:
        # Key 不存在（通常意味着没有数据）
        return {}
    except Exception as e:
        logger.error(f"Failed to rename redis key: {e}")
        return {}

    try:
        # 获取所有数据
        raw_data = client.hgetall(temp_key)
        # 处理完后删除临时 Key
        client.delete(temp_key)
    except Exception as e:
        logger.error(f"Failed to fetch/delete redis data: {e}")
        return {}

    # 解析数据
    parsed_data = {}
    for field_bytes, count_bytes in raw_data.items():
        try:
            field = field_bytes.decode('utf-8')
            count = int(count_bytes)
            
            # field 格式: date:category:name:type
            parts = field.rsplit(':', 1)
            if len(parts) != 2:
                continue
                
            identifier, type_suffix = parts
            # identifier 是 date:category:name
            
            # 分割 date, category, name
            # 注意：category 或 name 中可能包含冒号吗？假设没有，或者我们限制了它们。
            # 但为了安全，我们假设 date 是 YYYY-MM-DD，没有冒号。
            # 我们可以限制 split 次数
            
            id_parts = identifier.split(':', 2)
            if len(id_parts) != 3:
                continue
                
            date_str, category, name = id_parts
            
            key = (date_str, category, name)
            if key not in parsed_data:
                parsed_data[key] = {'req': 0, 'err': 0}
            
            if type_suffix == 'req':
                parsed_data[key]['req'] += count
            elif type_suffix == 'err':
                parsed_data[key]['err'] += count
                
        except Exception as e:
            logger.error(f"Error parsing redis data field {field_bytes}: {e}")
            continue
            
    return parsed_data