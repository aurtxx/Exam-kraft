from rest_framework import serializers
from .models import (
    Examination,
    ExaminationSection,
    ExaminationQuestion,
    CandidateAssignment,
    ExaminationStatus,
)
from apps.question_bank.models import QuestionBank
from apps.question_bank.serializers import QuestionSerializer


class ExaminationSectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExaminationSection
        fields = [
            'id',
            'exam',
            'title',
            'order',
            'total_questions',
            'marks_per_question',
            'negative_marks',
            'partial_marks',
        ]
        read_only_fields = ['id']


class ExaminationSerializer(serializers.ModelSerializer):
    sections = ExaminationSectionSerializer(many=True, read_only=True)
    question_paper_id = serializers.UUIDField(required=False, write_only=True, allow_null=True)
    assigned_groups = serializers.SerializerMethodField()
    assigned_centres = serializers.SerializerMethodField()

    class Meta:
        model = Examination
        fields = [
            'id',
            'organization',
            'name',
            'code',
            'slug',
            'question_paper',
            'question_paper_id',
            'instructions',
            'duration_minutes',
            'total_marks',
            'passing_marks',
            'status',
            'start_window',
            'end_window',
            'shuffle_questions',
            'shuffle_options',
            'camera_proctoring',
            'max_window_switches',
            'allow_section_skip',
            'practice_mode',
            'pc_only',
            'hide_results',
            'hide_rank',
            'hide_analytics',
            'short_url',
            'sections',
            'assigned_groups',
            'assigned_centres',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'organization', 'status', 'created_at', 'updated_at']
        extra_kwargs = {'duration_minutes': {'min_value': 1, 'max_value': 1440}}

    def validate(self, attrs):
        start_window = attrs.get('start_window', getattr(self.instance, 'start_window', None))
        end_window = attrs.get('end_window', getattr(self.instance, 'end_window', None))
        if start_window is not None and end_window is not None and start_window >= end_window:
            raise serializers.ValidationError({'end_window': 'Must be later than start_window.'})
        return attrs

    def validate_question_paper(self, paper):
        self.validate_question_paper_id(paper.pk if paper else None)
        return paper

    def validate_question_paper_id(self, paper_id):
        if paper_id and self.instance and not QuestionBank.all_objects.filter(
            pk=paper_id, organization_id=self.instance.organization_id
        ).exists():
            raise serializers.ValidationError('Unknown question paper.')
        if self.instance and self.instance.status == ExaminationStatus.PUBLISHED:
            if paper_id != self.instance.question_paper_id:
                raise serializers.ValidationError('Cannot change the question paper of a published examination.')
        return paper_id

    def get_assigned_groups(self, obj) -> list[str]:
        return list(obj.candidate_assignments.filter(batch__isnull=False).values_list('batch__name', flat=True))

    def get_assigned_centres(self, obj) -> list[str]:
        return list(obj.candidate_assignments.filter(center__isnull=False).values_list('center__name', flat=True))

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        if instance.question_paper:
            ret['question_paper_id'] = str(instance.question_paper_id)
        return ret


class CandidateAssignmentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.profile.full_name', read_only=True)
    batch_name = serializers.CharField(source='batch.name', read_only=True)
    center_name = serializers.CharField(source='center.name', read_only=True)

    class Meta:
        model = CandidateAssignment
        fields = [
            'id',
            'exam',
            'student',
            'student_name',
            'batch',
            'batch_name',
            'center',
            'center_name',
            'assigned_at',
        ]
        read_only_fields = ['id', 'assigned_at']
