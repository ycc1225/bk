# -*- coding: utf-8 -*-
"""
数据同步工具类
"""

from django.http import JsonResponse
from django.db import transaction
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
    def sync_data(request, sync_type=None, bk_biz_id=None, bk_set_id=None):
        """
        统一的数据同步接口

        Args:
            request: Django请求对象
            sync_type: 同步类型 (biz/set/module/all)
            bk_biz_id: 业务ID
            bk_set_id: 集群ID
        """
        client = get_client_by_request(request)

        # 确定需要同步的数据类型
        sync_types = []
        if sync_type == "all":
            sync_types = ["biz", "set", "module"]
        elif sync_type in ["biz", "set", "module"]:
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