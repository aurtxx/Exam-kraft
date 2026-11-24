from rest_framework import serializers
from .models import (
    QuestionBank,
    Section,
    Tag,
    Question,
    Option,
    QuestionType,
    normalize_question_type,
)


class OptionSerializer(serializers.ModelSerializer):
    key = serializers.CharField(source='option_key', required=False)
    text = serializers.CharField(source='content_text', required=False)

    class Meta:
        model = Option
        fields = ['id', 'option_key', 'key', 'content_text', 'text', 'is_correct', 'order']
        read_only_fields = ['id']

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['key'] = instance.option_key
        ret['text'] = instance.content_text
        return ret


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'slug']
        read_only_fields = ['id']


class SectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Section
        fields = ['id', 'question_bank', 'name', 'code', 'order']
        read_only_fields = ['id']


class QuestionSerializer(serializers.ModelSerializer):
    options = OptionSerializer(many=True, required=False)
    section = serializers.CharField(source='section_name', required=False)
    cmk = serializers.FloatField(source='positive_marks', required=False)
    imk = serializers.FloatField(source='negative_marks', required=False)
    pmk = serializers.FloatField(source='partial_marks', required=False)
    canc = serializers.BooleanField(source='is_cancelled', required=False)

    class Meta:
        model = Question
        fields = [
            'id',
            'question_bank',
            'section',
            'section_name',
            'question_number',
            'question_type',
            'content_text',
            'content_html',
            'image_url',
            'explanation',
            'difficulty',
            'key',
            'positive_marks',
            'negative_marks',
            'partial_marks',
            'cmk',
            'imk',
            'pmk',
            'is_cancelled',
            'canc',
            'numerical_min',
            'numerical_max',
            'coding_language',
            'code_boilerplate',
            'test_cases',
            'options',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['section'] = instance.section_name or (instance.section.name if instance.section else 'General')
        ret['cmk'] = instance.positive_marks
        ret['imk'] = instance.negative_marks
        ret['pmk'] = instance.partial_marks
        ret['canc'] = instance.is_cancelled
        return ret


class QuestionBankSerializer(serializers.ModelSerializer):
    total_questions = serializers.SerializerMethodField()
    subjects = serializers.SerializerMethodField()

    class Meta:
        model = QuestionBank
        fields = [
            'id',
            'organization',
            'name',
            'exam_type',
            'description',
            'instructions',
            'duration_minutes',
            'is_locked',
            'total_questions',
            'subjects',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'organization', 'is_locked', 'created_at', 'updated_at']

    def get_total_questions(self, obj) -> int:
        return obj.questions.count()

    def get_subjects(self, obj) -> list[str]:
        sects = list(obj.sections.values_list('name', flat=True))
        if not sects:
            q_sects = list(obj.questions.values_list('section_name', flat=True).distinct())
            return [s for s in q_sects if s]
        return sects
