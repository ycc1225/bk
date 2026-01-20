# -*- coding: utf-8 -*-
"""
DRF 视图定义 - 使用REST API风格重构接口
"""
import json
import time
from collections import defaultdict

from django.db.models import F
from django.utils import timezone
from rest_framework import status, viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend

from blueking.component.shortcuts import get_client_by_request
from .models import BizInfo, SetInfo, ModuleInfo, BackupJob, BackupRecord, ApiRequestCount
from .serializers import (
    BizInfoSerializer, SetInfoSerializer, ModuleInfoSerializer,
    BackupJobSerializer, BackupJobListSerializer, BackupRecordSerializer,
    ApiRequestCountSerializer
)
from .constants import (
    MAX_ATTEMPTS, JOB_RESULT_ATTEMPTS_INTERVAL, JOB_BK_BIZ_ID,
    BK_JOB_HOST, WEB_SUCCESS_CODE, SEARCH_FILE_PLAN_ID, WAITING_CODE,
    SUCCESS_CODE, BACKUP_FILE_PLAN_ID, STEP_STATUS_SUCCESS
)
from .utils import DataSyncManager


class StandardResultsSetPagination(PageNumberPagination):
    """标准分页类"""
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class BizInfoViewSet(viewsets.ReadOnlyModelViewSet):
    """业务信息视图集"""
    queryset = BizInfo.objects.all()
    serializer_class = BizInfoSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['bk_biz_name']
    ordering_fields = ['id', 'bk_biz_id', 'bk_biz_name']
    ordering = ['bk_biz_id']


class SetInfoViewSet(viewsets.ReadOnlyModelViewSet):
    """集群信息视图集"""
    queryset = SetInfo.objects.all()
    serializer_class = SetInfoSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['bk_biz_id']
    search_fields = ['bk_set_name']
    ordering_fields = ['id', 'bk_set_id', 'bk_set_name']
    ordering = ['bk_set_id']


class ModuleInfoViewSet(viewsets.ReadOnlyModelViewSet):
    """模块信息视图集"""
    queryset = ModuleInfo.objects.all()
    serializer_class = ModuleInfoSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['bk_biz_id', 'bk_set_id']
    search_fields = ['bk_module_name']
    ordering_fields = ['id', 'bk_module_id', 'bk_module_name']
    ordering = ['bk_module_id']


