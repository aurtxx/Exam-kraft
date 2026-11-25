from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from . import services
from .services import build_attempt_payload
from apps.accounts.permissions import IsTenantMember


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
    permission_classes = [IsAuthenticated, IsTenantMember]

    def post(self, request, id):
        outcome = services.record_proctoring_event(
            id,
            request.user,
            request.data,
            tenant=getattr(request, 'tenant', None),
        )
        return Response(outcome.data, status=outcome.http_status)
