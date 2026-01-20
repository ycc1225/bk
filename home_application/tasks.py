# -*- coding: utf-8 -*-
"""
Celery 异步任务定义
"""
import json
import logging
import os
import time

from celery import shared_task

from home_application.models import ApiRequestCount, BackupJob, BackupRecord

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
    from home_application.cmdb_repository import CmdbRepository

    try:
        # 构建认证信息
        auth_header = {
            "bk_username": "25zhujiao1",
            "bk_app_code": os.getenv("BKPAAS_APP_ID"),
            "bk_app_secret": os.getenv("BKPAAS_APP_SECRET"),
        }

        # 使用CmdbRepository同步数据（定时任务模式）
        cmdb_repo = CmdbRepository(auth=auth_header)
        result = cmdb_repo.sync_all_data()

        if result['result']:
            logger.info(
                f"成功同步数据: 业务{result['data']['biz_count']}个, "
                f"集群{result['data']['set_count']}个, "
                f"模块{result['data']['module_count']}个"
            )
        else:
            logger.error(f"同步数据失败: {result['message']}")
    except Exception as e:
        logger.error(f"异步同步数据失败: {str(e)}")
        pass


@shared_task(bind=True, max_retries=3)
def process_backup_job_task(self, job_instance_id, bk_token, operator, host_id_list, search_path, suffix, backup_path):
    """
    异步处理备份作业：轮询作业状态，完成后获取日志并创建备份记录

    Args:
        job_instance_id (str): 作业实例ID
        bk_token (str): 用户认证 token
        operator (str): 操作者（仅用于记录）
        host_id_list (list): 主机ID列表
        search_path (str): 搜索路径
        suffix (str): 文件后缀
        backup_path (str): 备份路径

    Returns:
        dict: 处理结果
    """
    from home_application.constants import (
        JOB_BK_BIZ_ID, WAITING_CODE, SUCCESS_CODE,
        MAX_ATTEMPTS, JOB_RESULT_ATTEMPTS_INTERVAL
    )
    from blueking.component import client as component_client
    from blueking.component import conf

    # 使用 bk_token 创建 client
    client = component_client.ComponentClient(
        app_code=conf.APP_CODE,
        app_secret=conf.SECRET_KEY,
        common_args={"bk_token": bk_token}
    )
    
    logger.info(f"开始异步处理备份作业: job_instance_id={job_instance_id}, operator={operator}")
    
    try:
        # 查询备份作业记录
        backup_job = BackupJob.objects.get(job_instance_id=str(job_instance_id))
    except BackupJob.DoesNotExist:
        logger.error(f"备份作业不存在: job_instance_id={job_instance_id}")
        return {
            "result": False,
            "message": f"备份作业不存在: {job_instance_id}"
        }

    # 如果作业已经处理完成，直接返回
    if backup_job.status in ["success", "failed"]:
        logger.info(f"备份作业已处理完成: job_instance_id={job_instance_id}, status={backup_job.status}")
        return {
            "result": True,
            "message": f"作业已处理，状态: {backup_job.status}"
        }

    # 1. 轮询作业执行状态
    attempts = 0
    step_instance_id = None

    logger.info(f"开始轮询作业状态: job_instance_id={job_instance_id}")

    while attempts < MAX_ATTEMPTS:
        try:
            kwargs = {
                "bk_scope_type": "biz",
                "bk_scope_id": JOB_BK_BIZ_ID,
                "job_instance_id": job_instance_id,
            }

            # 获取作业状态
            response = client.jobv3.get_job_instance_status(**kwargs)
            step_instance_list = response.get("data", {}).get("step_instance_list", [])

            if not step_instance_list:
                logger.warning(f"作业状态返回空: job_instance_id={job_instance_id}, attempt={attempts + 1}")
                time.sleep(JOB_RESULT_ATTEMPTS_INTERVAL)
                attempts += 1
                continue

            step_status = step_instance_list[0].get("status")

            if step_status == WAITING_CODE:
                time.sleep(JOB_RESULT_ATTEMPTS_INTERVAL)
                attempts += 1
            elif step_status != SUCCESS_CODE:
                logger.error(f"作业执行失败: job_instance_id={job_instance_id}, status={step_status}")
                backup_job.status = "failed"
                backup_job.save()
                return None
            else:
                step_instance_id = step_instance_list[0].get("step_instance_id")
        except Exception as e:
            logger.error(f"查询作业状态异常: job_instance_id={job_instance_id}, error={str(e)}")
            time.sleep(JOB_RESULT_ATTEMPTS_INTERVAL)
            attempts += 1
            continue

    if attempts >= MAX_ATTEMPTS:
        # 超过最大轮询次数，标记为处理中（可能回调会更新状态）
        logger.warning(f"作业轮询超时: job_instance_id={job_instance_id}")
        backup_job.status = "processing"
        backup_job.save()
        return None

    # 2. 获取各主机的执行日志
    logger.info(f"开始获取主机日志: job_instance_id={job_instance_id}, host_count={len(host_id_list)}")

    total_files = 0
    success_hosts = 0
    failed_hosts = 0

    for bk_host_id in host_id_list:
        try:
            data = {
                "bk_scope_type": "biz",
                "bk_scope_id": JOB_BK_BIZ_ID,
                "job_instance_id": job_instance_id,
                "step_instance_id": step_instance_id,
                "bk_host_id": bk_host_id,
            }

            # 获取主机日志
            response = client.jobv3.get_job_instance_ip_log(**data)
            log_data = response.get("data", {})
            log_content = log_data.get("log_content", "")

            if not log_content:
                logger.warning(f"主机日志为空: job_instance_id={job_instance_id}, bk_host_id={bk_host_id}")
                failed_hosts += 1
                continue

            # 解析日志内容
            try:
                json_step_res = json.loads(log_content)
            except json.JSONDecodeError:
                logger.error(f"日志解析失败: job_instance_id={job_instance_id}, bk_host_id={bk_host_id}")
                failed_hosts += 1
                continue

            # 创建备份记录
            for step_res in json_step_res:
                BackupRecord.objects.create(
                    backup_job=backup_job,
                    bk_host_id=bk_host_id,
                    status="success",
                    bk_backup_name=step_res.get("bk_backup_name", "unknown"),
                )
                total_files += 1

            success_hosts += 1
            logger.info(f"主机日志处理成功: job_instance_id={job_instance_id}, bk_host_id={bk_host_id}, files={len(json_step_res)}")

        except Exception as e:
            logger.error(f"处理主机日志异常: job_instance_id={job_instance_id}, bk_host_id={bk_host_id}, error={str(e)}")
            failed_hosts += 1
            continue

    # 3. 更新备份作业状态
    backup_job.file_count = total_files

    if failed_hosts == 0:
        # 所有主机都成功
        backup_job.status = "success"
    elif success_hosts == 0:
        # 所有主机都失败
        backup_job.status = "failed"
    else:
        # 部分主机成功
        backup_job.status = "partial"

    backup_job.save()
    
    logger.info(
        f"备份作业处理完成: job_instance_id={job_instance_id}, "
        f"status={backup_job.status}, total_files={total_files}, "
        f"success_hosts={success_hosts}, failed_hosts={failed_hosts}"
    )
    return None