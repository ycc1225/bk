"""
备份失败诊断服务（规则引擎，零外部依赖）

通过关键词匹配对失败的备份日志进行自动归因，
生成失败类型、诊断摘要和修复建议，结果存入数据库。

使用方式：
    from home_application.services.diagnosis import DiagnosisService
    diagnosis = DiagnosisService().diagnose_backup_job(backup_job)
"""

import logging

from home_application.models import BackupJob, BackupRecord, DiagnosisRecord

logger = logging.getLogger(__name__)

# =============================
# 诊断规则定义
# 格式：(关键词列表, 失败类别, 修复建议)
# 规则按优先级从高到低排列，匹配到第一条即停止
# =============================
DIAGNOSIS_RULES = [
    (
        ["permission denied", "access denied", "权限不足"],
        DiagnosisRecord.FailureCategory.PERMISSION_DENIED,
        "检查目标路径的文件权限，确保执行用户有读/写权限",
    ),
    (
        ["no space left", "disk full", "磁盘满", "空间不足"],
        DiagnosisRecord.FailureCategory.DISK_FULL,
        "清理目标主机磁盘空间，或更换备份路径到有足够空间的分区",
    ),
    (
        ["no such file", "not found", "路径不存在"],
        DiagnosisRecord.FailureCategory.PATH_NOT_FOUND,
        "检查搜索路径和备份路径是否正确存在",
    ),
    (
        ["timeout", "超时"],
        DiagnosisRecord.FailureCategory.TIMEOUT,
        "作业执行超时，建议分批处理或调大超时时间",
    ),
    (
        ["agent", "gse", "proxy"],
        DiagnosisRecord.FailureCategory.AGENT_OFFLINE,
        "目标主机 Agent 异常，请检查 Agent 进程状态并尝试重启",
    ),
    (
        ["connection refused", "connection reset", "网络"],
        DiagnosisRecord.FailureCategory.NETWORK_ERROR,
        "检查主机网络连通性和防火墙规则",
    ),
]


class DiagnosisService:
    """备份作业失败诊断服务（关键词规则匹配）"""

    def diagnose_backup_job(self, backup_job: BackupJob) -> DiagnosisRecord | None:
        """对失败/部分成功的备份作业进行诊断，结果存入数据库

        Args:
            backup_job: 需要诊断的备份作业实例

        Returns:
            DiagnosisRecord 实例，或 None（作业成功时无需诊断）
        """
        # 成功的作业不需要诊断
        if backup_job.status == BackupJob.Status.SUCCESS:
            return None

        # 避免重复诊断
        existing = DiagnosisRecord.objects.filter(backup_job=backup_job).first()
        if existing:
            logger.info("[诊断] 作业 %s 已存在诊断记录，跳过", backup_job.job_instance_id)
            return existing

        # 获取失败的备份记录
        failed_records = BackupRecord.objects.filter(backup_job=backup_job, status="failed")

        if not failed_records.exists():
            logger.info("[诊断] 作业 %s 没有失败记录，跳过", backup_job.job_instance_id)
            return None

        # 逐条分析失败记录
        host_diagnoses = []
        category_counter = {}

        for record in failed_records:
            category, suggestion = self.match_rule(record.bk_backup_name)
            category_counter[category] = category_counter.get(category, 0) + 1
            host_diagnoses.append(
                {
                    "bk_host_id": record.bk_host_id,
                    "log_content": record.bk_backup_name,
                    "category": category,
                    "suggestion": suggestion,
                }
            )

        # 确定主要失败类型（出现次数最多的类别）
        top_category = max(category_counter, key=category_counter.get)

        # 获取主要类型对应的修复建议
        top_suggestion = self._get_suggestion_for_category(top_category)

        # 生成诊断摘要
        summary = self._build_summary(category_counter)

        # 入库
        diagnosis = DiagnosisRecord.objects.create(
            backup_job=backup_job,
            top_category=top_category,
            summary=summary,
            suggestion=top_suggestion,
            detail={
                "category_counter": category_counter,
                "host_diagnoses": host_diagnoses[:50],
            },
        )

        logger.info(
            "[诊断] 作业 %s 诊断完成 | 主要原因: %s | 失败主机: %d",
            backup_job.job_instance_id,
            top_category,
            len(host_diagnoses),
        )

        return diagnosis

    @staticmethod
    def match_rule(log_content: str) -> tuple:
        """基于关键词匹配失败原因（公共接口）

        Args:
            log_content: 日志内容

        Returns:
            (失败类别, 修复建议)
        """
        if not log_content:
            return (
                DiagnosisRecord.FailureCategory.UNKNOWN,
                "日志内容为空，建议到 JOB 平台查看详细执行日志",
            )

        log_lower = log_content.lower()
        for keywords, category, suggestion in DIAGNOSIS_RULES:
            if any(kw in log_lower for kw in keywords):
                return category, suggestion

        return (
            DiagnosisRecord.FailureCategory.UNKNOWN,
            "无法自动识别失败原因，建议到 JOB 平台查看详细执行日志",
        )

    @staticmethod
    def _get_suggestion_for_category(category: str) -> str:
        """根据失败类型获取修复建议"""
        for _, rule_category, suggestion in DIAGNOSIS_RULES:
            if rule_category == category:
                return suggestion
        return "建议到 JOB 平台查看详细执行日志"

    @staticmethod
    def _build_summary(category_counter: dict) -> str:
        """生成诊断摘要文本"""
        total_failed = sum(category_counter.values())
        lines = [f"共 {total_failed} 台主机备份失败。"]

        for cat, count in sorted(category_counter.items(), key=lambda x: -x[1]):
            label = DiagnosisRecord.FailureCategory(cat).label
            lines.append(f"  - {label}: {count} 台")

        return "\n".join(lines)