class BackupJobViewSet(viewsets.ModelViewSet):
    """备份作业视图集"""
    queryset = BackupJob.objects.all().order_by('-id')
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'operator', 'job_instance_id']
    search_fields = ['operator', 'search_path', 'suffix']
    ordering_fields = ['id', 'created_at', 'file_count']
    
    def get_serializer_class(self):
        """根据action返回不同的序列化器"""
        if self.action == 'list':
            return BackupJobListSerializer
        if self.action == 'retrieve':
            return BackupJobSerializer
        return BackupJobSerializer
    
    def retrieve(self, request, *args, **kwargs):
        """获取备份作业详情"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        
        # 按主机分组文件记录
        records = instance.records.all()
        host_files = defaultdict(list)
        for record in records:
            host_files[record.bk_host_id].append({
                "file_path": record.bk_backup_name,
                "status": record.status
            })
        
        data = serializer.data
        data['host_files'] = dict(host_files)
        return Response({
            "result": True,
            "data": data
        })

class DataSyncAPIView(APIView):
    """数据同步API"""
    
    def get(self, request):
        """同步数据"""
        bk_biz_id = request.query_params.get('bk_biz_id')
        bk_set_id = request.query_params.get('bk_set_id')

        client = get_client_by_request(request)
        
        # 同步业务数据
        biz_sync_result = DataSyncManager.sync_data(client, 'biz')
        if not biz_sync_result.get("result"):
            return Response(biz_sync_result)
        
        if bk_biz_id:
            # 同步集群数据
            set_sync_result = DataSyncManager.sync_data(client, 'set', bk_biz_id)
            if not set_sync_result.get("result"):
                return Response(set_sync_result)
            
            if bk_set_id:
                # 同步模块数据
                module_sync_result = DataSyncManager.sync_data(client, 'module', bk_biz_id, bk_set_id)
                if not module_sync_result.get("result"):
                    return Response(module_sync_result)
        else:
            from .tasks import sync_data
            sync_data.delay()
        
        return Response({
            "result": True,
            "message": "同步成功"
        })


class HostListAPIView(APIView):
    """主机列表API"""
    
    def get(self, request):
        """查询主机列表"""
        client = get_client_by_request(request)

        # 获取分页参数
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 10))
        start = (page - 1) * page_size

        # 构造请求参数
        kwargs = {
            "bk_biz_id": request.query_params.get('bk_biz_id'),
            "page": {
                "start": start,
                "limit": page_size,
            },
            "fields": [
                "bk_host_id",
                "bk_host_innerip",
                "operator",
                "bk_bak_operator",
            ],
        }

        # 添加可选参数
        if request.query_params.get("bk_set_id"):
            kwargs["bk_set_ids"] = [int(request.query_params.get("bk_set_id"))]

        if request.query_params.get("bk_module_id"):
            kwargs["bk_module_ids"] = [int(request.query_params.get("bk_module_id"))]

        # 构造查询规则
        rules = []
        if request.query_params.get("operator"):
            rules.append({
                "field": "operator",
                "operator": "contains",
                "value": request.query_params.get("operator")
            })
        if request.query_params.get("bk_host_id"):
            rules.append({
                "field": "bk_host_id",
                "operator": "equal",
                "value": int(request.query_params.get("bk_host_id"))
            })
        if request.query_params.get("bk_host_innerip"):
            rules.append({
                "field": "bk_host_innerip",
                "operator": "contains",
                "value": request.query_params.get("bk_host_innerip")
            })

        if rules:
            kwargs["host_property_filter"] = {
                "condition": "AND",
                "rules": rules
            }

        result = client.cc.list_biz_hosts(kwargs)

        # 添加分页信息
        if result.get("result"):
            data = result.get("data", {})
            total_count = data.get("count", 0)
            data["pagination"] = {
                "current": page,
                "count": total_count,
                "limit": page_size,
            }
            result["data"] = data

        return Response(result)


class HostDetailAPIView(APIView):
    """主机详情API"""
    
    def get(self, request):
        """查询主机详情"""
        client = get_client_by_request(request)

        kwargs = {
            "bk_host_id": request.query_params.get('bk_host_id'),
        }

        result = client.cc.get_host_base_info(kwargs)
        return Response(result)


class SearchFileAPIView(APIView):
    """搜索文件API"""
    
    def get(self, request):
        """根据主机IP、文件目录和文件后缀查询文件"""
        host_id_list_str = request.query_params.get("host_id_list")
        host_id_list = [int(bk_host_id) for bk_host_id in host_id_list_str.split(",")]
        
        kwargs = {
            "bk_scope_type": "biz",
            "bk_scope_id": JOB_BK_BIZ_ID,
            "job_plan_id": SEARCH_FILE_PLAN_ID,
            "global_var_list": [
                {
                    "name": "host_list",
                    "server": {
                        "host_id_list": host_id_list,
                    },
                },
                {
                    "name": "search_path",
                    "value": request.query_params.get("search_path"),
                },
                {
                    "name": "suffix",
                    "value": request.query_params.get("suffix"),
                },
            ],
        }

        client = get_client_by_request(request)
        job_instance_id = client.jobv3.execute_job_plan(**kwargs).get("data").get("job_instance_id")

        kwargs = {
            "bk_scope_type": "biz",
            "bk_scope_id": JOB_BK_BIZ_ID,
            "job_instance_id": job_instance_id,
        }

        # 轮询执行状态
        attempts = 0
        while attempts < MAX_ATTEMPTS:
            step_instance_list = client.jobv3.get_job_instance_status(**kwargs).get("data").get("step_instance_list")
            if step_instance_list[0].get("status") == WAITING_CODE:
                time.sleep(JOB_RESULT_ATTEMPTS_INTERVAL)
            elif step_instance_list[0].get("status") != SUCCESS_CODE:
                return Response({
                    "result": False,
                    "code": WEB_SUCCESS_CODE,
                    "message": "search failed",
                })
            elif step_instance_list[0].get("status") == SUCCESS_CODE:
                break
            attempts += 1

        step_instance_id = step_instance_list[0].get("step_instance_id")

        # 获取执行日志
        log_list = []
        for bk_host_id in host_id_list:
            data = {
                "bk_scope_type": "biz",
                "bk_scope_id": JOB_BK_BIZ_ID,
                "job_instance_id": job_instance_id,
                "step_instance_id": step_instance_id,
                "bk_host_id": bk_host_id,
            }

            response = client.jobv3.get_job_instance_ip_log(**data).get("data")
            step_res = response.get("log_content")
            json_step_res = json.loads(step_res)
            json_step_res["bk_host_id"] = response.get("bk_host_id")
            log_list.append(json_step_res)

        return Response({
            "result": True,
            "code": WEB_SUCCESS_CODE,
            "data": log_list,
        })


class BackupFileAPIView(APIView):
    """备份文件API"""
    
    def get(self, request):
        """备份文件到指定目录"""
        host_id_list_str = request.query_params.get("host_id_list")
        host_id_list = [int(bk_host_id) for bk_host_id in host_id_list_str.split(",")]
        search_path = request.query_params.get("search_path")
        suffix = request.query_params.get("suffix")
        backup_path = request.query_params.get("backup_path")

        kwargs = {
            "bk_scope_type": "biz",
            "bk_scope_id": JOB_BK_BIZ_ID,
            "job_plan_id": BACKUP_FILE_PLAN_ID,
            "global_var_list": [
                {
                    "name": "host_list",
                    "server": {
                        "host_id_list": host_id_list,
                    },
                },
                {
                    "name": "search_path",
                    "value": search_path
                },
                {
                    "name": "suffix",
                    "value": suffix
                },
                {
                    "name": "backup_path",
                    "value": backup_path,
                },
            ],
        }

        client = get_client_by_request(request)
        job_instance_id = client.jobv3.execute_job_plan(**kwargs).get("data").get("job_instance_id")

        kwargs = {
            "bk_scope_type": "biz",
            "bk_scope_id": JOB_BK_BIZ_ID,
            "job_instance_id": job_instance_id,
        }

        # 轮询执行状态
        attempts = 0
        while attempts < MAX_ATTEMPTS:
            step_instance_list = client.jobv3.get_job_instance_status(**kwargs).get("data").get("step_instance_list")
            if step_instance_list[0].get("status") == WAITING_CODE:
                time.sleep(JOB_RESULT_ATTEMPTS_INTERVAL)
            elif step_instance_list[0].get("status") != SUCCESS_CODE:
                return Response({
                    "result": False,
                    "code": WEB_SUCCESS_CODE,
                    "message": "backup failed",
                })
            elif step_instance_list[0].get("status") == SUCCESS_CODE:
                break
            attempts += 1

        step_instance_id = step_instance_list[0].get("step_instance_id")

        # 生成作业链接
        bk_job_link = "{}/biz/{}/execute/task/{}".format(
            BK_JOB_HOST,
            JOB_BK_BIZ_ID,
            job_instance_id,
        )

        # 创建备份作业记录
        backup_job = BackupJob.objects.create(
            job_instance_id=str(job_instance_id),
            operator=request.user.username,
            search_path=search_path,
            suffix=suffix,
            backup_path=backup_path,
            bk_job_link=bk_job_link,
            status="pending",
            host_count=len(host_id_list),
            file_count=0,
        )

        # 创建备份记录
        total_files = 0
        for bk_host_id in host_id_list:
            data = {
                "bk_scope_type": "biz",
                "bk_scope_id": JOB_BK_BIZ_ID,
                "job_instance_id": job_instance_id,
                "step_instance_id": step_instance_id,
                "bk_host_id": bk_host_id,
            }

            response = client.jobv3.get_job_instance_ip_log(**data).get("data")
            step_res = response.get("log_content")
            json_step_res = json.loads(step_res)

            for step_res in json_step_res:
                BackupRecord.objects.create(
                    backup_job=backup_job,
                    bk_host_id=bk_host_id,
                    status="success",
                    bk_backup_name=step_res.get("bk_backup_name", "unknown"),
                )
                total_files += 1

        backup_job.file_count = total_files
        backup_job.status = "success"
        backup_job.save()

        serializer = BackupJobSerializer(backup_job)
        return Response({
            "result": True,
            "data": serializer.data,
            "code": WEB_SUCCESS_CODE,
        })

class BackupJobCallbackAPIView(APIView):
    """备份作业回调API"""
    def post(self, request):
        """回调成功返回200"""
        print(request.data)
        return Response(status=status.HTTP_200_OK)