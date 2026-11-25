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
    permission_classes = [IsAuthenticated, IsTenantMember]

    def post(self, request, id):
        qid_raw = request.data.get('question_id') if isinstance(request.data, dict) else None
        outcome = services.save_response(
            id,
            request.user,
            qid_raw,
            request.data,
            tenant=getattr(request, 'tenant', None),
        )
        return Response(outcome.data, status=outcome.http_status)


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
