"""
ChatOps 核心服务

使用 LangChain Agent + Tool Calling 实现自然语言运维查询。
所有工具均为只读查询，不涉及任何写入操作。
"""

import json
import logging
from datetime import timedelta
from typing import Optional

from django.db.models import Sum
from django.utils import timezone
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool

from home_application.models import (
    ApiRequestCount,
    BackupJob,
    BackupRecord,
    BizInfo,
    DiagnosisRecord,
    ModuleInfo,
    SetInfo,
    SyncStatus,
)
from home_application.services.llm_client import get_llm

logger = logging.getLogger(__name__)

# 查询结果最大条数限制
MAX_RESULTS = 20

# =============================
# 系统提示词
# =============================

SYSTEM_PROMPT = """你是蓝鲸运维平台的 AI 助手，帮助用户查询文件备份和 CMDB 拓扑数据。

你可以帮用户完成以下查询操作：
1. 查询 CMDB 业务/集群/模块信息，模糊搜索拓扑节点
2. 查询备份作业的状态和历史记录
3. 查看备份作业的详细信息和诊断结果
4. 查看 API 调用统计和 CMDB 同步状态

约束：
- 你只能查询数据，不能执行任何写入或修改操作
- 如果用户要求执行操作（如发起备份），请告知该功能暂未开放
- 如果用户的描述不够明确，请主动追问缺少的参数
- 回复简洁实用，使用中文
- 如果查询结果为空，友好地告知用户"""


# =============================
# 工具定义（LangChain @tool）
# =============================


@tool
def query_business_list(keyword: Optional[str] = None) -> str:
    """查询 CMDB 业务列表。可选传入关键字进行模糊搜索。

    Args:
        keyword: 业务名称关键字，用于模糊搜索，不传则返回全部业务
    """
    qs = BizInfo.objects.all()
    if keyword:
        qs = qs.filter(bk_biz_name__icontains=keyword)
    results = list(qs.values("bk_biz_id", "bk_biz_name")[:MAX_RESULTS])
    if not results:
        return "未找到匹配的业务"
    return json.dumps(results, ensure_ascii=False)


@tool
def query_sets(bk_biz_id: int, keyword: Optional[str] = None) -> str:
    """查询某个业务下的集群列表。

    Args:
        bk_biz_id: 业务ID（必填）
        keyword: 集群名称关键字，用于模糊搜索
    """
    qs = SetInfo.objects.filter(bk_biz_id=bk_biz_id)
    if keyword:
        qs = qs.filter(bk_set_name__icontains=keyword)
    results = list(qs.values("bk_set_id", "bk_set_name", "bk_biz_id")[:MAX_RESULTS])
    if not results:
        return f"业务 {bk_biz_id} 下未找到匹配的集群"
    return json.dumps(results, ensure_ascii=False)


@tool
def query_modules(bk_biz_id: int, bk_set_id: Optional[int] = None, keyword: Optional[str] = None) -> str:
    """查询模块列表。可按业务ID和集群ID筛选。

    Args:
        bk_biz_id: 业务ID（必填）
        bk_set_id: 集群ID，不传则查该业务下所有模块
        keyword: 模块名称关键字，用于模糊搜索
    """
    qs = ModuleInfo.objects.filter(bk_biz_id=bk_biz_id)
    if bk_set_id is not None:
        qs = qs.filter(bk_set_id=bk_set_id)
    if keyword:
        qs = qs.filter(bk_module_name__icontains=keyword)
    results = list(qs.values("bk_module_id", "bk_module_name", "bk_set_id", "bk_biz_id")[:MAX_RESULTS])
    if not results:
        return "未找到匹配的模块"
    return json.dumps(results, ensure_ascii=False)


@tool
def topo_search(keyword: str) -> str:
    """拓扑模糊搜索，在业务、集群、模块三个层级中搜索包含关键字的节点，返回完整拓扑路径。

    Args:
        keyword: 搜索关键字（必填）
    """
    # 构建映射
    biz_map = {b.bk_biz_id: b.bk_biz_name for b in BizInfo.objects.all()}
    set_map = {s.bk_set_id: {"bk_set_name": s.bk_set_name, "bk_biz_id": s.bk_biz_id} for s in SetInfo.objects.all()}

    results = []

    # 搜索业务
    for biz in BizInfo.objects.filter(bk_biz_name__icontains=keyword):
        results.append({"type": "biz", "topo_path": biz.bk_biz_name, "bk_biz_id": biz.bk_biz_id})

    # 搜索集群
    for s in SetInfo.objects.filter(bk_set_name__icontains=keyword):
        biz_name = biz_map.get(s.bk_biz_id, "未知业务")
        results.append(
            {
                "type": "set",
                "topo_path": f"{biz_name} / {s.bk_set_name}",
                "bk_biz_id": s.bk_biz_id,
                "bk_set_id": s.bk_set_id,
            }
        )

    # 搜索模块
    for m in ModuleInfo.objects.filter(bk_module_name__icontains=keyword):
        biz_name = biz_map.get(m.bk_biz_id, "未知业务")
        set_info = set_map.get(m.bk_set_id, {})
        set_name = set_info.get("bk_set_name", "未知集群")
        results.append(
            {
                "type": "module",
                "topo_path": f"{biz_name} / {set_name} / {m.bk_module_name}",
                "bk_biz_id": m.bk_biz_id,
                "bk_set_id": m.bk_set_id,
                "bk_module_id": m.bk_module_id,
            }
        )

    if not results:
        return f"未找到包含 '{keyword}' 的拓扑节点"
    return json.dumps(results[:MAX_RESULTS], ensure_ascii=False)


