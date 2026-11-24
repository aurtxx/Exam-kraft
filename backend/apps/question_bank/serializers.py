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


def mcq_options_error(question_type, correctness):
    if question_type in (QuestionType.MCQ_SINGLE, QuestionType.MCQ_MULTI):
        if len(correctness) < 2:
            return 'MISSING_OPTIONS', 'Multiple choice questions require at least two options.'
        if not any(correctness):
            return 'MISSING_CORRECT_OPTION', 'Multiple choice questions require at least one correct option.'
        if question_type == QuestionType.MCQ_SINGLE and sum(correctness) > 1:
            return 'MULTIPLE_CORRECT_OPTIONS', 'Single correct MCQs require exactly one correct option.'
    return None


def prepare_options(question_type, key, options):
    correct_keys = set()
    if question_type == QuestionType.MCQ_SINGLE:
        if key and not any('is_correct' in option for option in options):
            correct_keys = {key.strip().upper()}
    elif question_type == QuestionType.MCQ_MULTI and key:
        correct_keys = {part.strip().upper() for part in key.replace(',', '+').split('+')}

    prepared = []
    for index, option in enumerate(options):
        option_key = option.get('option_key') or chr(65 + index)
        prepared.append({
            **option,
            'option_key': option_key,
            'content_text': option.get('content_text', ''),
            'order': option.get('order', index),
            'is_correct': option.get('is_correct', False) or option_key.strip().upper() in correct_keys,
        })
    return prepared


class OptionSerializer(serializers.ModelSerializer):
    key = serializers.CharField(source='option_key', required=False, max_length=10)
    text = serializers.CharField(source='content_text', required=False)

    class Meta:
        model = Option
        fields = ['id', 'option_key', 'key', 'content_text', 'text', 'content_html', 'is_correct', 'order']
        read_only_fields = ['id']

    def get_fields(self):
        fields = super().get_fields()
        for name in ('option_key', 'content_text'):
            fields[name].required = False
        return fields

    def validate(self, attrs):
        if not attrs.get('content_text', '').strip():
            raise serializers.ValidationError({'text': 'Option content must not be empty.'})
        return attrs

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


class QuestionTypeField(serializers.ChoiceField):
    def to_internal_value(self, data):
        return super().to_internal_value(normalize_question_type(data) if data else data)


class QuestionSerializer(serializers.ModelSerializer):
    options = OptionSerializer(many=True, required=False)
    question_type = QuestionTypeField(choices=QuestionType.choices, required=False)
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

    def validate(self, attrs):
        instance = self.instance
        positive = attrs.get('positive_marks', instance.positive_marks if instance else 4.0)
        negative = attrs.get('negative_marks', instance.negative_marks if instance else 0.0)
        if not negative <= positive:
            raise serializers.ValidationError({'imk': 'Negative penalty cannot exceed positive marks.'})

        question_type = attrs.get('question_type', instance.question_type if instance else None)
        key = attrs.get('key', instance.key if instance else '')
        if 'options' in attrs:
            options = prepare_options(question_type, key, attrs['options'])
            attrs['options'] = options
        else:
            options = list(instance.options.values('option_key', 'content_text', 'is_correct')) if instance else []
            if any(not option['content_text'].strip() for option in options):
                raise serializers.ValidationError({'options': 'Option content must not be empty.'})
            if question_type == QuestionType.MCQ_SINGLE and 'key' in attrs:
                for option in options:
                    option['is_correct'] = option['option_key'].strip().upper() == key.strip().upper()
        correctness = [option['is_correct'] for option in options]
        error = mcq_options_error(question_type, correctness)
        if error:
            raise serializers.ValidationError({'options': error[1]})
        if question_type == QuestionType.MCQ_SINGLE:
            attrs['key'] = next(option['option_key'] for option in options if option['is_correct'])
        return attrs

    def update(self, instance, validated_data):
        options = validated_data.pop('options', None)
        instance = super().update(instance, validated_data)
        if options is not None:
            instance.options.all().delete()
            Option.objects.bulk_create(Option(question=instance, **option) for option in options)
        elif instance.question_type == QuestionType.MCQ_SINGLE and 'key' in self.initial_data:
            instance.options.exclude(option_key=instance.key).filter(is_correct=True).update(is_correct=False)
            instance.options.filter(option_key=instance.key, is_correct=False).update(is_correct=True)
        return instance

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
