# -*- coding: utf-8 -*-
"""
DRF 视图定义 - 使用REST API风格重构接口
"""
import json
import logging
import time
from collections import defaultdict

from blueapps.account.decorators import login_exempt
from django.urls import path, reverse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

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
from .cmdb_repository import CmdbRepository, CmdbFetchStrategy

logger = logging.getLogger(__name__)


# ============ 业务、集群、模块数据API ============


class BizInfoAPIView(APIView):
    """业务信息API"""
    def get(self, request):
        # 初始化CmdbRepository（HTTP请求模式，通过request获取认证信息）
        cmdb_repo = CmdbRepository(request=request)

        # 获取业务列表（优先从缓存获取）
        return cmdb_repo.get_biz_list()


class SetInfoAPIView(APIView):
    """
    集群信息API

    GET参数：
        bk_biz_id (int, 必填): 业务ID
    """
    def get(self, request):
        bk_biz_id = request.query_params.get('bk_biz_id')
        if not bk_biz_id:
            return Response({"result": False, "message": "bk_biz_id参数必填"})

        # 初始化CmdbRepository（HTTP请求模式，通过request获取认证信息）
        cmdb_repo = CmdbRepository(request=request)

        # 获取集群列表（优先从缓存获取）
        return cmdb_repo.get_set_list(bk_biz_id=int(bk_biz_id))


class ModuleInfoAPIView(APIView):
    """
    模块信息API

    GET参数：
        bk_biz_id (int, 必填): 业务ID
        bk_set_id (int, 必填): 集群ID
    """
    def get(self, request):
        bk_biz_id = request.query_params.get('bk_biz_id')
        bk_set_id = request.query_params.get('bk_set_id')
        if not bk_biz_id or not bk_set_id:
            return Response({"result": False, "message": "bk_biz_id和bk_set_id参数必填"})

        # 初始化CmdbRepository（HTTP请求模式，通过request获取认证信息）
        cmdb_repo = CmdbRepository(request=request)

        # 获取模块列表（优先从缓存获取）
        return cmdb_repo.get_module_list(bk_biz_id=int(bk_biz_id), bk_set_id=int(bk_set_id))


# ============ 备份作业API ============

class BackupJobListAPIView(APIView):
    """备份作业列表API"""
    
    def get(self, request):
        """获取备份作业列表"""
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 10))
        start = (page - 1) * page_size

        total_count = BackupJob.objects.count()
        jobs = BackupJob.objects.all()[start:start + page_size]

        res_data = {
            "result": True,
            "data": list(jobs.values()),
            "pagination": {
                "count": total_count,
                "current": page,
                "page_size": page_size,
            }
        }
        return Response(res_data)


class BackupJobDetailAPIView(APIView):
    """备份作业详情API"""
    
    def get(self, request, pk):
        """获取备份作业详情"""
        job_id = pk  # 使用URL参数中的pk作为job_id
        
        job = BackupJob.objects.get(id=job_id)
        records = job.records.all()

        # 按主机分组
        host_files = defaultdict(list)
        for record in records:
            host_files[record.bk_host_id].append({
                "file_path": record.bk_backup_name,
                "status": record.status
            })

        res_data = {
            "result": True,
            "data": {
                "job": {
                    "id": job.id,
                    "job_instance_id": job.job_instance_id,
                    "operator": job.operator,
                    "search_path": job.search_path,
                    "suffix": job.suffix,
                    "backup_path": job.backup_path,
                    "bk_job_link": job.bk_job_link,
                    "status": job.status,
                    "host_count": job.host_count,
                    "file_count": job.file_count,
                    "created_at": job.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                },
                "host_files": dict(host_files)
            }
        }
        return Response(res_data)


# ============ 数据同步API ============

