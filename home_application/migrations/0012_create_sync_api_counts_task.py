# -*- coding: utf-8 -*-
from django.db import migrations

def create_periodic_task(apps, schema_editor):
    try:
        # 使用 apps.get_model 获取模型，避免直接导入
        IntervalSchedule = apps.get_model('django_celery_beat', 'IntervalSchedule')
        PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
    except LookupError:
        # 如果 django_celery_beat 应用未安装，则跳过
        print("Warning: django_celery_beat app not installed, skipping task creation.")
        return

    # 创建 5 秒的间隔
    # 注意：period 的值必须匹配 IntervalSchedule.PERIOD_CHOICES 中的值
    schedule, created = IntervalSchedule.objects.get_or_create(
        every=5,
        period='seconds',
    )

    # 创建或更新定时任务
    PeriodicTask.objects.update_or_create(
        name='Sync API Counts to DB',
        defaults={
            'interval': schedule,
            'task': 'home_application.tasks.sync_api_counts_task',
            'enabled': True,
            'description': '每5秒从Redis同步API请求统计到数据库',
        }
    )

def remove_periodic_task(apps, schema_editor):
    try:
        PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
    except LookupError:
        return

    # 删除任务
    try:
        PeriodicTask.objects.filter(name='Sync API Counts to DB').delete()
    except Exception:
        pass

class Migration(migrations.Migration):

    dependencies = [
        ('home_application', '0011_auto_20260122_1643'),
    ]

    operations = [
        migrations.RunPython(create_periodic_task, remove_periodic_task),
    ]