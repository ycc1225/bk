# -*- coding: utf-8 -*-
"""
CMDB 数据仓库层 - 管理CMDB数据的获取和缓存
"""
import json
import logging
import os
from typing import Optional

import requests
from django.db import transaction
from django.http import JsonResponse, HttpRequest

from home_application.models import BizInfo, SetInfo, ModuleInfo

logger = logging.getLogger(__name__)


class CmdbFetchStrategy:
    """CMDB 数据获取策略枚举"""
    CACHE_FIRST = "cache_first"  # 优先从数据库缓存获取，未命中时调用API并保存（默认）
    MANUAL_REFRESH = "manual_refresh"  # 手动刷新：从API获取、保存到数据库并返回数据（用户接口）
    BACKGROUND_SYNC = "background_sync"  # 后台同步：从API获取、保存到数据库但不返回数据（定时任务）


class CmdbRepository:
    """
    CMDB 数据仓库类 - 专门管理CMDB业务、集群、模块数据

    职责：
    1. 统一管理CMDB数据（业务、集群、模块）的获取逻辑
    2. 支持从数据库缓存或API获取数据
    3. 提供针对CMDB的专用方法
    4. 支持两种认证方式：
       - 定时任务模式：auth_header直接传入（bk_username验证）
       - HTTP请求模式：request对象传入（bk_token验证）
    """

    # CMDB API配置
    CMDB_BASE_URL = "https://bkapi.ce.bktencent.com/api/bk-cmdb/prod/api/v3"
    CMDB_SUPPLIER_ACCOUNT = "0"

    # CMDB数据类型对应的API端点
    API_ENDPOINTS = {
        'biz': '/biz/search/{supplier_account}',
        'set': '/set/search/{supplier_account}/{bk_biz_id}',
        'module': '/module/search/{supplier_account}/{bk_biz_id}/{bk_set_id}'
    }

    # CMDB 数据配置
    _DATA_CONFIGS = {
        'biz': {
            'model': BizInfo,
            'unique_field': 'bk_biz_id',
            'fields': ['bk_biz_id', 'bk_biz_name'],
            'defaults_map': {'bk_biz_name': 'bk_biz_name'}
        },
        'set': {
            'model': SetInfo,
            'unique_field': 'bk_set_id',
            'fields': ['bk_set_id', 'bk_set_name', 'bk_biz_id'],
            'defaults_map': {
                'bk_set_name': 'bk_set_name',
                'bk_biz_id': 'bk_biz_id'
            }
        },
        'module': {
            'model': ModuleInfo,
            'unique_field': 'bk_module_id',
            'fields': ['bk_module_id', 'bk_module_name', 'bk_set_id', 'bk_biz_id'],
            'defaults_map': {
                'bk_module_name': 'bk_module_name',
                'bk_set_id': 'bk_set_id',
                'bk_biz_id': 'bk_biz_id'
            }
        }
    }

    def __init__(
        self,
        auth: Optional[dict] = None,
        request: Optional[HttpRequest] = None
    ):
        """
        初始化 CMDB 仓库

        Args:
            auth: 定时任务认证请求头（可选）
                         格式：{"bk_username": "", "bk_app_code": "", "bk_app_secret": ""}
            request: HTTP请求对象（可选），用于通过bk_token获取认证信息

        Note:
            两种认证方式二选一：
            1. 定时任务模式：传入auth_header
            2. HTTP请求模式：传入request对象
            3. 默认模式：从环境变量读取认证信息
        """
        # 验证认证方式
        if auth and request:
            raise ValueError("auth_header和request不能同时传入，请选择一种认证方式")

        if not auth and not request:
            # 默认使用环境变量初始化定时任务认证
            self.auth_header = self._get_default_auth_header()
            self.client = None
            self.auth_type = "scheduled_task"
            logger.info("CmdbRepository 初始化完成（使用默认定时任务认证）")
        elif auth:
            # 定时任务模式
            self.auth_header = auth
            self.client = None
            self.auth_type = "scheduled_task"
            logger.info("CmdbRepository 初始化完成（使用定时任务认证）")
        else:
            # HTTP请求模式
            self.auth_header = None
            self.client = self._get_client_by_request(request)
            self.auth_type = "http_request"
            logger.info("CmdbRepository 初始化完成（使用HTTP请求认证）")

    def _get_default_auth_header(self) -> Optional[dict]:
        """
        获取默认的定时任务认证头（从环境变量读取）
        """
        try:
            return {
                "bk_username": os.getenv("BKPAAS_USERNAME", "25zhujiao1"),
                "bk_app_code": os.getenv("BKPAAS_APP_ID"),
                "bk_app_secret": os.getenv("BKPAAS_APP_SECRET"),
            }
        except Exception as e:
            logger.error(f"获取默认认证头失败: {str(e)}")
            return None

    def _get_client_by_request(self, request: HttpRequest):
        """
        通过request对象获取客户端（使用bk_token认证）

        Args:
            request: Django HttpRequest对象

        Returns:
            包含认证信息的client对象
        """
        try:
            from blueking.component.shortcuts import get_client_by_request
            client = get_client_by_request(request)
            logger.info(f"通过request获取client成功: {client}")
            return client
        except ImportError:
            logger.error("无法导入get_client_by_request，请确保已安装blueapps")
            return None
        except Exception as e:
            logger.error(f"获取client失败: {str(e)}")
            return None

    def get_biz_list(
        self,
        filter_params: Optional[dict] = None,
        api_caller=None,
        api_params: Optional[dict] = None,
        strategy: str = CmdbFetchStrategy.CACHE_FIRST,
        auto_save: bool = True
    ) -> JsonResponse:
        """
        获取业务列表

        Args:
            filter_params: 数据库查询参数
            api_caller: 自定义CMDB API调用函数（可选，如果为空则使用内置HTTP调用）
            api_params: API调用参数
            strategy: 获取策略
            auto_save: 是否自动将API数据保存到数据库

        Returns:
            JsonResponse: 业务列表数据
        """
        return self._fetch_data(
            data_type='biz',
            filter_params=filter_params,
            api_caller=api_caller or self._build_api_caller('biz'),
            api_params=api_params,
            strategy=strategy,
            auto_save=auto_save
        )

    def get_set_list(
        self,
        bk_biz_id: int,
        filter_params: Optional[dict] = None,
        api_caller=None,
        api_params: Optional[dict] = None,
        strategy: str = CmdbFetchStrategy.CACHE_FIRST,
        auto_save: bool = True
    ) -> JsonResponse:
        """
        获取集群列表

        Args:
            bk_biz_id: 业务ID（必填）
            filter_params: 数据库查询参数
            api_caller: 自定义CMDB API调用函数（可选）
            api_params: API调用参数
            strategy: 获取策略
            auto_save: 是否自动将API数据保存到数据库

        Returns:
            JsonResponse: 集群列表数据
        """
        if not bk_biz_id:
            return JsonResponse({
                "result": False,
                "message": "业务ID不能为空"
            })

        # 合并筛选条件：确保按业务ID查询
        if filter_params is None:
            filter_params = {}
        filter_params['bk_biz_id'] = bk_biz_id

        return self._fetch_data(
            data_type='set',
            filter_params=filter_params,
            api_caller=api_caller or self._build_api_caller('set', bk_biz_id=bk_biz_id),
            api_params=api_params,
            strategy=strategy,
            auto_save=auto_save
        )

    def get_module_list(
        self,
        bk_biz_id: int,
        bk_set_id: int,
        filter_params: Optional[dict] = None,
        api_caller=None,
        api_params: Optional[dict] = None,
        strategy: str = CmdbFetchStrategy.CACHE_FIRST,
        auto_save: bool = True
    ) -> JsonResponse:
        """
        获取模块列表

        Args:
            bk_biz_id: 业务ID（必填）
            bk_set_id: 集群ID（必填）
            filter_params: 数据库查询参数
            api_caller: 自定义CMDB API调用函数（可选）
            api_params: API调用参数
            strategy: 获取策略
            auto_save: 是否自动将API数据保存到数据库

        Returns:
            JsonResponse: 模块列表数据
        """
        if not bk_biz_id or not bk_set_id:
            return JsonResponse({
                "result": False,
                "message": "业务ID和集群ID不能为空"
            })

        # 合并筛选条件：确保按业务ID和集群ID查询
        if filter_params is None:
            filter_params = {}
        filter_params['bk_biz_id'] = bk_biz_id
        filter_params['bk_set_id'] = bk_set_id

        return self._fetch_data(
            data_type='module',
            filter_params=filter_params,
            api_caller=api_caller or self._build_api_caller('module', bk_biz_id=bk_biz_id, bk_set_id=bk_set_id),
            api_params=api_params,
            strategy=strategy,
            auto_save=auto_save
        )

    def _build_api_caller(self, data_type: str, **kwargs):
        """
        构建内置的CMDB API调用函数

        Args:
            data_type: 数据类型（biz/set/module）
            **kwargs: 动态参数（bk_biz_id, bk_set_id等）

        Returns:
            API调用函数
        """
        def caller(api_params=None):
            return self._call_cmdb_api_http(
                data_type=data_type,
                api_params=api_params or {},
                **kwargs
            )
        return caller

    def _call_cmdb_api_http(
        self,
        data_type: str,
        api_params: dict,
        **kwargs
    ) -> dict:
        """
        通过HTTP请求调用CMDB API

        Args:
            data_type: 数据类型
            api_params: API请求参数
            **kwargs: 动态参数（bk_biz_id, bk_set_id等）

        Returns:
            API响应数据
        """
        # 构建API URL
        endpoint = self.API_ENDPOINTS.get(data_type)
        if not endpoint:
            return {
                "result": False,
                "message": f"不支持的数据类型: {data_type}"
            }

        # 替换URL中的路径参数
        url = self.CMDB_BASE_URL + endpoint.format(
            supplier_account=self.CMDB_SUPPLIER_ACCOUNT,
            bk_biz_id=kwargs.get('bk_biz_id', ''),
            bk_set_id=kwargs.get('bk_set_id', '')
        )

        # 根据认证方式调用API
        if self.auth_type == "http_request":
            # 使用client调用（bk_token认证）
            return self._call_via_client(url, api_params)
        else:
            # 使用auth_header调用（bk_username认证，定时任务）
            return self._call_via_auth_header(url, api_params)

    def _call_via_client(self, url: str, api_params: dict) -> dict:
        """
        使用client调用CMDB API（HTTP请求模式，bk_token认证）

        Args:
            url: API URL
            api_params: API请求参数

        Returns:
            API响应数据
        """
        if not self.client:
            logger.error("Client未初始化")
            return {
                "result": False,
                "message": "认证信息未初始化"
            }

        try:
            # 使用client调用API（blueapps SDK会自动处理认证）
            result = self.client.cmdb.search_business(
                bk_biz_id=0,
                fields=["bk_biz_id", "bk_biz_name"]
            )

            if result.get('result', False) is False:
                error_msg = result.get('message', '未知错误')
                logger.error(f"CMDB API返回错误: {error_msg}")
                return {
                    "result": False,
                    "message": error_msg
                }

            return result

        except Exception as e:
            logger.error(f"CMDB API请求异常（client调用）: {str(e)}")
            return {
                "result": False,
                "message": f"API调用失败: {str(e)}"
            }

    def _call_via_auth_header(self, url: str, api_params: dict) -> dict:
        """
        使用auth_header调用CMDB API（定时任务模式，bk_username认证）

        Args:
            url: API URL
            api_params: API请求参数

        Returns:
            API响应数据
        """
        if not self.auth_header:
            logger.error("未配置CMDB认证请求头")
            return {
                "result": False,
                "message": "未配置CMDB认证信息"
            }

        # 构建请求头：X-Bkapi-Authorization的值是JSON字符串
        headers = {
            "X-Bkapi-Authorization": json.dumps(self.auth_header)
        }

        try:
            response = requests.post(
                url,
                headers=headers,
                data=json.dumps(api_params),
                timeout=30
            )

            if response.status_code != 200:
                error_msg = f"CMDB API调用失败: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return {
                    "result": False,
                    "message": error_msg
                }

            result = response.json()
            if result.get('result', False) is False:
                error_msg = result.get('message', '未知错误')
                logger.error(f"CMDB API返回错误: {error_msg}")
                return {
                    "result": False,
                    "message": error_msg
                }

            return result

        except requests.exceptions.RequestException as e:
            logger.error(f"CMDB API请求异常: {str(e)}")
            return {
                "result": False,
                "message": f"网络请求失败: {str(e)}"
            }

    def _fetch_data(
        self,
        data_type: str,
        filter_params: Optional[dict] = None,
        api_caller=None,
        api_params: Optional[dict] = None,
        strategy: str = CmdbFetchStrategy.CACHE_FIRST,
        auto_save: bool = True
    ) -> JsonResponse:
        """
        统一数据获取接口（内部方法）

        Args:
            data_type: 数据类型（biz/set/module）
            filter_params: 数据库查询参数
            api_caller: CMDB API调用函数
            api_params: API调用参数
            strategy: 获取策略
            auto_save: 是否自动将API数据保存到数据库

        Returns:
            JsonResponse
        """
        config = self._DATA_CONFIGS.get(data_type)
        if not config:
            return JsonResponse({
                "result": False,
                "message": f"不支持的数据类型: {data_type}"
            })

        # 策略1: 手动刷新
        if strategy == CmdbFetchStrategy.MANUAL_REFRESH:
            return self._fetch_from_api(
                config, api_caller, api_params, save_to_db=auto_save, return_data=True
            )

        # 策略2: 后台同步（定时任务）
        if strategy == CmdbFetchStrategy.BACKGROUND_SYNC:
            return self._fetch_from_api(
                config, api_caller, api_params, save_to_db=auto_save, return_data=False
            )

        # 策略3: 优先从数据库缓存获取（默认）
        if strategy == CmdbFetchStrategy.CACHE_FIRST:
            db_result = self._fetch_from_database(config, filter_params)
            if db_result is not None:
                return db_result

            # 数据库无数据，从API获取
            return self._fetch_from_api(
                config, api_caller, api_params, save_to_db=auto_save, return_data=True
            )

        return JsonResponse({
            "result": False,
            "message": f"不支持的获取策略: {strategy}"
        })

    def _fetch_from_database(
        self,
        config: dict,
        filter_params: Optional[dict]
    ) -> Optional[JsonResponse]:
        """
        从数据库获取数据

        Returns:
            JsonResponse 如果找到数据，否则返回 None
        """
        model_class = config['model']
        fields = config['fields']

        try:
            queryset = model_class.objects.filter(**(filter_params or {}))
            if queryset.exists():
                data = list(queryset.values(*fields))
                return JsonResponse({
                    "result": True,
                    "data": {
                        "count": queryset.count(),
                        "info": data
                    }
                })
        except Exception as e:
            logger.error(f"从数据库获取{config['unique_field']}数据失败: {str(e)}")

        return None

    def _fetch_from_api(
        self,
        config: dict,
        api_caller,
        api_params: Optional[dict],
        save_to_db: bool,
        return_data: bool = True
    ) -> JsonResponse:
        """
        从CMDB API获取数据

        Args:
            config: 数据配置
            api_caller: API调用函数
            api_params: API调用参数
            save_to_db: 是否保存到数据库
            return_data: 是否返回数据详情

        Returns:
            JsonResponse
        """
        if not api_caller:
            return JsonResponse({
                "result": False,
                "message": "CMDB API调用函数未提供"
            })

        try:
            # 调用CMDB API
            api_result = api_caller(**(api_params or {}))

            # 检查API返回结果
            if not api_result.get("result", False):
                return JsonResponse(api_result)

            # 提取数据列表
            data_list = api_result.get("data", {}).get("info", [])

            # 保存到数据库
            saved_count = 0
            save_message = ""
            if save_to_db and data_list:
                save_result = self._save_to_database(config, data_list)
                saved_count = save_result.get("saved_count", 0)
                save_message = save_result['message']

            # 根据策略返回不同结果
            if not return_data:
                # 后台同步：只返回同步结果
                return JsonResponse({
                    "result": True,
                    "data": {
                        "count": saved_count,
                        "message": save_message,
                        "synced": True
                    }
                })

            # 返回完整数据
            response_data = {
                "result": True,
                "data": {
                    "count": len(data_list),
                    "info": data_list
                }
            }

            # 保持CMDB原有格式
            if "data" in api_result and "info" in api_result["data"]:
                response_data = api_result

            return JsonResponse(response_data)

        except Exception as e:
            logger.error(f"从CMDB API获取数据失败: {str(e)}")
            return JsonResponse({
                "result": False,
                "message": f"CMDB API调用失败: {str(e)}"
            })

    def _save_to_database(
        self,
        config: dict,
        data_list: list
    ) -> dict:
        """
        将CMDB数据保存到数据库

        Returns:
            {"success": bool, "message": str, "saved_count": int}
        """
        model_class = config['model']
        unique_field = config['unique_field']
        defaults_map = config['defaults_map']

        try:
            with transaction.atomic():
                # 过滤有效数据
                valid_data = []
                for item in data_list:
                    required_fields = list(defaults_map.keys()) + [unique_field]
                    if all(
                        field in item and item[field] is not None
                        for field in required_fields
                    ):
                        valid_data.append(item)

                # 批量保存
                saved_count = 0
                for item in valid_data:
                    defaults = {}
                    for field, api_field in defaults_map.items():
                        if api_field in item:
                            defaults[field] = item[api_field]

                    model_class.objects.update_or_create(
                        **{unique_field: item[unique_field]},
                        defaults=defaults
                    )
                    saved_count += 1

                logger.info(f"成功保存 {saved_count} 条{unique_field}数据到数据库")

            return {
                "success": True,
                "message": f"保存 {saved_count} 条数据成功",
                "saved_count": saved_count
            }

        except Exception as e:
            logger.error(f"保存{unique_field}数据到数据库失败: {str(e)}")
            return {
                "success": False,
                "message": f"保存失败: {str(e)}",
                "saved_count": 0
            }

    def sync_biz_data(
        self,
        api_caller=None,
        api_params: Optional[dict] = None
    ) -> dict:
        """
        同步业务数据到数据库

        Args:
            api_caller: 自定义CMDB API调用函数（可选）
            api_params: API调用参数

        Returns:
            同步结果
        """
        if not api_caller:
            api_caller = self._build_api_caller('biz')
        return self._sync_data('biz', api_caller, api_params)

    def sync_set_data(
        self,
        bk_biz_id: int,
        api_caller=None,
        api_params: Optional[dict] = None
    ) -> dict:
        """
        同步集群数据到数据库

        Args:
            bk_biz_id: 业务ID（必填）
            api_caller: 自定义CMDB API调用函数（可选）
            api_params: API调用参数

        Returns:
            同步结果
        """
        if not bk_biz_id:
            return {
                "result": False,
                "message": "业务ID不能为空"
            }
        if not api_caller:
            api_caller = self._build_api_caller('set', bk_biz_id=bk_biz_id)
        return self._sync_data('set', api_caller, api_params)

    def sync_module_data(
        self,
        bk_biz_id: int,
        bk_set_id: int,
        api_caller=None,
        api_params: Optional[dict] = None
    ) -> dict:
        """
        同步模块数据到数据库

        Args:
            bk_biz_id: 业务ID（必填）
            bk_set_id: 集群ID（必填）
            api_caller: 自定义CMDB API调用函数（可选）
            api_params: API调用参数

        Returns:
            同步结果
        """
        if not bk_biz_id or not bk_set_id:
            return {
                "result": False,
                "message": "业务ID和集群ID不能为空"
            }
        if not api_caller:
            api_caller = self._build_api_caller('module', bk_biz_id=bk_biz_id, bk_set_id=bk_set_id)
        return self._sync_data('module', api_caller, api_params)

    def sync_all_data(self) -> dict:
        """
        同步所有CMDB数据到数据库（定时任务使用）

        支持两种认证方式：
        1. 定时任务模式：需要初始化时传入auth_header
        2. HTTP请求模式：需要初始化时传入request对象

        Returns:
            同步结果汇总
        """
        # 检查认证配置
        if self.auth_type == "scheduled_task" and not self.auth_header:
            return {
                "result": False,
                "message": "定时任务模式下未配置CMDB认证信息（auth_header）"
            }
        elif self.auth_type == "http_request" and not self.client:
            return {
                "result": False,
                "message": "HTTP请求模式下未获取到client"
            }

        results = {}
        all_success = True

        # 1. 同步业务数据
        biz_result = self.sync_biz_data()
        results['biz'] = biz_result
        if not biz_result['result']:
            all_success = False

        # 2. 同步每个业务的集群数据
        biz_list = self._DATA_CONFIGS['biz']['model'].objects.all()
        total_set_count = 0
        total_module_count = 0

        for biz in biz_list:
            bk_biz_id = biz.bk_biz_id
            logger.info(f"开始同步业务 {bk_biz_id} 的集群和模块数据...")

            # 同步该业务的所有集群
            set_result = self.sync_set_data(bk_biz_id)
            results.setdefault('set_details', {})[bk_biz_id] = set_result

            if set_result['result']:
                total_set_count += set_result.get('count', 0)
            else:
                all_success = False

            # 3. 同步该业务每个集群的模块数据
            set_list = self._DATA_CONFIGS['set']['model'].objects.filter(bk_biz_id=bk_biz_id)
            for bk_set in set_list:
                bk_set_id = bk_set.bk_set_id
                module_result = self.sync_module_data(bk_biz_id, bk_set_id)

                if module_result['result']:
                    total_module_count += module_result.get('count', 0)
                else:
                    all_success = False

        # 汇总结果
        results['set'] = {
            "result": all(r['result'] for r in results.get('set_details', {}).values()),
            "count": total_set_count
        }
        results['module'] = {
            "result": all_success,
            "count": total_module_count
        }

        return {
            "result": all_success,
            "message": "CMDB全量数据同步完成" if all_success else "部分同步失败",
            "data": {
                "biz_count": results['biz'].get('count', 0),
                "set_count": total_set_count,
                "module_count": total_module_count
            },
            "details": results
        }

    def _sync_data(
        self,
        data_type: str,
        api_caller,
        api_params: Optional[dict] = None
    ) -> dict:
        """
        同步数据到数据库（内部方法）

        Args:
            data_type: 数据类型
            api_caller: API调用函数
            api_params: API调用参数

        Returns:
            同步结果
        """
        config = self._DATA_CONFIGS.get(data_type)
        if not config:
            return {
                "result": False,
                "message": f"不支持的数据类型: {data_type}"
            }

        try:
            # 调用API
            api_result = api_caller(**(api_params or {}))

            if not api_result.get("result", False):
                return {
                    "result": False,
                    "message": f"CMDB API调用失败: {api_result.get('message', '未知错误')}"
                }

            # 提取数据
            data_list = api_result.get("data", {}).get("info", [])

            # 保存到数据库
            save_result = self._save_to_database(config, data_list)

            return {
                "result": save_result['success'],
                "message": save_result['message'],
                "count": len(data_list)
            }

        except Exception as e:
            logger.error(f"同步{data_type}数据失败: {str(e)}")
            return {
                "result": False,
                "message": f"同步失败: {str(e)}"
            }