class DataSyncAPIView(APIView):
    """数据同步API"""
    
    def post(self, request):
        """执行数据同步"""
        try:
            result = DataSyncManager.sync_all_data(request)
            return Response(result)
        except Exception as e:
            return Response({
                "result": False,
                "message": f"数据同步失败: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============ 主机相关API ============

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


# ============ 文件操作API ============

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
    """
    备份文件API
    
    GET参数：
        host_id_list (str, 必填): 主机ID列表，逗号分隔
        search_path (str, 必填): 搜索路径
        suffix (str, 必填): 文件后缀
        backup_path (str, 必填): 备份路径
    
    返回：
        job_instance_id: 作业实例ID，可用于查询作业状态
    """
    
    def get(self, request):
        """备份文件到指定目录（异步处理）"""
        host_id_list_str = request.query_params.get("host_id_list")
        host_id_list = [int(bk_host_id) for bk_host_id in host_id_list_str.split(",")]
        search_path = request.query_params.get("search_path")
        suffix = request.query_params.get("suffix")
        backup_path = request.query_params.get("backup_path")

        # 执行作业计划
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
            "callback_url": "https://apps1.ce.bktencent.com/prod--default--leve4-bkvision/api/backup-callback/"
        }

        try:
            client = get_client_by_request(request)
            job_response = client.jobv3.execute_job_plan(**kwargs)
            job_instance_id = job_response.get("data", {}).get("job_instance_id")
            
            if not job_instance_id:
                return Response({
                    "result": False,
                    "code": WEB_SUCCESS_CODE,
                    "message": "执行作业失败，未返回job_instance_id",
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            logger.error(f"执行作业异常: {str(e)}")
            return Response({
                "result": False,
                "code": WEB_SUCCESS_CODE,
                "message": f"执行作业失败: {str(e)}",
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 生成作业链接
        bk_job_link = "{}/biz/{}/execute/task/{}".format(
            BK_JOB_HOST,
            JOB_BK_BIZ_ID,
            job_instance_id,
        )

        # 创建备份作业记录（状态为pending）
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

        # 从 request 中提取 bk_token
        bk_token = request.COOKIES.get("bk_token", "")

        # 启动异步任务处理作业（传递 bk_token 而非 bk_username）
        from home_application.tasks import process_backup_job_task
        process_backup_job_task.delay(
            job_instance_id=str(job_instance_id),
            bk_token=bk_token,  # 使用 bk_token
            operator=request.user.username,  # 只用于记录操作者
            host_id_list=host_id_list,
            search_path=search_path,
            suffix=suffix,
            backup_path=backup_path,
        )

        # 立即返回，不阻塞等待作业完成
        return Response({
            "result": True,
            "data": "备份作业已提交，正在后台处理",
            "code": WEB_SUCCESS_CODE,
        })

class BackupJobCallbackAPIView(APIView):
    """
    备份作业回调API
    
    JOB平台会在作业完成时调用此接口，更新作业状态
    """
    
    def post(self, request):
        """处理JOB平台的回调通知"""
        data = request.data

        # 兼容"JSON 被当成 key"的情况
        if isinstance(data, dict) and len(data) == 1:
            key = next(iter(data.keys()))
            try:
                data = json.loads(key)
            except json.JSONDecodeError:
                logger.warning(f"无效的回调数据格式: {key}")
                return Response(
                    {"error": "invalid callback payload"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        job_instance_id = data.get("job_instance_id")
        status_code = data.get("status")
        step_instances = data.get("step_instances", [])
        step_status = step_instances[0].get("status")


        if not job_instance_id or not status_code:
            logger.warning(f"回调缺少必要参数: job_instance_id={job_instance_id}, status={status_code}")
            return Response(
                {"error": "missing required parameters"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            backup_job = BackupJob.objects.get(job_instance_id=str(job_instance_id))
            
            # 只更新未完成的作业
            if backup_job.status == "pending" or backup_job.status == "processing":
                new_status = "success" if (int(status_code) == SUCCESS_CODE and step_status == SUCCESS_CODE) else "failed"
                backup_job.status = new_status
                backup_job.save()
                
                logger.info(
                    f"回调更新作业状态: job_instance_id={job_instance_id}, "
                    f"old_status={new_status}, new_status={new_status}"
                )
            else:
                logger.info(
                    f"作业状态已处理，跳过回调更新: job_instance_id={job_instance_id}, "
                    f"current_status={backup_job.status}"
                )
            
            return Response({"result": True, "message": "callback received"})
            
        except BackupJob.DoesNotExist:
            logger.error(f"备份作业不存在: job_instance_id={job_instance_id}")
            return Response(
                {"error": "backup job not found"},
                status=status.HTTP_404_NOT_FOUND
            )