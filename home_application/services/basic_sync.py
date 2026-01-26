# cmdb/services/basic_sync.py

from django.db import transaction
from home_application.models import BizInfo, SetInfo, ModuleInfo, SyncStatus
from home_application.services.cmdb_api_client import CMDBApiClient
from home_application.services.cmdb_client import CMDBClient


class BasicCMDBSyncService:
    STATUS_NAME = "basic_sync"

    def __init__(self,token=None):
        if token:
            self.client = CMDBClient(token=token)
        else:
            self.client = CMDBApiClient()
        self.status, _ = SyncStatus.objects.get_or_create(name=self.STATUS_NAME)

    def sync(self):
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

        biz_ids = [b["bk_biz_id"] for b in biz_list]

        # 1. 查已存在的
        existing_map = SetInfo.objects.in_bulk(
            field_name="bk_set_id"
        )

        to_update = []
        to_create = []

        for biz in biz_list:
            obj = existing_map.get(biz["bk_biz_id"])
            if obj:
                obj.bk_biz_name = biz["bk_biz_name"]
                to_update.append(obj)
            else:
                to_create.append(
                    BizInfo(
                        bk_biz_id=biz["bk_biz_id"],
                        bk_biz_name=biz["bk_biz_name"],
                    )
                )

        # 2. 批量更新
        if to_update:
            BizInfo.objects.bulk_update(to_update, ["bk_biz_name"])

        # 3. 批量创建
        if to_create:
            BizInfo.objects.bulk_create(to_create)

        # 4. 删除多余的
        BizInfo.objects.exclude(bk_biz_id__in=biz_ids).delete()

    @transaction.atomic
    def sync_set(self):
        existing_map = SetInfo.objects.in_bulk(
            field_name="bk_set_id"
        )

        seen_ids = set()
        to_update = []
        to_create = []

        for biz in BizInfo.objects.all():
            set_list = self.client.get_set(biz.bk_biz_id)
            for s in set_list:
                seen_ids.add(s["bk_set_id"])
                obj = existing_map.get(s["bk_set_id"])
                if obj:
                    obj.bk_set_name = s["bk_set_name"]
                    obj.bk_biz_id = biz.bk_biz_id
                    to_update.append(obj)
                else:
                    to_create.append(
                        SetInfo(
                            bk_set_id=s["bk_set_id"],
                            bk_set_name=s["bk_set_name"],
                            bk_biz_id=biz.bk_biz_id,
                        )
                    )

        if to_update:
            SetInfo.objects.bulk_update(
                to_update, ["bk_set_name", "bk_biz_id"]
            )

        if to_create:
            SetInfo.objects.bulk_create(to_create)

        SetInfo.objects.exclude(bk_set_id__in=seen_ids).delete()

    @transaction.atomic
    def sync_module(self):
        # ✅ 关键修复点：用 in_bulk
        existing_map = ModuleInfo.objects.in_bulk(
            field_name="bk_module_id"
        )

        seen_ids = set()
        to_update = []
        to_create = []

        for s in SetInfo.objects.all():
            module_list = self.client.get_module(
                s.bk_biz_id, s.bk_set_id
            )
            for m in module_list:
                seen_ids.add(m["bk_module_id"])
                obj = existing_map.get(m["bk_module_id"])

                if obj:
                    # obj.pk 在 in_bulk 场景下是 100% 存在的
                    obj.bk_module_name = m["bk_module_name"]
                    obj.bk_set_id = s.bk_set_id
                    obj.bk_biz_id = s.bk_biz_id
                    to_update.append(obj)
                else:
                    to_create.append(
                        ModuleInfo(
                            bk_module_id=m["bk_module_id"],
                            bk_module_name=m["bk_module_name"],
                            bk_set_id=s.bk_set_id,
                            bk_biz_id=s.bk_biz_id,
                        )
                    )

        if to_update:
            ModuleInfo.objects.bulk_update(
                to_update,
                ["bk_module_name", "bk_set_id", "bk_biz_id"],
            )

        if to_create:
            ModuleInfo.objects.bulk_create(to_create)

        ModuleInfo.objects.exclude(
            bk_module_id__in=seen_ids
        ).delete()