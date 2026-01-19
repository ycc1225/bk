# -*- coding: utf-8 -*-
"""
Celery 异步任务定义
"""
import logging
import os

from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist

from blueking.component.shortcuts import get_client_by_user
from home_application.models import ApiRequestCount, BizInfo, SetInfo, ModuleInfo
from home_application.utils import DataSyncManager

logger = logging.getLogger(__name__)


@shared_task
def record_api_request_task(username, api_category, api_name):
    """
    异步记录 API 请求次数
    
    Args:
        username (str): 用户名
        api_category (str): API类别（CMDB/JOB/Unknown）
        api_name (str): API名称
    """
    try:
        # 根据 api_category 和 api_name 记录请求次数
        api_request_count, created = ApiRequestCount.objects.get_or_create(
            api_category=api_category,
            api_name=api_name
        )
        
        # 使用 F() 表达式原子性地增加请求次数
        from django.db.models import F
        api_request_count.request_count = F("request_count") + 1
        api_request_count.save()
        
        logger.info(
            f"成功记录用户行为: 用户={username}, 类别={api_category}, "
            f"接口={api_name}, 新记录={created}"
        )
    except Exception as e:
        logger.error(
            f"异步记录用户行为失败: 用户={username}, 类别={api_category}, "
            f"接口={api_name}, 错误={str(e)}"
        )
        # 任务失败不会影响主流程，静默处理
        pass


@shared_task
def sync_data():
    """
    异步同步数据
    """
    from blueapps.account.models import User

    try:
        # 同步数据
        auth_header = {
            "bk_username": "25zhujiao1",
            "bk_app_code": os.getenv("BKPAAS_APP_ID"),
            "bk_app_secret": os.getenv("BKPAAS_APP_SECRET"),
        }
        DataSyncManager.sync_all_data(auth_header)
        logger.info("成功同步数据")
    except Exception as e:
        logger.error(f"异步同步数据失败: {str(e)}")
        pass