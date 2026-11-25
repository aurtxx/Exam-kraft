import uuid
from datetime import timedelta
from collections import defaultdict

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import (
    ExaminationAttempt,
    AttemptResponse,
    ProctoringLog,
    AttemptStatus,
    ResponseStatus,
    ProctoringEventType,
    normalize_response_status,
)
from . import services
from .services import build_attempt_payload
from apps.accounts.permissions import IsTenantMember
from apps.question_bank.models import Question


class StartAttemptView(APIView):
    permission_classes = [IsAuthenticated, IsTenantMember]

    def post(self, request, id=None):
        exam_id = id or request.data.get('exam_id')
        outcome = services.start_attempt(
            request.user,
            exam_id,
            tenant=getattr(request, 'tenant', None),
        )
        return Response(outcome.data, status=outcome.http_status)


class HeartbeatView(APIView):
    permission_classes = [IsAuthenticated, IsTenantMember]

    def post(self, request, id):
        blur_count = request.data.get('window_blur_count', 0)
        outcome = services.heartbeat_attempt(
            id,
            request.user,
            blur_count_raw=blur_count,
            tenant=getattr(request, 'tenant', None),
        )
        return Response(outcome.data, status=outcome.http_status)


class SaveResponseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        try:
            attempt = ExaminationAttempt.objects.select_related('examination').get(id=id)
        except (ExaminationAttempt.DoesNotExist, ValueError):
            return Response({
                'status': 'ERROR',
                'code': 'ATTEMPT_NOT_FOUND',
                'message': 'Attempt not found.'
            }, status=status.HTTP_404_NOT_FOUND)

        if attempt.user != request.user and not request.user.is_staff:
            return Response({
                'status': 'ERROR',
                'code': 'UNAUTHORIZED',
                'message': 'You do not have permission to access this attempt.'
            }, status=status.HTTP_403_FORBIDDEN)

        # Locked attempt check
        if attempt.status in (AttemptStatus.SUBMITTED, AttemptStatus.AUTO_SUBMITTED):
            return Response({
                'status': 'ERROR',
                'code': 'ATTEMPT_LOCKED',
                'message': 'Attempt is locked and submitted.'
            }, status=status.HTTP_403_FORBIDDEN)

        now = timezone.now()
        # Late submission after deadline + 30s grace period
        if now > (attempt.server_deadline + timedelta(seconds=30)):
            attempt.status = AttemptStatus.AUTO_SUBMITTED
            attempt.submitted_at = now
            attempt.save(update_fields=['status', 'submitted_at', 'updated_at'])
            return Response({
                'status': 'ERROR',
                'code': 'DEADLINE_EXPIRED',
                'message': 'Response rejected: Server deadline + grace period has expired.'
            }, status=status.HTTP_403_FORBIDDEN)

        data = request.data
        qid_raw = data.get('question_id')
        if not qid_raw:
            return Response({
                'status': 'ERROR',
                'code': 'INVALID_PAYLOAD',
                'message': 'question_id is required.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Lookup question
        question = None
        try:
            # Check UUID or question_number
            try:
                qid_uuid = uuid.UUID(str(qid_raw))
                question = Question.objects.filter(id=qid_uuid).first()
            except ValueError:
                pass
            if not question:
                # Try question_number
                question = Question.objects.filter(question_number=int(qid_raw)).first()
            if not question:
                # Try raw pk if pk is numeric/other
                question = Question.objects.filter(pk=qid_raw).first()
        except Exception:
            question = None

        if not question:
            return Response({
                'status': 'ERROR',
                'code': 'QUESTION_NOT_FOUND',
                'message': f'Question {qid_raw} not found.'
            }, status=status.HTTP_404_NOT_FOUND)

        selected_options = data.get('selected_options', [])
        numerical_value = data.get('numerical_value')
        status_input = data.get('status')
        time_spent = data.get('time_spent_seconds', 0)
        try:
            time_spent = int(time_spent)
        except (ValueError, TypeError):
            time_spent = 0

        if status_input:
            resp_status = normalize_response_status(status_input)
        else:
            if selected_options or (numerical_value is not None and str(numerical_value).strip() != ''):
                resp_status = ResponseStatus.ANSWERED
            else:
                resp_status = ResponseStatus.UNANSWERED

        response_obj, _ = AttemptResponse.objects.update_or_create(
            attempt=attempt,
            question=question,
            defaults={
                'selected_options': selected_options,
                'numerical_value': str(numerical_value) if numerical_value is not None else None,
                'status': resp_status,
                'time_spent_seconds': time_spent,
            }
        )

        rem_secs = max(0, int((attempt.server_deadline - now).total_seconds()))

        return Response({
            'status': 'SUCCESS',
            'saved_at': response_obj.saved_at.isoformat(),
            'question_id': qid_raw,
            'remaining_seconds': rem_secs,
        }, status=status.HTTP_200_OK)


class SubmitAttemptView(APIView):
    permission_classes = [IsAuthenticated, IsTenantMember]

    def post(self, request, id):
        reason = request.data.get('submission_reason', 'MANUAL_SUBMIT') if isinstance(request.data, dict) else 'MANUAL_SUBMIT'
        outcome = services.submit_attempt(
            id,
            request.user,
            reason=reason,
            tenant=getattr(request, 'tenant', None),
        )
        return Response(outcome.data, status=outcome.http_status)


class ResumeAttemptView(APIView):
    permission_classes = [IsAuthenticated, IsTenantMember]

    def get(self, request, id):
        outcome = services.resume_attempt(
            id,
            request.user,
            tenant=getattr(request, 'tenant', None),
        )
        return Response(outcome.data, status=outcome.http_status)


class ProctoringEventView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        try:
            attempt = ExaminationAttempt.objects.select_related('examination').get(id=id)
        except (ExaminationAttempt.DoesNotExist, ValueError):
            return Response({
                'status': 'ERROR',
                'code': 'ATTEMPT_NOT_FOUND',
                'message': 'Attempt not found.'
            }, status=status.HTTP_404_NOT_FOUND)

        if attempt.user != request.user and not request.user.is_staff:
            return Response({
                'status': 'ERROR',
                'code': 'UNAUTHORIZED',
                'message': 'You do not have permission to access this attempt.'
            }, status=status.HTTP_403_FORBIDDEN)

        event_type = request.data.get('event_type', ProctoringEventType.TAB_SWITCH)
        details = request.data.get('details', {})

        ProctoringLog.objects.create(
            attempt=attempt,
            event_type=event_type,
            details=details
        )

        if event_type in (ProctoringEventType.TAB_SWITCH, ProctoringEventType.WINDOW_BLUR):
            attempt.tab_switch_count += 1
            max_switches = getattr(attempt.examination, 'max_window_switches', 3) or 3
            if attempt.tab_switch_count > max_switches and attempt.status == AttemptStatus.IN_PROGRESS:
                attempt.status = AttemptStatus.AUTO_SUBMITTED
                attempt.submitted_at = timezone.now()
            attempt.save(update_fields=['tab_switch_count', 'status', 'submitted_at', 'updated_at'])

        max_switches = getattr(attempt.examination, 'max_window_switches', 3) or 3
        return Response({
            'status': 'SUCCESS',
            'tab_switch_count': attempt.tab_switch_count,
            'max_allowed': max_switches,
            'auto_submitted': attempt.status == AttemptStatus.AUTO_SUBMITTED,
        }, status=status.HTTP_200_OK)
