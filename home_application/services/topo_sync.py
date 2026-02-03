# cmdb/services/topo_sync.py
from concurrent.futures import ThreadPoolExecutor

from django.db import transaction

from home_application.models import BizInfo, ModuleInfo, SetInfo, SyncStatus
from home_application.services.cmdb_client import CMDBClient


class TopoCMDBSyncService:
    STATUS_NAME = "topo_sync"

    def __init__(self, token: str):
        self.client = CMDBClient(token=token)
        self.status, _ = SyncStatus.objects.get_or_create(name=self.STATUS_NAME)

    def sync(self):
        try:
            self.status.mark_running()
            biz_list = self.client.get_biz()["data"]["info"]
            with ThreadPoolExecutor(max_workers=10) as executor:
                list(executor.map(self.sync_biz_topo, biz_list))

        except Exception as e:
            self.status.mark_failed(str(e))
            raise
        else:
            self.status.mark_success()

    def sync_biz_topo(self, biz):
        topo = self.client.get_topo(biz["bk_biz_id"])["data"]
        self._sync_from_topo(topo[0])

    def _sync_from_topo(self, data: dict):
        """
        使用topo快速同步
        """
        biz_id = data.get("bk_inst_id")
        if not biz_id:
            raise ValueError(f"Invalid biz_id: {biz_id}")
        set_map = {}
        module_map = {}

        environments = data.get("child", [])
        for env in environments:
            subsystem = env.get("child", [])
            for sub in subsystem:
                sets = sub.get("child", [])
                for s in sets:
                    set_id = s.get("bk_inst_id")
                    set_name = s.get("bk_inst_name")
                    set_map[set_id] = SetInfo(bk_biz_id=biz_id, bk_set_id=set_id, bk_set_name=set_name)
                    modules = s.get("child", [])
                    for m in modules:
                        mod_id = m.get("bk_inst_id")
                        mod_name = m.get("bk_inst_name")
                        module_map[mod_id] = ModuleInfo(
                            bk_biz_id=biz_id, bk_set_id=set_id, bk_module_id=mod_id, bk_module_name=mod_name
                        )

        with transaction.atomic():
            BizInfo.objects.update_or_create(bk_biz_id=biz_id, defaults={"bk_biz_name": data.get("bk_inst_name")})
            _bulk_upsert(SetInfo, set_map, "bk_set_id", ["bk_biz_id", "bk_set_name"])
            _bulk_upsert(ModuleInfo, module_map, "bk_module_id", ["bk_biz_id", "bk_set_id", "bk_module_name"])


def _bulk_upsert(model, objects, id_field, update_fields):
    """
    批量更新或创建
    """
    if not objects:
        return
    all_ids = list(objects.keys())
    existing_records = model.objects.filter(**{f"{id_field}__in": all_ids}).values(id_field, "pk")
    id_mapping = {item[id_field]: item["pk"] for item in existing_records}

    to_update = []
    to_create = []

    for obj_id, obj in objects.items():
        if obj_id in id_mapping:
            obj.pk = id_mapping[obj_id]
            to_update.append(obj)
        else:
            to_create.append(obj)

    if to_create and len(to_create) > 0:
        model.objects.bulk_create(to_create, batch_size=500)
    if to_update and len(to_update) > 0:
        model.objects.bulk_update(to_update, update_fields, batch_size=500)
