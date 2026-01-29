# -*- coding: utf-8 -*-

from django.utils.deprecation import MiddlewareMixin
import logging

logger = logging.getLogger(__name__)

# 这里的CMDB和JOB对应的名称应该同你的URL定义的前缀，详见 /home_application/urls.py

CMDB_BEHAVIORS = [
    'biz-list',
    'set-list',
    'module-list',
    'host-list',
    'host-detail',
    'sync'
]

JOB_BEHAVIORS = [
    'search-file',
    'backup-file',
    'backup-jobs',
    'backup-callback',
]


class RecordUserBehaviorMiddleware(MiddlewareMixin):
    """
    自定义中间件-记录用户行为，进行埋点
    """

    def process_response(self, request, response):
        try:
            # 获取需要埋点存储的信息：用户名、请求的API名称、请求的API所属的类别（CMDB/JOB）
            username = request.user.username

            # 路径格式：/api/biz-list/ -> 获取/api/之后的第一部分
            # 例如：/api/biz-list/ -> biz-list, /api/biz-list/123/ -> biz-list, /api/search-file/?param=1 -> search-file
            path_clean = request.path.rstrip('/')
            
            # 分割路径并找到 /api/ 之后的部分
            path_parts = path_clean.split('/')
            api_name = ''
            
            # 找到 'api' 的索引，并获取其后的第一部分
            try:
                api_index = path_parts.index('api')
                if api_index + 1 < len(path_parts):
                    api_name = path_parts[api_index + 1]
            except ValueError:
                pass

            # 判断接口所属类别
            api_category = 'CMDB' if api_name in CMDB_BEHAVIORS else 'JOB' if api_name in JOB_BEHAVIORS else 'Unknown'

            # 判断是否为错误请求（4xx 或 5xx 状态码）或者返回码不为0
            is_error = response.status_code >= 400
            if not is_error:
                try:
                    if hasattr(response, 'data') and isinstance(response.data, dict):
                        is_error = not response.data.get('result', True)
                except AttributeError as e:
                    is_error = True

            from django.utils import timezone
            today = timezone.now().date()

            from home_application.utils.redis_utils import increment_api_count
            increment_api_count(api_category, api_name, today, is_error)
        except Exception as e:
            # 这里即使产生了异常，也应该继续往后执行，因为埋点记录不应该影响用户请求接口，应该是静默的，所以建议学有余力的同学尝试进行异步优化
            logger.exception(f"Unexpected Exception when record user behavior:{e}")
            pass
        return response