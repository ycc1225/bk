import json
import os

from home_application.models import BizInfo, ModuleInfo, SetInfo

# =============================
# API鉴权信息
# =============================
_auth_info = {
    "bk_username": os.getenv("BK_USERNAME", "admin"),
    "bk_app_code": os.getenv("BKPAAS_APP_ID"),
    "bk_app_secret": os.getenv("BKPAAS_APP_SECRET"),
}

API_AUTH_HEADER = {"X-Bkapi-Authorization": json.dumps(_auth_info)}

# =============================
# JOB常量
# =============================

# 作业执行结果查询的最大轮询次数
# 配合 retry_backoff=0.5 和 retry_backoff_max=10，可支持最长 55 秒的作业
# 适用于 90% 作业在 1-2 秒内完成的场景
MAX_ATTEMPTS = 10

# 轮询间隔基数（秒）
# 实际间隔会指数增长:1s, 2s, 4s, 8s, 10s(max), 10s, ...
JOB_RESULT_ATTEMPTS_INTERVAL = 1

# 轮询最大间隔（秒）
# 限制指数退避的最大间隔时间，避免等待过久
JOB_RETRY_BACKOFF_MAX = 10

# JOB作业平台HOST
BK_JOB_HOST = os.getenv("BKPAAS_JOB_URL")

# JOB 平台的状态码
WAITING_CODE = 2
SUCCESS_CODE = 3
FAILED_CODE = 4
STEP_STATUS_SUCCESS = 9

# 默认HTTP状态码
WEB_SUCCESS_CODE = 0

# 从环境变量读取业务 ID
JOB_BK_BIZ_ID = int(os.getenv("JOB_BK_BIZ_ID", "3"))

# 从环境变量读取作业方案 ID
SEARCH_FILE_PLAN_ID = int(os.getenv("SEARCH_FILE_PLAN_ID", "1000451"))
BACKUP_FILE_PLAN_ID = int(os.getenv("BACKUP_FILE_PLAN_ID", "1000452"))


# =============================
# JOB请求参数
# =============================

# JOB备份文件路径白名单
ALLOW_PATH_PREFIX = ["/project"]
ALLOW_FILE_SUFFIX = ["log", "txt", "csv", "json", "bak"]

# JOB回调URL
CALLBACK_URL = os.getenv("BACKEND_URL", "") + "api/job/backup-callback/"

# API端点
CMDB_BASE_URL = "https://bkapi.ce.bktencent.com/api/bk-cmdb/prod/api/v3"
SUPPLIER_ACCOUNT = "0"
API_ENDPOINTS = {
    "biz": "/biz/search/{supplier_account}",
    "set": "/set/search/{supplier_account}/{bk_biz_id}",
    "module": "/module/search/{supplier_account}/{bk_biz_id}/{bk_set_id}",
}

# 作业最大返回条数
MAX_HOST_COUNT = 5
MAX_FILE_COUNT = 5

# =============================
# CMDB数据库表字段映射
# =============================
DATA_CONFIGS = {
    "biz": {
        "model": BizInfo,
        "unique_field": "bk_biz_id",
        "fields": ["bk_biz_id", "bk_biz_name"],
        "defaults_map": {"bk_biz_name": "bk_biz_name"},
    },
    "set": {
        "model": SetInfo,
        "unique_field": "bk_set_id",
        "fields": ["bk_set_id", "bk_set_name", "bk_biz_id"],
        "defaults_map": {"bk_set_name": "bk_set_name", "bk_biz_id": "bk_biz_id"},
    },
    "module": {
        "model": ModuleInfo,
        "unique_field": "bk_module_id",
        "fields": ["bk_module_id", "bk_module_name", "bk_set_id", "bk_biz_id"],
        "defaults_map": {"bk_module_name": "bk_module_name", "bk_set_id": "bk_set_id", "bk_biz_id": "bk_biz_id"},
    },
}

# =============================
# 角色常量与层级体系
# =============================

# 角色枚举值
ROLE_ADMIN = "admin"
ROLE_OPS = "ops"
ROLE_DEV = "dev"
ROLE_BOT = "bot"

ROLE_CHOICES = (
    (ROLE_ADMIN, "管理员"),
    (ROLE_OPS, "运维"),
    (ROLE_DEV, "开发"),
    (ROLE_BOT, "机器人"),
)

# 所有有效角色值集合
VALID_ROLES = {ROLE_ADMIN, ROLE_OPS, ROLE_DEV, ROLE_BOT}

# 角色层级数值映射（数值越大，权限越高）
# Bot 与 Dev 同级（均为10），但逻辑上独立区分
ROLE_LEVEL = {
    ROLE_ADMIN: 100,
    ROLE_OPS: 50,
    ROLE_DEV: 10,
    ROLE_BOT: 10,
}


def get_role_level(role):
    """获取角色的层级数值，用于权限比较。

    Args:
        role: 角色字符串，如 'admin'、'ops'、'dev'、'bot'

    Returns:
        int: 角色对应的层级数值，未知角色返回 0
    """
    return ROLE_LEVEL.get(role, 0)
