# -*- coding: utf-8 -*-
"""
DRF 序列化器定义
"""
from rest_framework import serializers
from .models import BizInfo, SetInfo, ModuleInfo, BackupJob, BackupRecord, ApiRequestCount


class BizInfoSerializer(serializers.ModelSerializer):
    """业务信息序列化器"""
    
    class Meta:
        model = BizInfo
        fields = ['id', 'bk_biz_id', 'bk_biz_name']
        read_only_fields = ['id']


class SetInfoSerializer(serializers.ModelSerializer):
    """集群信息序列化器"""
    
    class Meta:
        model = SetInfo
        fields = ['id', 'bk_set_id', 'bk_set_name', 'bk_biz_id']
        read_only_fields = ['id']


class ModuleInfoSerializer(serializers.ModelSerializer):
    """模块信息序列化器"""
    
    class Meta:
        model = ModuleInfo
        fields = ['id', 'bk_module_id', 'bk_module_name', 'bk_set_id', 'bk_biz_id']
        read_only_fields = ['id']


class BackupRecordSerializer(serializers.ModelSerializer):
    """备份记录序列化器"""
    
    class Meta:
        model = BackupRecord
        fields = ['id', 'bk_host_id', 'status', 'bk_backup_name']
        read_only_fields = ['id']


class BackupJobSerializer(serializers.ModelSerializer):
    """备份作业序列化器"""
    records = BackupRecordSerializer(many=True, read_only=True)
    operator_name = serializers.CharField(source='operator', read_only=True)
    
    class Meta:
        model = BackupJob
        fields = [
            'id', 'job_instance_id', 'operator', 'operator_name',
            'search_path', 'suffix', 'backup_path', 'bk_job_link',
            'status', 'host_count', 'file_count', 'created_at', 'records'
        ]
        read_only_fields = ['id', 'created_at']


class BackupJobListSerializer(serializers.ModelSerializer):
    """备份作业列表序列化器（不包含records详情）"""
    operator_name = serializers.CharField(source='operator', read_only=True)
    
    class Meta:
        model = BackupJob
        fields = [
            'id', 'job_instance_id', 'operator', 'operator_name',
            'search_path', 'suffix', 'backup_path', 'bk_job_link',
            'status', 'host_count', 'file_count', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class ApiRequestCountSerializer(serializers.ModelSerializer):
    """API请求次数序列化器"""
    
    class Meta:
        model = ApiRequestCount
        fields = ['id', 'api_category', 'api_name', 'request_count']
        read_only_fields = ['id']