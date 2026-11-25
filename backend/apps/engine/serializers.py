import json
from rest_framework import serializers
from .models import (
    ExaminationAttempt,
    AttemptResponse,
    ProctoringEventType,
    ProctoringLog,
    ResponseStatus,
    normalize_response_status,
)
from apps.question_bank.models import Question, Option


class DeliveryOptionSerializer(serializers.ModelSerializer):
    """Sanitized option serializer for CBT candidate delivery (strictly excludes is_correct)."""
    key = serializers.CharField(source='option_key')
    text = serializers.CharField(source='content_text')

    class Meta:
        model = Option
        fields = ['id', 'key', 'text', 'content_text', 'content_html', 'order']


class DeliveryQuestionSerializer(serializers.ModelSerializer):
    """Sanitized question serializer for CBT candidate delivery (strictly excludes answer key and explanation)."""
    options = serializers.SerializerMethodField()
    section_name = serializers.CharField(read_only=True)

    class Meta:
        model = Question
        fields = [
            'id',
            'section_name',
            'question_number',
            'question_type',
            'content_text',
            'content_html',
            'image_url',
            'difficulty',
            'positive_marks',
            'negative_marks',
            'partial_marks',
            'coding_language',
            'code_boilerplate',
            'options',
        ]

    def get_options(self, obj):
        options_qs = obj.options.all().order_by('order', 'option_key')
        return DeliveryOptionSerializer(options_qs, many=True).data


class AttemptResponseSerializer(serializers.ModelSerializer):
    question_id = serializers.PrimaryKeyRelatedField(
        queryset=Question.objects.none(),
        source='question'
    )

    class Meta:
        model = AttemptResponse
        fields = [
            'id',
            'question_id',
            'selected_options',
            'numerical_value',
            'status',
            'saved_at',
            'time_spent_seconds',
        ]
        read_only_fields = ['id', 'saved_at']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        examination = self.context.get('examination') if hasattr(self, 'context') else None
        if examination is not None:
            from .services import scoped_exam_questions
            self.fields['question_id'].queryset = scoped_exam_questions(examination)

    def validate_status(self, value):
        return normalize_response_status(value)


class ExaminationAttemptSerializer(serializers.ModelSerializer):
    remaining_seconds = serializers.IntegerField(read_only=True)

    class Meta:
        model = ExaminationAttempt
        fields = [
            'id',
            'attempt_token',
            'user',
            'examination',
            'started_at',
            'server_deadline',
            'submitted_at',
            'status',
            'tab_switch_count',
            'remaining_seconds',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'attempt_token',
            'user',
            'examination',
            'started_at',
            'server_deadline',
            'submitted_at',
            'created_at',
            'updated_at',
        ]


class ProctoringLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProctoringLog
        fields = [
            'id',
            'attempt',
            'event_type',
            'timestamp',
            'details',
        ]
        read_only_fields = ['id', 'timestamp']


class ProctoringEventInputSerializer(serializers.Serializer):
    event_type = serializers.ChoiceField(
        choices=ProctoringEventType.choices,
        default=ProctoringEventType.TAB_SWITCH,
        required=False,
        allow_null=False,
    )
    details = serializers.DictField(
        default=dict,
        required=False,
        allow_null=False,
    )

    def validate_details(self, value):
        if len(value) > 20:
            raise serializers.ValidationError("Too many keys in details payload (max 20).")
        for k, v in value.items():
            if not isinstance(k, str) or len(k) > 64:
                raise serializers.ValidationError("Detail keys must be strings <= 64 characters.")
            if isinstance(v, (dict, list)):
                raise serializers.ValidationError("Nested objects/arrays are not permitted in details.")
        raw_bytes = len(json.dumps(value, separators=(',', ':'), ensure_ascii=False).encode('utf-8'))
        if raw_bytes > 4096:
            raise serializers.ValidationError("Details payload exceeds 4096 bytes.")
        return value
