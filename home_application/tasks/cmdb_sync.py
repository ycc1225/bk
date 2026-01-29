from celery import shared_task

from home_application.services.basic_sync import BasicCMDBSyncService
from home_application.services.topo_sync import TopoCMDBSyncService


@shared_task
def basic_sync_data_task(token=None):
    BasicCMDBSyncService(token).sync()


@shared_task
def topo_sync_data_task(token):
    TopoCMDBSyncService(token).sync()