@tool
def query_backup_jobs(
    status: Optional[str] = None,
    operator: Optional[str] = None,
    limit: int = 10,
) -> str:
    """查询备份作业列表。可按状态和操作人筛选。

    Args:
        status: 作业状态筛选，可选值：pending/processing/success/failed/partial
        operator: 按操作人筛选
        limit: 返回条数，默认10，最大20
    """
    qs = BackupJob.objects.all()
    if status:
        qs = qs.filter(status=status)
    if operator:
        qs = qs.filter(operator__icontains=operator)
    limit = min(limit, MAX_RESULTS)
    results = list(
        qs.values(
            "id",
            "job_instance_id",
            "operator",
            "search_path",
            "suffix",
            "backup_path",
            "status",
            "host_count",
            "file_count",
            "created_at",
        )[:limit]
    )
    if not results:
        return "未找到匹配的备份作业"
    # 格式化时间
    for r in results:
        if r.get("created_at"):
            r["created_at"] = r["created_at"].strftime("%Y-%m-%d %H:%M:%S")
    return json.dumps(results, ensure_ascii=False)


@tool
def query_backup_job_detail(job_id: int) -> str:
    """查询某个备份作业的详细信息，包括备份记录明细和诊断结果（如有）。

    Args:
        job_id: 备份作业ID（必填）
    """
    try:
        job = BackupJob.objects.get(id=job_id)
    except BackupJob.DoesNotExist:
        return f"未找到 ID 为 {job_id} 的备份作业"

    result = {
        "id": job.id,
        "job_instance_id": job.job_instance_id,
        "operator": job.operator,
        "search_path": job.search_path,
        "suffix": job.suffix,
        "backup_path": job.backup_path,
        "status": job.status,
        "host_count": job.host_count,
        "file_count": job.file_count,
        "bk_job_link": job.bk_job_link,
        "created_at": job.created_at.strftime("%Y-%m-%d %H:%M:%S") if job.created_at else None,
    }

    # 备份记录明细
    records = list(
        BackupRecord.objects.filter(backup_job=job).values("bk_host_id", "status", "bk_backup_name")[:MAX_RESULTS]
    )
    result["records"] = records
    result["records_total"] = BackupRecord.objects.filter(backup_job=job).count()

    # 诊断记录
    try:
        diag = job.diagnosis
        result["diagnosis"] = {
            "top_category": diag.get_top_category_display(),
            "summary": diag.summary,
            "suggestion": diag.suggestion,
        }
    except DiagnosisRecord.DoesNotExist:
        result["diagnosis"] = None

    return json.dumps(result, ensure_ascii=False)


@tool
def query_sync_status() -> str:
    """查询 CMDB 数据同步状态，显示各同步任务的最近执行情况。"""
    results = list(SyncStatus.objects.all().values("name", "last_sync_at", "last_status", "last_error", "updated_at"))
    if not results:
        return "暂无同步状态记录"
    for r in results:
        for field in ("last_sync_at", "updated_at"):
            if r.get(field):
                r[field] = r[field].strftime("%Y-%m-%d %H:%M:%S")
    return json.dumps(results, ensure_ascii=False)


@tool
def query_api_stats(days: int = 7) -> str:
    """查询 API 调用统计数据，按类别和名称汇总请求次数与错误次数。

    Args:
        days: 统计最近多少天的数据，默认7天，最大30天
    """
    days = min(days, 30)
    since = timezone.now().date() - timedelta(days=days)
    qs = (
        ApiRequestCount.objects.filter(date__gte=since)
        .values("api_category", "api_name")
        .annotate(total_requests=Sum("request_count"), total_errors=Sum("error_count"))
        .order_by("-total_requests")
    )
    results = list(qs[:MAX_RESULTS])
    if not results:
        return f"最近 {days} 天暂无 API 调用记录"
    return json.dumps(results, ensure_ascii=False)


# =============================
# 工具列表
# =============================

ALL_TOOLS = [
    query_business_list,
    query_sets,
    query_modules,
    topo_search,
    query_backup_jobs,
    query_backup_job_detail,
    query_sync_status,
    query_api_stats,
]


# =============================
# ChatOps 服务
# =============================


class ChatOpsService:
    """ChatOps 对话服务，基于 langchain create_agent 实现"""

    def __init__(self):
        self._agent = None

    def _get_agent(self):
        """延迟初始化 Agent（避免模块加载时就连接 LLM）"""
        if self._agent is None:
            llm = get_llm()
            self._agent = create_agent(
                model=llm,
                tools=ALL_TOOLS,
                system_prompt=SYSTEM_PROMPT,
            )
        return self._agent

    def chat(self, message: str, conversation_history: list = None) -> dict:
        """
        处理用户消息，返回 AI 回复

        Args:
            message: 用户消息
            conversation_history: 历史对话列表，格式 [{"role": "user/assistant", "content": "..."}]

        Returns:
            dict: {"reply": "AI回复内容"}
        """
        # 构建消息列表：历史消息 + 当前消息
        messages = []
        if conversation_history:
            for msg in conversation_history:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role == "user":
                    messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    messages.append(AIMessage(content=content))

        # 添加当前用户消息
        messages.append(HumanMessage(content=message))

        agent = self._get_agent()
        result = agent.invoke({"messages": messages})

        # 提取最终回复（最后一条 AI 消息）
        output_messages = result.get("messages", [])
        if output_messages:
            reply = output_messages[-1].content
        else:
            reply = "抱歉，我无法处理这个请求。"

        return {"reply": reply}


# 全局单例
chatops_service = ChatOpsService()
