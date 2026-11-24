import csv
from decimal import Decimal

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
from apps.engine.models import AttemptStatus, ExaminationAttempt
from apps.examinations.models import Examination, ExaminationStatus

from .models import QuestionResponseReview, Result, Scorecard, SectionScore
from .serializers import (
    QuestionReviewSerializer,
    RankSerializer,
    ResultSerializer,
    ScorecardSerializer,
    SectionScoreSerializer,
)
from .services import (
    FINAL_STATUSES,
    build_examination_summary,
    cohort_results,
    evaluate_examination,
)


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
        for section in data.get('sections', []):
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
        count = evaluate_examination(exam.pk)
        summary = build_examination_summary(exam)
        return Response({
            'status': 'SUCCESS',
            'message': 'Evaluation completed.',
            'evaluated_count': count,
            'summary': summary,
        })


class ExaminationResultsView(StaffExaminationView):
    def get(self, request, exam_id):
        exam = self.get_examination(exam_id)
        # Evaluate if there are unevaluated attempts
        pending = ExaminationAttempt.objects.filter(
            examination=exam,
            status__in=FINAL_STATUSES,
            result__isnull=True,
        ).exists()
        if pending:
            evaluate_examination(exam.pk)

        summary = build_examination_summary(exam)
        results = cohort_results(exam)
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
            'status': 'SUCCESS',
            'exam_id': str(exam.pk),
            'summary': summary,
            'results': summary,
            'rankings': summary['rankings'],
            'score_distribution': list(distribution),
            'sections': list(sections),
            'questions': list(questions),
        })


class AttemptReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        queryset = ExaminationAttempt.objects.select_related('examination', 'user__profile')
        attempt = get_object_or_404(queryset, pk=id)

        # Tenant & user isolation checks
        is_staff = request.user.is_superadmin or (
            (request.user.is_staff or request.user.role in ('ORG_ADMIN', 'FACULTY')) and
            request.user.organization_id == attempt.examination.organization_id
        )
        is_owner = (attempt.user_id == request.user.id)

        if not (is_staff or is_owner):
            return Response({'status': 'ERROR', 'code': 'FORBIDDEN'}, status=status.HTTP_403_FORBIDDEN)

        if attempt.status not in FINAL_STATUSES:
            return Response(
                {'status': 'ERROR', 'code': 'ATTEMPT_NOT_SUBMITTED', 'detail': 'Attempt has not been submitted yet.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        exam = attempt.examination
        is_student = not is_staff
        now = timezone.now()
        is_window_closed = (
            (exam.end_window is not None and now >= exam.end_window)
            or exam.status in (ExaminationStatus.CLOSED, ExaminationStatus.EVALUATED)
        )

        if is_student:
            if exam.hide_results:
                return Response(
                    {'status': 'ERROR', 'code': 'RESULTS_HIDDEN', 'detail': 'Results are hidden by administrator.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            result = Result.objects.filter(attempt=attempt).first()
            if result is None or not result.is_published or not is_window_closed:
                return Response(
                    {
                        'status': 'ERROR',
                        'code': 'RESULTS_NOT_PUBLISHED',
                        'error': 'RESULTS_NOT_PUBLISHED',
                        'detail': 'Examination results have not been published yet.',
                        'message': 'Examination results have not been published yet.',
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
        else:
            # Evaluate on demand for staff callers if result not yet generated
            if not hasattr(attempt, 'result'):
                evaluate_examination(exam.pk)
                attempt.refresh_from_db()
            result = attempt.result

        scorecard = result.scorecard
        sections = scorecard.sections.all().prefetch_related('reviews__question__options')

        sec_scores = {}
        total_correct = 0
        total_incorrect = 0
        total_unanswered = 0
        reviews_list = []

        policy = getattr(exam, 'answer_reveal_policy', 'IMMEDIATELY')
        hide_answers = False
        if is_student:
            if policy == 'NEVER':
                hide_answers = True
            elif policy == 'AFTER_CLOSE':
                if not is_window_closed:
                    hide_answers = True

        for sec in sections:
            sec_scores[sec.title] = {
                'score': float(sec.score),
                'maximum_score': float(sec.maximum_score),
                'order': sec.order,
            }
            for rev in sec.reviews.all():
                is_corr = rev.outcome in (QuestionResponseReview.Outcome.CORRECT, QuestionResponseReview.Outcome.CANCELLED)
                is_inc = rev.outcome == QuestionResponseReview.Outcome.INCORRECT
                is_unans = rev.outcome == QuestionResponseReview.Outcome.UNANSWERED
                if is_corr:
                    total_correct += 1
                if is_inc:
                    total_incorrect += 1
                if is_unans:
                    total_unanswered += 1

                reviews_list.append({
                    'question_id': rev.question_id,
                    'section': sec.title,
                    'marks_awarded': float(rev.marks),
                    'is_correct': is_corr,
                    'is_attempted': not is_unans,
                    'outcome': rev.outcome,
                    'selected_options': rev.selected_options,
                    'submitted_value': rev.submitted_value,
                    'answer': [] if hide_answers else rev.answer,
                    'explanation': '' if hide_answers else rev.explanation,
                    'time_spent_seconds': rev.time_spent_seconds,
                })

        user_rank = result.rank if not (is_student and exam.hide_rank) else None
        user_percentile = float(result.percentile) if result.percentile is not None and not (is_student and exam.hide_rank) else None

        report_summary = {
            'attempt_id': str(attempt.pk),
            'candidate_id': str(attempt.user_id),
            'candidate_name': attempt.user.get_full_name() or attempt.user.username,
            'total_score': float(result.total_score),
            'maximum_score': float(result.maximum_score),
            'penalty': float(result.penalty),
            'score_percentage': float(scorecard.score_percentage),
            'passed': scorecard.passed,
            'rank': user_rank,
            'percentile': user_percentile,
            'total_correct': total_correct,
            'total_incorrect': total_incorrect,
            'total_unanswered': total_unanswered,
            'section_scores': sec_scores,
            'question_reviews': reviews_list,
        }

        context = {'request': request, 'student': is_student}
        return Response({
            'status': 'SUCCESS',
            'attempt_id': str(attempt.pk),
            'exam_id': str(exam.pk),
            'exam_name': exam.name,
            'report': report_summary,
            'result': ResultSerializer(result, context=context).data,
            'scorecard': ScorecardSerializer(scorecard, context=context).data,
            'sections': SectionScoreSerializer(sections, many=True, context=context).data,
            'reviews': reviews_list,
        })


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
