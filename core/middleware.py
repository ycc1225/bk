# -*- coding: utf-8 -*-

from django.utils.deprecation import MiddlewareMixin
import logging
from django.db.models import F


from home_application.models import ApiRequestCount

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

    def process_request(self, request):
        try:
            # 获取需要埋点存储的信息：用户名、请求的API名称、请求的API所属的类别（CMDB/JOB）
            username = request.user.username

            # 路径格式：/api/biz-list/ -> 去除首尾斜杠后分割取最后一个部分
            # 例如：/api/biz-list/ -> biz-list, /api/set-list/ -> set-list
            path_clean = request.path.rstrip('/')
            api_name = path_clean.split('/')[-1] if path_clean else ''

            # 判断接口所属类别
            api_category = 'CMDB' if api_name in CMDB_BEHAVIORS else 'JOB' if api_name in JOB_BEHAVIORS else 'Unknown'

            from home_application.tasks import record_api_request_task
            record_api_request_task.delay(username, api_category, api_name)
        except Exception as e:  # pylint: disable=broad-except
            # 这里即使产生了异常，也应该继续往后执行，因为埋点记录不应该影响用户请求接口，应该是静默的，所以建议学有余力的同学尝试进行异步优化
            logger.exception(f"Unexpected Exception when record user behavior:{e}")
            pass
        return None

