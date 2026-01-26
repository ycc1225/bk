from collections import defaultdict

from rest_framework.response import Response
from rest_framework.views import APIView

from home_application.models import BackupJob


class BackupJobListAPIView(APIView):
    """备份作业列表API"""

    def get(self, request):
        """获取备份作业列表"""
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 10))
        start = (page - 1) * page_size

        total_count = BackupJob.objects.count()
        jobs = BackupJob.objects.all()[start:start + page_size]

        res_data = {
            "result": True,
            "data": list(jobs.values()),
            "pagination": {
                "count": total_count,
                "current": page,
                "page_size": page_size,
            }
        }
        return Response(res_data)


class BackupJobDetailAPIView(APIView):
    """备份作业详情API"""

    def get(self, request, pk):
        """获取备份作业详情"""
        job_id = pk  # 使用URL参数中的pk作为job_id

        job = BackupJob.objects.get(id=job_id)
        records = job.records.all()

        # 按主机分组
        host_files = defaultdict(list)
        for record in records:
            host_files[record.bk_host_id].append({
                "file_path": record.bk_backup_name,
                "status": record.status
            })

        res_data = {
            "result": True,
            "data": {
                "job": {
                    "id": job.id,
                    "job_instance_id": job.job_instance_id,
                    "operator": job.operator,
                    "search_path": job.search_path,
                    "suffix": job.suffix,
                    "backup_path": job.backup_path,
                    "bk_job_link": job.bk_job_link,
                    "status": job.status,
                    "host_count": job.host_count,
                    "file_count": job.file_count,
                    "created_at": job.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                },
                "host_files": dict(host_files)
            }
        }
        return Response(res_data)
