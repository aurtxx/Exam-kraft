from django.utils import timezone
from rest_framework import serializers

from .models import QuestionResponseReview, Result, Scorecard, SectionScore


class ResultSerializer(serializers.ModelSerializer):
    examination_id = serializers.UUIDField(source='attempt.examination_id')
    examination_name = serializers.CharField(source='attempt.examination.name')

    class Meta:
        model = Result
        fields = (
            'id', 'attempt', 'examination_id', 'examination_name', 'total_score',
            'maximum_score', 'penalty', 'rank', 'percentile', 'evaluated_at',
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        is_student = self.context.get('student', False)
        if request and getattr(request.user, 'role', None) == 'STUDENT':
            is_student = True

        if is_student and instance.attempt.examination.hide_rank:
            data['rank'] = data['percentile'] = None
        return data


class RankSerializer(ResultSerializer):
    candidate_id = serializers.UUIDField(source='attempt.user_id')
    username = serializers.CharField(source='attempt.user.username')

    class Meta(ResultSerializer.Meta):
        fields = ResultSerializer.Meta.fields + ('candidate_id', 'username', 'is_published')


class QuestionReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionResponseReview
        fields = (
            'question', 'selected_options', 'submitted_value', 'answer', 'explanation',
            'outcome', 'marks', 'time_spent_seconds',
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        is_student = self.context.get('student', False)
        if request and getattr(request.user, 'role', None) == 'STUDENT':
            is_student = True

        if is_student:
            try:
                exam = instance.section.scorecard.result.attempt.examination
                policy = getattr(exam, 'answer_reveal_policy', 'IMMEDIATELY')
                hide = False
                if policy == 'NEVER':
                    hide = True
                elif policy == 'AFTER_CLOSE':
                    now = timezone.now()
                    is_past = (exam.end_window and now >= exam.end_window) or exam.status in ('CLOSED', 'EVALUATED')
                    if not is_past:
                        hide = True
                if hide:
                    data['answer'] = []
                    data['explanation'] = ''
            except Exception:
                pass
        return data


class SectionScoreSerializer(serializers.ModelSerializer):
    reviews = QuestionReviewSerializer(many=True)

    class Meta:
        model = SectionScore
        fields = ('title', 'order', 'score', 'maximum_score', 'reviews')


class ScorecardSerializer(serializers.ModelSerializer):
    result = ResultSerializer()
    sections = SectionScoreSerializer(many=True)

    class Meta:
        model = Scorecard
        fields = ('result', 'score_percentage', 'passed', 'sections')

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        is_student = self.context.get('student', False)
        if request and getattr(request.user, 'role', None) == 'STUDENT':
            is_student = True

        exam = getattr(instance.result.attempt, 'examination', None)
        if is_student and exam and exam.hide_analytics:
            data['sections'] = []
        return data
