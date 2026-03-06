import logging

from celery import shared_task

from home_application.services.basic_sync import BasicCMDBSyncService
from home_application.services.topo_sync import TopoCMDBSyncService
from home_application.views.metrics import celery_tasks_total, cmdb_sync_last_success

logger = logging.getLogger(__name__)


@shared_task(queue="sync")
def basic_sync_data_task(token=None):
    try:
        BasicCMDBSyncService(token).sync()
        celery_tasks_total.labels(task_name="basic_sync_data", status="success").inc()
        cmdb_sync_last_success.labels(sync_type="basic").set_to_current_time()
    except Exception as e:
        celery_tasks_total.labels(task_name="basic_sync_data", status="failure").inc()
        logger.error(f"[指标埋点] basic_sync_data_task 失败: {e}")
        raise


@shared_task(queue="sync")
def topo_sync_data_task(token):
    try:
        TopoCMDBSyncService(token).sync()
        celery_tasks_total.labels(task_name="topo_sync_data", status="success").inc()
        cmdb_sync_last_success.labels(sync_type="topo").set_to_current_time()
    except Exception as e:
        celery_tasks_total.labels(task_name="topo_sync_data", status="failure").inc()
        logger.error(f"[指标埋点] topo_sync_data_task 失败: {e}")
        raise
