# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
Edition) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import json
import time

from django.http import JsonResponse
from django.shortcuts import render

from blueking.component.shortcuts import get_client_by_request
from home_application.constants import MAX_ATTEMPTS, JOB_RESULT_ATTEMPTS_INTERVAL, JOB_BK_BIZ_ID, BK_JOB_HOST, \
    WEB_SUCCESS_CODE, SEARCH_FILE_PLAN_ID, WAITING_CODE, SUCCESS_CODE, BACKUP_FILE_PLAN_ID
from home_application.models import BackupRecord
from home_application.utils import DataSyncManager


# 开发框架中通过中间件默认是需要登录态的，如有不需要登录的，可添加装饰器login_exempt
# 装饰器引入 from blueapps.account.decorators import login_exempt
def home(request):
    """
    首页
    """
    return render(request, "home_application/index_home.html")


def dev_guide(request):
    """
    开发指引
    """
    return render(request, "home_application/dev_guide.html")


def contact(request):
    """
    联系页
    """
    return render(request, "home_application/contact.html")


# 开发框架中通过中间件默认是需要登录态的，如有不需要登录的，可添加装饰器login_exempt
# 装饰器引入 from blueapps.account.decorators import login_exempt
def home(request):
    """
    首页
    """
    return render(request, "home_application/index_home.html")


def dev_guide(request):
    """
    开发指引
    """
    return render(request, "home_application/dev_guide.html")


def contact(request):
    """
    联系页
    """
    return render(request, "home_application/contact.html")


def get_bizs_list(request):
    """
    获取业务列表 - 使用统一工具类
    """
    return DataSyncManager.get_bizs_data(request)


def get_sets_list(request):
    """
    根据业务ID，查询业务下的集群列表 - 使用统一工具类
    """
    bk_biz_id = request.GET.get('bk_biz_id')
    if not bk_biz_id:
        return JsonResponse({"result": False, "message": "缺少业务ID参数"})

    return DataSyncManager.get_sets_data(request, int(bk_biz_id))


def get_modules_list(request):
    """
    根据业务ID和集群ID，查询对应的模块列表 - 使用统一工具类
    """
    bk_biz_id = request.GET.get('bk_biz_id')
    bk_set_id = request.GET.get("bk_set_id")

    if not bk_biz_id or not bk_set_id:
        return JsonResponse({"result": False, "message": "缺少业务ID或集群ID参数"})

    return DataSyncManager.get_modules_data(request, int(bk_biz_id), int(bk_set_id))

def sync(request):
    bk_biz_id = request.GET.get('bk_biz_id')
    bk_set_id = request.GET.get('bk_set_id')

    # 根据提供的参数同步相应的数据
    # 同步业务数据
    biz_sync_result = DataSyncManager.sync_data(request, 'biz')
    if not biz_sync_result.get("result"):
        return biz_sync_result
    if bk_biz_id:
        # 同步集群数据
        set_sync_result = DataSyncManager.sync_data(request, 'set', bk_biz_id)
        if not set_sync_result.get("result"):
            return set_sync_result
        if bk_set_id:
            # 同步模块数据
            module_sync_result = DataSyncManager.sync_data(request, 'module', bk_biz_id, bk_set_id)
            if not module_sync_result.get("result"):
                return module_sync_result
    else:
        all_sync_result = DataSyncManager.sync_data(request, 'all')
        if not all_sync_result.get("result"):
            return all_sync_result
    return JsonResponse({"result": True, "message": "同步成功","data":{}})


