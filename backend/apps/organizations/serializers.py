from rest_framework import serializers
from .models import Organization, ExaminationCenter, Batch, StudentBatchEnrollment


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = [
            'id',
            'name',
            'slug',
            'domain',
            'is_active',
            'settings',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class OrganizationBrandingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ['id', 'name', 'slug', 'domain', 'settings']
        read_only_fields = ['id', 'slug']

    def update(self, instance, validated_data):
        new_settings = validated_data.get('settings', {})
        if new_settings:
            # Merge settings
            current_settings = instance.settings or {}
            current_settings.update(new_settings)
            instance.settings = current_settings
        if 'name' in validated_data:
            instance.name = validated_data['name']
        if 'domain' in validated_data:
            instance.domain = validated_data['domain']
        instance.save()
        return instance


class ExaminationCenterSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExaminationCenter
        fields = ['id', 'organization', 'name', 'code', 'address', 'capacity', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'organization', 'created_at', 'updated_at']


class BatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Batch
        fields = ['id', 'organization', 'name', 'code', 'stream', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'organization', 'created_at', 'updated_at']


class StudentBatchEnrollmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentBatchEnrollment
        fields = ['id', 'student', 'batch', 'center', 'roll_number', 'enrolled_at', 'is_active']
        read_only_fields = ['id', 'enrolled_at']
