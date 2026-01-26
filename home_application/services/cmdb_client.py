import os

from blueking.component.shortcuts import get_client_by_request
from config import APP_CODE, SECRET_KEY
from home_application.constants import DATA_CONFIGS


class CMDBClient:
    def __init__(self, request=None, token=None):
        if request:
            self.client = get_client_by_request(request)
        elif token:
            from blueking.component import client as component_client
            from blueking.component import conf
            self.client = component_client.ComponentClient(
                APP_CODE,
                SECRET_KEY,
                common_args={"bk_token": token}
            )
        else:
            raise ValueError("Either request or token must be provided")

    def get_biz(self):
        kwargs = {
            "fields": DATA_CONFIGS['biz']['fields']
        }
        return self.client.cc.search_business(kwargs)

    def get_set(self, biz_id: int):
        kwargs = {
            "bk_biz_id": biz_id,
            "fields": DATA_CONFIGS['set']['fields']
        }
        return self.client.cc.search_set(kwargs)

    def get_module(self, biz_id: int, set_id: int):
        kwargs = {
            "bk_biz_id": biz_id,
            "bk_set_id": set_id,
            "fields": DATA_CONFIGS['module']['fields']
        }
        return self.client.cc.search_module(kwargs)

    def get_topo(self,biz_id):
        kwargs = {
            "bk_biz_id": biz_id,
        }
        return self.client.cc.search_biz_inst_topo(biz_id)

    def get_host_list(self, args):
        return self.client.cc.list_biz_hosts(args)

    def get_host_detail(self, args):
        return self.client.cc.get_host_base_info(args)