def get_hosts_list(request):
    """
    根据传递的查询条件，包括但不限于（业务ID、集群ID、模块ID、主机ID、主机维护人）
    查询主机列表
    """
    client = get_client_by_request(request)

    # 获取分页参数，设置默认值
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 10))
    start = (page - 1) * page_size

    # 构造请求函数
    kwargs = {
        "bk_biz_id": request.GET.get('bk_biz_id'),
        "page": {
            "start": start,
            "limit": page_size,
        },
        "fields": [
            "bk_host_id",  # 主机ID
            "bk_host_innerip",  # 内网IP
            "operator",  # 主要维护人
            "bk_bak_operator",  # 备份维护人
        ],
    }

    # 添加可选参数，如集群ID、模块ID、主机ID...
    if request.GET.get("bk_set_id"):
        kwargs["bk_set_ids"] = [int(request.GET.get("bk_set_id"))]

    if request.GET.get("bk_module_id"):
        kwargs["bk_module_ids"] = [int(request.GET.get("bk_module_id"))]

    rules = []  # 额外的查询参数，配置查询规则，参数参考API文档
    if request.GET.get("operator"):
        rules.append({
            "field": "operator",
            "operator": "contains",
            "value": request.GET.get("operator")
        })
    if request.GET.get("bk_host_id"):
        rules.append({
            "field": "bk_host_id",
            "operator": "equal",
            "value": int(request.GET.get("bk_host_id"))
        })
    if request.GET.get("bk_host_innerip"):
        rules.append({
            "field": "bk_host_innerip",
            "operator": "contains",
            "value": request.GET.get("bk_host_innerip")
        })
    # TODO: 添加额外的查询参数

    #  将额外的查询添加进过滤器中
    if rules:
        kwargs["host_property_filter"] = {
            "condition": "AND",
            "rules": rules
        }

    print(kwargs)

    result = client.cc.list_biz_hosts(kwargs)

    # 在返回结果中添加分页信息
    if result.get("result"):
        data = result.get("data", {})
        # 计算总页数
        total_count = data.get("count", 0)

        # 添加分页信息到返回数据
        data["pagination"] = {
            "current": page,
            "count": total_count,
            "limit": page_size,
        }
        result["data"] = data

    return JsonResponse(result)


def get_host_detail(request):
    """
    根据主机ID，查询主机详情信息
    """
    client = get_client_by_request(request)

    kwargs = {
        "bk_host_id": request.GET.get("bk_host_id"),
    }

    result = client.cc.get_host_base_info(kwargs)
    return JsonResponse(result)


def search_file(request):
    """
    根据主机IP、文件目录和文件后缀，查询符合条件的主机文件
    """

    # 注意：先在constants.py中替换SEARCH_FILE_PLAN_ID为你自己在作业平台上新建的方案的ID
    host_id_list_str = request.GET.get("host_id_list")
    host_id_list = [int(bk_host_id) for bk_host_id in host_id_list_str.split(",")]
    kwargs = {
        "bk_scope_type": "biz",
        "bk_scope_id": JOB_BK_BIZ_ID,
        "job_plan_id": SEARCH_FILE_PLAN_ID,
        # TODO 修改为你创建的执行方案的全局变量
        "global_var_list": [
            {
                "name": "host_list",
                "server": {
                    "host_id_list": host_id_list,
                },
            },
            {
                "name": "search_path",
                "value": request.GET.get("search_path"),
            },
            {
                "name": "suffix",
                "value": request.GET.get("suffix"),
            },
        ],
    }

    # 调用执行方案
    client = get_client_by_request(request)
    job_instance_id = client.jobv3.execute_job_plan(**kwargs).get("data").get("job_instance_id")

    kwargs = {
        "bk_scope_type": "biz",
        "bk_scope_id": JOB_BK_BIZ_ID,
        "job_instance_id": job_instance_id,
    }

    attempts = 0
    while attempts < MAX_ATTEMPTS:
        # 获取执行方案执行状态
        step_instance_list = client.jobv3.get_job_instance_status(**kwargs).get("data").get("step_instance_list")
        if step_instance_list[0].get("status") == WAITING_CODE:
            time.sleep(JOB_RESULT_ATTEMPTS_INTERVAL)
        elif step_instance_list[0].get("status") != SUCCESS_CODE:
            res_data = {
                "result": False,
                "code": WEB_SUCCESS_CODE,
                "message": "search failed",
            }
            return JsonResponse(res_data)
        elif step_instance_list[0].get("status") == SUCCESS_CODE:
            break
        attempts += 1

    step_instance_id = step_instance_list[0].get("step_instance_id")

    log_list = []
    for bk_host_id in host_id_list:
        data = {
            "bk_scope_type": "biz",
            "bk_scope_id": JOB_BK_BIZ_ID,
            "job_instance_id": job_instance_id,
            "step_instance_id": step_instance_id,
            "bk_host_id": bk_host_id,
        }

        # 查询执行日志
        response = client.jobv3.get_job_instance_ip_log(**data).get("data")
        step_res = response.get("log_content")
        json_step_res = json.loads(step_res)

        json_step_res["bk_host_id"] = response.get("bk_host_id")
        log_list.append(json_step_res)

    res_data = {
        "result": True,
        "code": WEB_SUCCESS_CODE,
        "data": log_list,
    }
    return JsonResponse(res_data)


