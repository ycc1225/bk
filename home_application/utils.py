# -*- coding: utf-8 -*-
"""
数据同步工具类
"""
import json
from typing import Any, Dict

from django.db import transaction
from django.http import JsonResponse

from blueking.component.shortcuts import get_client_by_request
from home_application.models import BizInfo, SetInfo, ModuleInfo


class DataSyncManager:
    """
    数据同步管理器
    """

    # API配置映射
    API_CONFIGS = {
        'biz': {
            'model': BizInfo,
            'api_method': 'search_business',
            'unique_field': 'bk_biz_id',
            'fields': ['bk_biz_id', 'bk_biz_name'],
            'defaults_map': {'bk_biz_name': 'bk_biz_name'}
        },
        'set': {
            'model': SetInfo,
            'api_method': 'search_set',
            'unique_field': 'bk_set_id',
            'fields': ['bk_set_id', 'bk_set_name', 'bk_biz_id'],
            'defaults_map': {'bk_set_name': 'bk_set_name', 'bk_biz_id': 'bk_biz_id'}
        },
        'module': {
            'model': ModuleInfo,
            'api_method': 'search_module',
            'unique_field': 'bk_module_id',
            'fields': ['bk_module_id', 'bk_module_name', 'bk_set_id', 'bk_biz_id'],
            'defaults_map': {
                'bk_module_name': 'bk_module_name',
                'bk_set_id': 'bk_set_id',
                'bk_biz_id': 'bk_biz_id'
            }
        }
    }

    @staticmethod
    def _call_api(client, api_method, api_kwargs):
        """统一API调用方法"""
        method = getattr(client.cc, api_method)
        return method(api_kwargs)

    @staticmethod
    def _save_data_to_db(model_class, data_list, unique_field, defaults_map):
        """统一数据保存方法"""
        valid_data = []
        for item in data_list:
            # 验证必需字段
            required_fields = list(defaults_map.keys()) + [unique_field]
            if all(field in item and item[field] is not None for field in required_fields):
                valid_data.append(item)

        # 批量保存数据
        for item in valid_data:
            defaults = {}
            for field, api_field in defaults_map.items():
                if api_field in item:
                    defaults[field] = item[api_field]

            model_class.objects.update_or_create(
                **{unique_field: item[unique_field]},
                defaults=defaults
            )

    @staticmethod
    def get_data(data_type, request, filter_params=None, api_kwargs=None):
        """
        统一数据获取方法

        Args:
            data_type: 数据类型 (biz/set/module)
            request: Django请求对象
            filter_params: 数据库查询参数
            api_kwargs: API调用参数
        """
        if data_type not in DataSyncManager.API_CONFIGS:
            return JsonResponse({"result": False, "message": "不支持的数据类型"})

        config = DataSyncManager.API_CONFIGS[data_type]
        model_class = config['model']

        # 优先从数据库获取
        queryset = model_class.objects.filter(**(filter_params or {}))
        if queryset.exists():
            data = list(queryset.values(*config['fields']))
            return JsonResponse({
                "result": True,
                "data": {
                    "count": queryset.count(),
                    "info": data
                }
            })

        # 数据库没有数据，调用API
        client = get_client_by_request(request)
        result = DataSyncManager._call_api(client, config['api_method'], api_kwargs or {})

        if result.get("result") and "data" in result:
            try:
                with transaction.atomic():
                    DataSyncManager._save_data_to_db(
                        model_class,
                        result["data"]["info"],
                        config['unique_field'],
                        config['defaults_map']
                    )
            except Exception as e:
                return JsonResponse({
                    "result": False,
                    "message": f"数据同步失败: {str(e)}"
                })
        return JsonResponse(result)

    @staticmethod
    def get_bizs_data(request):
        """获取业务数据"""
        return DataSyncManager.get_data('biz', request)

    @staticmethod
    def get_sets_data(request, bk_biz_id):
        """获取集群数据"""
        return DataSyncManager.get_data('set', request, {'bk_biz_id': bk_biz_id}, {'bk_biz_id': bk_biz_id})

    @staticmethod
    def get_modules_data(request, bk_biz_id, bk_set_id):
        """获取模块数据"""
        return DataSyncManager.get_data('module', request, {'bk_biz_id': bk_biz_id, 'bk_set_id': bk_set_id},
                                        {'bk_biz_id': bk_biz_id, 'bk_set_id': bk_set_id})

    @staticmethod
    def sync_data(client, sync_type=None, bk_biz_id=None, bk_set_id=None):
        """
        统一的数据同步接口

        Args:
            client: Django请求对象
            sync_type: 同步类型 (biz/set/module/all)
            bk_biz_id: 业务ID
            bk_set_id: 集群ID
        """


        # 确定需要同步的数据类型
        sync_types = []
        if sync_type in ["biz", "set", "module"]:
            sync_types = [sync_type]
        else:
            return {"result": False, "message": "不支持的同步类型"}

        try:
            with transaction.atomic():
                for data_type in sync_types:
                    config = DataSyncManager.API_CONFIGS[data_type]

                    # 构建API参数
                    api_kwargs = {
                        "fields": config['fields'],
                        "page": {"start": 0, "limit": 100, "sort": ""}
                    }

                    # 只有set和module数据类型才需要业务ID参数
                    if data_type in ["set", "module"] and bk_biz_id:
                        api_kwargs["bk_biz_id"] = bk_biz_id
                    # 只有module数据类型才需要集群ID参数
                    if data_type == "module" and bk_set_id:
                        api_kwargs["bk_set_id"] = bk_set_id

                    # 调用API获取数据
                    result = DataSyncManager._call_api(client, config['api_method'], api_kwargs)

                    if result.get("result") and "data" in result:
                        # 保存数据到数据库
                        DataSyncManager._save_data_to_db(
                            config['model'],
                            result["data"]["info"],
                            config['unique_field'],
                            config['defaults_map']
                        )

            return {
                "result": True,
                "message": f"{sync_type}数据同步成功"
            }

        except Exception as e:
            return {
                "result": False,
                "message": f"数据同步失败: {str(e)}"
            }

    @staticmethod
    def _call_cmdb_api(url: str, headers: Dict[str, str], data: Dict[str, Any]) -> Dict[str, Any]:
        """
        通过HTTP请求调用CMDB API

        Args:
            url: API地址
            headers: 请求头
            data: 请求体

        Returns:
            API响应数据

        Raises:
            Exception: 当API调用失败时
        """
        import requests
        import logging
        logger = logging.getLogger("celery")

        try:
            response = requests.request("post",url, headers=headers, data=data)
            
            if response.status_code != 200:
                error_msg = f"CMDB API调用失败: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)

            result = response.json()
            
            if result.get('result', False) is False:
                error_msg = result.get('message', '未知错误')
                logger.error(f"CMDB API返回错误: {error_msg}")
                raise Exception(error_msg)

            return result

        except requests.exceptions.RequestException as e:
            logger.error(f"CMDB API请求异常: {str(e)}")
            raise Exception(f"网络请求失败: {str(e)}")

    @staticmethod
    def sync_all_data(auth_header: Dict[str, str]) -> Dict[str, Any]:
        """
        同步所有CMDB数据（业务、集群、模块）到数据库
        通过HTTP请求直接调用CMDB API，不使用BK SDK的client

        Args:
            auth_header: 认证请求头，包含 BK-APP-CODE 和 BK-APP-SECRET 等信息

        Returns:
            同步结果字典
            {
                "result": True/False,
                "message": "同步成功/失败",
                "data": {
                    "biz_count": 业务数量,
                    "set_count": 集群数量,
                    "module_count": 模块数量
                }
            }
        """
        import logging
        logger = logging.getLogger(__name__)

        # CMDB API基础URL
        base_url = "https://bkapi.ce.bktencent.com/api/bk-cmdb/prod/api/v3"
        bk_supplier_account = "0"
        headers = {"X-Bkapi-Authorization": json.dumps(auth_header)}

        stats = {
            "biz_count": 0,
            "set_count": 0,
            "module_count": 0
        }

        try:
            with transaction.atomic():
                # 1. 同步业务数据
                logger.info("开始同步业务数据...")
                biz_url = f"{base_url}/biz/search/{bk_supplier_account}"
                biz_result = DataSyncManager._call_cmdb_api(
                    biz_url,
                    headers,
                    {}
                )

                biz_list = biz_result.get('data', {}).get('info', [])
                if biz_list:
                    DataSyncManager._save_data_to_db(
                        BizInfo,
                        biz_list,
                        'bk_biz_id',
                        {'bk_biz_name': 'bk_biz_name'}
                    )
                    stats["biz_count"] = len(biz_list)
                    logger.info(f"业务数据同步完成，共 {stats['biz_count']} 条")

                # 2. 同步集群和模块数据
                for biz in biz_list:
                    bk_biz_id = biz.get('bk_biz_id')
                    if bk_biz_id is None:
                        continue

                    logger.info(f"开始同步业务 {bk_biz_id} 的集群和模块数据...")

                    # 获取集群列表
                    set_url = f"{base_url}/set/search/{bk_supplier_account}/{bk_biz_id}"
                    set_result = DataSyncManager._call_cmdb_api(
                        set_url,
                        headers,
                        {}
                    )

                    set_list = set_result.get('data', {}).get('info', [])
                    if set_list:
                        DataSyncManager._save_data_to_db(
                            SetInfo,
                            set_list,
                            'bk_set_id',
                            {
                                'bk_set_name': 'bk_set_name',
                                'bk_biz_id': 'bk_biz_id'
                            }
                        )
                        stats["set_count"] += len(set_list)

                    # 获取每个集群的模块列表
                    for bk_set in set_list:
                        bk_set_id = bk_set.get('bk_set_id')
                        if bk_set_id is None:
                            continue

                        module_url = f"{base_url}/module/search/{bk_supplier_account}/{bk_biz_id}/{bk_set_id}"
                        module_result = DataSyncManager._call_cmdb_api(
                            module_url,
                            headers,
                            {}
                        )

                        module_list = module_result.get('data', {}).get('info', [])
                        if module_list:
                            DataSyncManager._save_data_to_db(
                                ModuleInfo,
                                module_list,
                                'bk_module_id',
                                {
                                    'bk_module_name': 'bk_module_name',
                                    'bk_set_id': 'bk_set_id',
                                    'bk_biz_id': 'bk_biz_id'
                                }
                            )
                            stats["module_count"] += len(module_list)

                    logger.info(f"业务 {bk_biz_id} 数据同步完成：集群 {len(set_list)} 个，模块 {sum(len(m.get('data', {}).get('info', [])) for m in [])} 个")

            return {
                "result": True,
                "message": "全量数据同步成功",
                "data": stats
            }

        except Exception as e:
            logger.exception(f"全量数据同步失败: {str(e)}")
            return {
                "result": False,
                "message": f"全量数据同步失败: {str(e)}",
                "data": stats
            }


