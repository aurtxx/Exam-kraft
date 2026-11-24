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
        if self.context.get('student') and instance.attempt.examination.hide_rank:
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
