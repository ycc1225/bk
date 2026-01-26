# cmdb/services/basic_sync.py

from django.db import transaction
from home_application.models import BizInfo, SetInfo, ModuleInfo, SyncStatus
from home_application.services.cmdb_api_client import CMDBApiClient
from home_application.services.cmdb_client import CMDBClient


class BasicCMDBSyncService:
    STATUS_NAME = "basic_sync"

    def __init__(self):
        self.client = CMDBApiClient()
        self.status, _ = SyncStatus.objects.get_or_create(name=self.STATUS_NAME)

    def sync_all(self):
        try:
            self.sync_biz()
            self.sync_set()
            self.sync_module()
        except Exception as e:
            self.status.mark_failed(str(e))
            raise
        else:
            self.status.mark_success()

    @transaction.atomic
    def sync_biz(self):
        biz_list = self.client.get_biz()
        ids = []

        objs = []
        for biz in biz_list:
            ids.append(biz["bk_biz_id"])
            objs.append(
                BizInfo(
                    bk_biz_id=biz["bk_biz_id"],
                    bk_biz_name=biz["bk_biz_name"],
                )
            )

        BizInfo.objects.bulk_create(
            objs,
            update_conflicts=True,
            unique_fields=["bk_biz_id"],
            update_fields=["bk_biz_name"],
        )
        BizInfo.objects.exclude(bk_biz_id__in=ids).delete()

    @transaction.atomic
    def sync_set(self):
        ids = []
        objs = []

        for biz in BizInfo.objects.all():
            set_list = self.client.get_set(biz.bk_biz_id)
            for s in set_list:
                ids.append(s["bk_set_id"])
                objs.append(
                    SetInfo(
                        bk_set_id=s["bk_set_id"],
                        bk_set_name=s["bk_set_name"],
                        bk_biz_id=biz.bk_biz_id,
                    )
                )

        SetInfo.objects.bulk_create(
            objs,
            update_conflicts=True,
            unique_fields=["bk_set_id"],
            update_fields=["bk_set_name", "bk_biz_id"],
        )
        SetInfo.objects.exclude(bk_set_id__in=ids).delete()

    @transaction.atomic
    def sync_module(self):
        ids = []
        objs = []

        for s in SetInfo.objects.all():
            module_list = self.client.get_module(
                s.bk_biz_id, s.bk_set_id
            )
            for m in module_list:
                ids.append(m["bk_module_id"])
                objs.append(
                    ModuleInfo(
                        bk_module_id=m["bk_module_id"],
                        bk_module_name=m["bk_module_name"],
                        bk_set_id=s.bk_set_id,
                        bk_biz_id=s.bk_biz_id,
                    )
                )

        ModuleInfo.objects.bulk_create(
            objs,
            update_conflicts=True,
            unique_fields=["bk_module_id"],
            update_fields=["bk_module_name", "bk_set_id", "bk_biz_id"],
        )
        ModuleInfo.objects.exclude(bk_module_id__in=ids).delete()