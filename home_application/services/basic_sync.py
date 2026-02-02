# cmdb/services/basic_sync.py
import logging

from django.db import transaction

from home_application.models import BizInfo, ModuleInfo, SetInfo, SyncStatus
from home_application.services.cmdb_api_client import CMDBApiClient
from home_application.services.cmdb_client import CMDBClient

logger = logging.getLogger(__name__)


class BasicCMDBSyncService:
    STATUS_NAME = "basic_sync"

    def __init__(self, token=None):
        if token:
            self.client = CMDBClient(token=token)
        else:
            self.client = CMDBApiClient()
        self.status, _ = SyncStatus.objects.get_or_create(name=self.STATUS_NAME)

    def sync(self):
        try:
            self.status.mark_running()
            self.sync_biz()
            self.sync_set()
            self.sync_module()
        except Exception as e:
            self.status.mark_failed(str(e))
            raise
        else:
            self.status.mark_success()

    def sync_biz(self):
        biz_list = self.client.get_biz()["data"]["info"]

        return self._save_to_database(
            config={
                "model": BizInfo,
                "unique_field": "bk_biz_id",
                "defaults_map": {
                    "bk_biz_name": "bk_biz_name",
                },
            },
            data_list=biz_list,
        )

    def sync_set(self):
        data_list = []

        for biz in BizInfo.objects.all():
            set_list = self.client.get_set(biz.bk_biz_id)["data"]["info"]
            for s in set_list:
                data_list.append(s)

        return self._save_to_database(
            config={
                "model": SetInfo,
                "unique_field": "bk_set_id",
                "defaults_map": {
                    "bk_set_name": "bk_set_name",
                    "bk_biz_id": "bk_biz_id",
                },
            },
            data_list=data_list,
        )

    def sync_module(self):
        data_list = []

        for s in SetInfo.objects.all():
            module_list = self.client.get_module(s.bk_biz_id, s.bk_set_id)["data"]["info"]
            for m in module_list:
                data_list.append(m)

        return self._save_to_database(
            config={
                "model": ModuleInfo,
                "unique_field": "bk_module_id",
                "defaults_map": {
                    "bk_module_name": "bk_module_name",
                    "bk_set_id": "bk_set_id",
                    "bk_biz_id": "bk_biz_id",
                },
            },
            data_list=data_list,
        )

    def _save_to_database(
        self,
        config: dict,
        data_list: list,
    ) -> dict:
        """
        将 CMDB 数据保存到数据库

        config = {
            "model": ModelClass,
            "unique_field": "bk_xxx_id",
            "defaults_map": {
                "model_field": "api_field"
            }
        }
        """
        model_class = config["model"]
        unique_field = config["unique_field"]
        defaults_map = config["defaults_map"]

        saved_count = 0
        data_list = data_list

        try:
            with transaction.atomic():
                for item in data_list:
                    # 必填字段校验
                    if unique_field not in item or item[unique_field] is None:
                        continue

                    defaults = {}
                    for model_field, api_field in defaults_map.items():
                        if api_field in item:
                            defaults[model_field] = item[api_field]

                    model_class.objects.update_or_create(
                        **{unique_field: item[unique_field]},
                        defaults=defaults,
                    )
                    saved_count += 1

            logger.info(f"成功保存 {saved_count} 条 {model_class.__name__} 数据")

            return {
                "success": True,
                "message": f"保存 {saved_count} 条数据成功",
                "saved_count": saved_count,
            }

        except Exception as e:
            logger.exception(f"保存 {model_class.__name__} 数据失败")
            return {
                "success": False,
                "message": str(e),
                "saved_count": 0,
            }
