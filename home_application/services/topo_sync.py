# cmdb/services/topo_sync.py

from home_application.models import BizInfo, SetInfo, ModuleInfo, SyncStatus
from home_application.services.cmdb_client import CMDBClient


class TopoCMDBSyncService:
    STATUS_NAME = "topo_sync"

    def __init__(self, token: str):
        self.client = CMDBClient(token=token)
        self.status, _ = SyncStatus.objects.get_or_create(name=self.STATUS_NAME)

    def sync(self):
        try:

            topo = self.client.get_topo()
            self._sync_from_topo(topo)
        except Exception as e:
            self.status.mark_failed(str(e))
            raise
        else:
            self.status.mark_success()

    def _sync_from_topo(self, topo: dict):
        """
        使用topo快速同步
        """
        pass
