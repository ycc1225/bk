import logging

import requests
from requests import RequestException

from home_application.constants import (
    API_AUTH_HEADER,
    API_ENDPOINTS,
    CMDB_BASE_URL,
    DATA_CONFIGS,
    SUPPLIER_ACCOUNT,
)

logger = logging.getLogger(__name__)


class CMDBApiClient:
    def __init__(self):
        self.headers = API_AUTH_HEADER

    def _send_request(self, url, payload=None):
        try:
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()

            data = response.json()
            if data.get("result", False) and "data" in data:
                result_data = data["data"]["info"]
                return result_data
            else:
                error_msg = data.get("message", "Unknown error")
                logger.error(f"CMDB API Error: {error_msg}")
                raise Exception(error_msg)
        except RequestException as e:
            logger.error(f"Request Error: {e}")
            raise
        except ValueError as e:
            logger.error(f"JSON Decode Error: {e}")
            raise

    def get_biz(self):
        url = CMDB_BASE_URL + API_ENDPOINTS["biz"].format(supplier_account=SUPPLIER_ACCOUNT)
        payload = {"fields": DATA_CONFIGS["biz"]["fields"]}
        return self._send_request(url, payload)

    def get_set(self, bk_biz_id):
        url = CMDB_BASE_URL + API_ENDPOINTS["set"].format(supplier_account=SUPPLIER_ACCOUNT, bk_biz_id=bk_biz_id)
        payload = {"fields": DATA_CONFIGS["set"]["fields"]}
        return self._send_request(url, payload)

    def get_module(self, bk_biz_id, bk_set_id):
        url = CMDB_BASE_URL + API_ENDPOINTS["module"].format(
            supplier_account=SUPPLIER_ACCOUNT, bk_biz_id=bk_biz_id, bk_set_id=bk_set_id
        )
        payload = {"fields": DATA_CONFIGS["module"]["fields"]}
        return self._send_request(url, payload)
