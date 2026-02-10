from django.db import migrations


def create_periodic_task(apps, schema_editor):
    try:
        IntervalSchedule = apps.get_model("django_celery_beat", "IntervalSchedule")
        PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    except LookupError:
        print("Warning: django_celery_beat app not installed, skipping task creation.")
        return

    # 创建 60 秒的间隔
    schedule, created = IntervalSchedule.objects.get_or_create(
        every=60,
        period="seconds",
    )

    # 创建或更新定时任务
    PeriodicTask.objects.update_or_create(
        name="Push Metrics to BK Monitor",
        defaults={
            "interval": schedule,
            "task": "home_application.tasks.metrics_push.push_metrics_task",
            "enabled": True,
            "description": "每60秒推送 Prometheus 指标到蓝鲸监控平台",
        },
    )


def remove_periodic_task(apps, schema_editor):
    try:
        PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    except LookupError:
        return

    try:
        PeriodicTask.objects.filter(name="Push Metrics to BK Monitor").delete()
    except Exception:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ("home_application", "0016_userrole"),
    ]

    operations = [
        migrations.RunPython(create_periodic_task, remove_periodic_task),
    ]
