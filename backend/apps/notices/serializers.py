from rest_framework import serializers
from .models import Notice


class NoticeSerializer(serializers.ModelSerializer):
    target_batch_ids = serializers.ListField(child=serializers.CharField(), required=False, write_only=True)
    target_center_ids = serializers.ListField(child=serializers.CharField(), required=False, write_only=True)
    target_batch_names = serializers.SerializerMethodField()
    target_center_names = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source='created_by.profile.full_name', read_only=True)

    def validate(self, attrs):
        start = attrs.get('start_time')
        end = attrs.get('end_time')
        if self.instance:
            if start is None:
                start = self.instance.start_time
            if end is None:
                end = self.instance.end_time
        if start and end and start >= end:
            raise serializers.ValidationError({'end_time': 'end_time must be after start_time.'})
        return attrs

    class Meta:
        model = Notice
        fields = [
            'id',
            'organization',
            'title',
            'content',
            'target_batches',
            'target_centers',
            'target_batch_ids',
            'target_center_ids',
            'target_batch_names',
            'target_center_names',
            'is_active',
            'start_time',
            'end_time',
            'created_by',
            'created_by_name',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'organization', 'created_by', 'created_at', 'updated_at']

    def get_target_batch_names(self, obj) -> list[str]:
        return list(obj.target_batches.values_list('name', flat=True))

    def get_target_center_names(self, obj) -> list[str]:
        return list(obj.target_centers.values_list('name', flat=True))
