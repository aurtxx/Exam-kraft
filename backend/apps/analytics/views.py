import csv

from django.db import transaction
from django.db.models import Avg, Count, Max, Min, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsOrgAdminOrFaculty, IsTenantMember
from apps.engine.models import AttemptStatus
from apps.examinations.models import Examination

from .models import QuestionResponseReview, Result, SectionScore
from .serializers import RankSerializer, ResultSerializer, ScorecardSerializer
from .services import FINAL_STATUSES, cohort_results, evaluate_examination


class StudentResultsView(ListAPIView):
    permission_classes = [IsAuthenticated, IsTenantMember]
    serializer_class = ResultSerializer

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'student': True}

    def get_queryset(self):
        return Result.objects.select_related('attempt__examination').filter(
            attempt__user=self.request.user,
            attempt__examination__organization_id=self.request.user.organization_id,
            attempt__examination__hide_results=False,
            attempt__status__in=FINAL_STATUSES,
            is_published=True,
        ).order_by('-evaluated_at', 'pk')


class StudentResultView(StudentResultsView, RetrieveAPIView):
    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)


class StudentScorecardView(StudentResultView):
    serializer_class = ScorecardSerializer

    def retrieve(self, request, *args, **kwargs):
        result = self.get_object()
        return Response(self.get_serializer(result.scorecard).data)

    def get_queryset(self):
        return super().get_queryset().filter(
            attempt__examination__hide_analytics=False,
        ).select_related('scorecard').prefetch_related('scorecard__sections__reviews')


class ScorecardDownloadView(StudentScorecardView):
    def retrieve(self, request, *args, **kwargs):
        result = self.get_object()
        data = self.get_serializer(result.scorecard).data
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="scorecard-{result.pk}.csv"'
        writer = csv.writer(response)
        writer.writerow(['Total score', 'Maximum score', 'Percentage', 'Rank', 'Percentile'])
        summary = data['result']
        writer.writerow([
            summary['total_score'], summary['maximum_score'], data['score_percentage'],
            summary['rank'], summary['percentile'],
        ])
        writer.writerow([])
        writer.writerow(['Section', 'Score', 'Maximum score'])
        for section in data['sections']:
            title = section['title']
            if title.lstrip().startswith(('=', '+', '-', '@')) or title.startswith(('\t', '\r', '\n')):
                title = "'" + title
            writer.writerow([title, section['score'], section['maximum_score']])
        return response


class StaffExaminationView(APIView):
    permission_classes = [IsAuthenticated, IsTenantMember, IsOrgAdminOrFaculty]

    def get_examination(self, exam_id, *, lock=False):
        queryset = Examination.all_objects.all()
        if not self.request.user.is_superadmin:
            queryset = queryset.filter(organization_id=self.request.user.organization_id)
        elif getattr(self.request, 'tenant', None):
            queryset = queryset.filter(organization=self.request.tenant)
        if lock:
            queryset = queryset.select_for_update()
        return get_object_or_404(queryset, pk=exam_id)


class EvaluateExaminationView(StaffExaminationView):
    def post(self, request, exam_id):
        exam = self.get_examination(exam_id)
        return Response({'evaluated_count': evaluate_examination(exam.pk)})


class PublishResultsView(StaffExaminationView):
    @transaction.atomic
    def post(self, request, exam_id):
        exam = self.get_examination(exam_id, lock=True)
        pending = exam.attempts.filter(
            status=AttemptStatus.IN_PROGRESS, user__organization_id=exam.organization_id,
        ).exists()
        if pending or (exam.end_window and timezone.now() < exam.end_window):
            return Response(
                {'detail': 'The examination window must be over and all attempts submitted.'},
                status=status.HTTP_409_CONFLICT,
            )
        evaluate_examination(exam.pk)
        published = cohort_results(exam).update(is_published=True)
        return Response({'published_count': published})


class RankListView(StaffExaminationView):
    def get(self, request, exam_id):
        exam = self.get_examination(exam_id)
        results = cohort_results(exam).select_related('attempt__user', 'attempt__examination').order_by('rank', 'pk')
        return Response(RankSerializer(results, many=True).data)


class ExaminationReportView(StaffExaminationView):
    def get(self, request, exam_id):
        exam = self.get_examination(exam_id)
        results = cohort_results(exam)
        summary = results.aggregate(
            candidates=Count('pk'), mean=Avg('total_score'), highest=Max('total_score'), lowest=Min('total_score'),
        )
        distribution = results.values('total_score').annotate(candidates=Count('pk')).order_by('total_score')
        sections = SectionScore.objects.filter(scorecard__result__in=results).values('title', 'order').annotate(
            mean=Avg('score'), highest=Max('score'), lowest=Min('score'),
        ).order_by('order', 'title')
        outcomes = QuestionResponseReview.Outcome
        questions = QuestionResponseReview.objects.filter(
            section__scorecard__result__in=results, question__isnull=False,
        ).values('question_id').annotate(
            correct=Count('pk', filter=Q(outcome=outcomes.CORRECT)),
            partial=Count('pk', filter=Q(outcome=outcomes.PARTIAL)),
            incorrect=Count('pk', filter=Q(outcome=outcomes.INCORRECT)),
            unanswered=Count('pk', filter=Q(outcome=outcomes.UNANSWERED)),
            mean_time_seconds=Avg('time_spent_seconds'),
        ).order_by('question_id')
        return Response({
            'summary': summary,
            'score_distribution': list(distribution),
            'sections': list(sections),
            'questions': list(questions),
        })