def backup_file(request):
    """
    根据主机IP、文件目录和文件后缀，备份符合条件的主机文件到指定目录
    """

    # 注意：先在constants.py中替换BACKUP_FILE_PLAN_ID为你自己在作业平台上新建的方案的ID
    host_id_list_str = request.GET.get("host_id_list")
    host_id_list = [int(bk_host_id) for bk_host_id in host_id_list_str.split(",")]
    search_path = request.GET.get("search_path")
    suffix = request.GET.get("suffix")
    kwargs = {
        "bk_scope_type": "biz",
        "bk_scope_id": JOB_BK_BIZ_ID,
        "job_plan_id": BACKUP_FILE_PLAN_ID,
        # TODO 修改为你创建的执行方案的全局变量
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
                "value": request.GET.get("backup_path"),
            },
        ],
    }

    # 调用执行方案
    client = get_client_by_request(request)
    job_instance_id = client.jobv3.execute_job_plan(**kwargs).get("data").get("job_instance_id")

    kwargs = {
        "bk_scope_type": "biz",
        "bk_scope_id": JOB_BK_BIZ_ID,
        "job_instance_id": job_instance_id,
    }
    attempts = 0
    while attempts < MAX_ATTEMPTS:
        # 获取执行方案执行状态
        step_instance_list = client.jobv3.get_job_instance_status(**kwargs).get("data").get("step_instance_list")
        if step_instance_list[0].get("status") == WAITING_CODE:
            time.sleep(JOB_RESULT_ATTEMPTS_INTERVAL)
        elif step_instance_list[0].get("status") != SUCCESS_CODE:
            res_data = {
                "result": False,
                "code": WEB_SUCCESS_CODE,
                "message": "backup failed",
            }
            return JsonResponse(res_data)
        elif step_instance_list[0].get("status") == SUCCESS_CODE:
            break
        attempts += 1

    step_instance_id = step_instance_list[0].get("step_instance_id")

    for bk_host_id in host_id_list:
        data = {
            "bk_scope_type": "biz",
            "bk_scope_id": JOB_BK_BIZ_ID,
            "job_instance_id": job_instance_id,
            "step_instance_id": step_instance_id,
            "bk_host_id": bk_host_id,
        }

        # 查询执行日志
        response = client.jobv3.get_job_instance_ip_log(**data).get("data")
        step_res = response.get("log_content")
        json_step_res = json.loads(step_res)

        for step_res in json_step_res:
            # 创建备份记录
            step_res["bk_host_id"] = bk_host_id
            step_res["bk_file_dir"] = search_path
            step_res["bk_file_suffix"] = suffix
            step_res["bk_file_operator"] = request.user.username
            step_res["bk_job_link"] = "{}/biz/{}/execute/task/{}".format(
                BK_JOB_HOST,
                JOB_BK_BIZ_ID,
                job_instance_id,
            )
            BackupRecord.objects.create(**step_res)

    res_data = {
        "result": True,
        "data": "success",
        "code": WEB_SUCCESS_CODE,
    }
    return JsonResponse(res_data)

def get_backup_record(request):
    """
    查询备份记录
    """
    res_data = {
        "result": True,
        "data": list(BackupRecord.objects.all().order_by("-id").values()),
        "code": WEB_SUCCESS_CODE,
    }
    return JsonResponse(res_data)

