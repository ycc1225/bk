import json
import os

from home_application.models import BizInfo, SetInfo, ModuleInfo

# JOB执行作业的业务ID
JOB_BK_BIZ_ID = 3

# 作业执行结果查询的最大轮询次数
MAX_ATTEMPTS = 10

# 调用作业执行结果api的轮询间隔
JOB_RESULT_ATTEMPTS_INTERVAL = 0.2

# JOB作业平台HOST
BK_JOB_HOST = os.getenv("BKPAAS_JOB_URL")

# JOB 平台的状态码
WAITING_CODE = 2
SUCCESS_CODE = 3
STEP_STATUS_SUCCESS = 9

# 默认HTTP状态码
WEB_SUCCESS_CODE = 0

# 作业方案ID
SEARCH_FILE_PLAN_ID = 1000451   # 将这里的方案ID更改为你自己在JOB平台上新建的方案ID
BACKUP_FILE_PLAN_ID = 1000452

CALLBACK_URL = os.getenv("BACKEND_URL", "") + "api/backup-callback/"

# API鉴权信息
_auth_info = {
    "bk_username": "25zhujiao1",
    "bk_app_code": os.getenv("BKPAAS_APP_ID"),
    "bk_app_secret": os.getenv("BKPAAS_APP_SECRET"),
}

API_AUTH_HEADER = {"X-Bkapi-Authorization":json.dumps(_auth_info)}
# API端点
CMDB_BASE_URL = "https://bkapi.ce.bktencent.com/api/bk-cmdb/prod/api/v3"
SUPPLIER_ACCOUNT = "0"
API_ENDPOINTS = {
    'biz': '/biz/search/{supplier_account}',
    'set': '/set/search/{supplier_account}/{bk_biz_id}',
    'module': '/module/search/{supplier_account}/{bk_biz_id}/{bk_set_id}'
}
# CMDB数据配置
DATA_CONFIGS = {
    'biz': {
        'model': BizInfo,
        'unique_field': 'bk_biz_id',
        'fields': ['bk_biz_id', 'bk_biz_name'],
        'defaults_map': {'bk_biz_name': 'bk_biz_name'}
    },
    'set': {
        'model': SetInfo,
        'unique_field': 'bk_set_id',
        'fields': ['bk_set_id', 'bk_set_name', 'bk_biz_id'],
        'defaults_map': {
            'bk_set_name': 'bk_set_name',
            'bk_biz_id': 'bk_biz_id'
        }
    },
    'module': {
        'model': ModuleInfo,
        'unique_field': 'bk_module_id',
        'fields': ['bk_module_id', 'bk_module_name', 'bk_set_id', 'bk_biz_id'],
        'defaults_map': {
            'bk_module_name': 'bk_module_name',
            'bk_set_id': 'bk_set_id',
            'bk_biz_id': 'bk_biz_id'
        }
    }
}
