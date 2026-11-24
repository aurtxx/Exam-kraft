import uuid
from datetime import timedelta
from collections import defaultdict

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
from .serializers import DeliveryQuestionSerializer
from apps.examinations.models import Examination, ExaminationStatus
from apps.question_bank.models import Question


def build_attempt_payload(attempt: ExaminationAttempt, is_recovered: bool = False):
    """Constructs complete CBT attempt session payload including sections, questions, responses, and palette."""
    exam = attempt.examination
    now = timezone.now()
    if not is_recovered:
        remaining_secs = max(0, int(round((attempt.server_deadline - attempt.started_at).total_seconds())))
    else:
        remaining_secs = max(0, int(round((attempt.server_deadline - now).total_seconds())))

    # Gather questions
    # 1. From ExaminationSections if present
    sections_data = []
    question_map = {}
    total_q_count = 0

    exam_sections = exam.sections.all().order_by('order')
    if exam_sections.exists():
        for sec in exam_sections:
            eq_qs = sec.exam_questions.all().order_by('order')
            sec_qids = []
            sec_questions = []
            for eq in eq_qs:
                q = eq.question
                question_map[str(q.id)] = q
                sec_qids.append(q.id)
                sec_questions.append(DeliveryQuestionSerializer(q).data)

            sections_data.append({
                'id': str(sec.id),
                'name': sec.title,
                'title': sec.title,
                'order': sec.order,
                'total_questions': len(sec_qids),
                'question_ids': sec_qids,
                'questions': sec_questions,
            })
            total_q_count += len(sec_qids)

    # 2. If no sections directly on exam, check exam.question_paper
    if not sections_data and exam.question_paper:
        paper_questions = exam.question_paper.questions.all().order_by('question_number', 'created_at')
        grouped = defaultdict(list)
        for q in paper_questions:
            s_name = q.section_name or (q.section.name if q.section else 'General')
            grouped[s_name].append(q)
            question_map[str(q.id)] = q

        order_idx = 1
        for s_name, q_list in grouped.items():
            sec_qids = [q.id for q in q_list]
            sec_questions = [DeliveryQuestionSerializer(q).data for q in q_list]
            sections_data.append({
                'id': f"sec-{order_idx}",
                'name': s_name,
                'title': s_name,
                'order': order_idx,
                'total_questions': len(sec_qids),
                'question_ids': sec_qids,
                'questions': sec_questions,
            })
            total_q_count += len(sec_qids)
            order_idx += 1

    # Fetch existing responses
    responses_qs = attempt.responses.all()
    existing_responses = {}
    answered_count = 0
    unanswered_count = 0
    marked_count = 0
    answered_marked_count = 0

    for r in responses_qs:
        qid_key = str(r.question_id)
        existing_responses[qid_key] = {
            'question_id': r.question_id,
            'selected_options': r.selected_options or [],
            'numerical_value': r.numerical_value,
            'status': r.status,
            'time_spent_seconds': r.time_spent_seconds,
            'saved_at': r.saved_at.isoformat() if r.saved_at else None,
        }
        # Counters
        if r.status == ResponseStatus.ANSWERED:
            answered_count += 1
        elif r.status == ResponseStatus.MARKED_FOR_REVIEW:
            marked_count += 1
        elif r.status == ResponseStatus.ANSWERED_AND_MARKED:
            answered_marked_count += 1
        elif r.status == ResponseStatus.UNANSWERED:
            unanswered_count += 1

    visited_count = len(existing_responses)
    not_visited_count = max(0, total_q_count - visited_count)
    if not is_recovered and visited_count == 0:
        unanswered_count = total_q_count

    palette_summary = {
        'answered': answered_count,
        'unanswered': unanswered_count,
        'marked_for_review': marked_count,
        'answered_marked_for_review': answered_marked_count,
        'not_visited': not_visited_count,
    }

    return {
        'status': 'SUCCESS',
        'attempt_id': str(attempt.id),
        'attempt_token': str(attempt.attempt_token),
        'started_at': attempt.started_at.isoformat(),
        'server_deadline': attempt.server_deadline.isoformat(),
        'remaining_seconds': remaining_secs,
        'sections': sections_data,
        'existing_responses': existing_responses,
        'palette_summary': palette_summary,
        'is_recovered': is_recovered,
        'exam': {
            'id': str(exam.id),
            'name': exam.name,
            'duration_minutes': exam.duration_minutes,
            'total_marks': float(exam.total_marks),
            'instructions': exam.instructions,
            'camera_proctoring': exam.camera_proctoring,
            'max_window_switches': exam.max_window_switches,
            'allow_section_skip': exam.allow_section_skip,
        }
    }


class StartAttemptView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, id=None):
        exam_id = id or request.data.get('exam_id')
        if not exam_id:
            return Response({
                'status': 'ERROR',
                'code': 'EXAM_NOT_FOUND',
                'message': 'Examination ID is required.'
            }, status=status.HTTP_404_NOT_FOUND)

        try:
            exam = Examination.objects.get(id=exam_id)
        except (Examination.DoesNotExist, ValueError):
            return Response({
                'status': 'ERROR',
                'code': 'EXAM_NOT_FOUND',
                'message': f'Examination {exam_id} not found.'
            }, status=status.HTTP_404_NOT_FOUND)

        now = timezone.now()

        # Window validation
        if exam.start_window and now < exam.start_window:
            return Response({
                'status': 'ERROR',
                'code': 'EXAM_NOT_STARTED',
                'message': 'Examination has not started yet.'
            }, status=status.HTTP_403_FORBIDDEN)

        if exam.end_window and now > exam.end_window:
            return Response({
                'status': 'ERROR',
                'code': 'EXAM_EXPIRED',
                'message': 'Examination window has passed.'
            }, status=status.HTTP_403_FORBIDDEN)

        # Check existing attempt
        existing_attempt = ExaminationAttempt.objects.filter(
            examination=exam,
            user=request.user
        ).order_by('-started_at').first()

        if existing_attempt:
            if existing_attempt.status in (AttemptStatus.SUBMITTED, AttemptStatus.AUTO_SUBMITTED):
                return Response({
                    'status': 'ERROR',
                    'code': 'ALREADY_SUBMITTED',
                    'message': 'Attempt already completed.'
                }, status=status.HTTP_409_CONFLICT)

            # Recover existing in-progress session
            payload = build_attempt_payload(existing_attempt, is_recovered=True)
            return Response(payload, status=status.HTTP_200_OK)

        # Create new attempt
        started_at = now
        server_deadline = started_at + timedelta(minutes=exam.duration_minutes)
        if exam.end_window and exam.end_window < server_deadline:
            server_deadline = exam.end_window

        attempt = ExaminationAttempt.objects.create(
            user=request.user,
            examination=exam,
            started_at=started_at,
            server_deadline=server_deadline,
            status=AttemptStatus.IN_PROGRESS,
            tab_switch_count=0
        )

        payload = build_attempt_payload(attempt, is_recovered=False)
        return Response(payload, status=status.HTTP_200_OK)


class HeartbeatView(APIView):
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

        # Candidate security check
        if attempt.user != request.user and not request.user.is_staff:
            return Response({
                'status': 'ERROR',
                'code': 'UNAUTHORIZED',
                'message': 'You do not have permission to access this attempt.'
            }, status=status.HTTP_403_FORBIDDEN)

        blur_count = request.data.get('window_blur_count', 0)
        try:
            blur_count = int(blur_count)
        except (ValueError, TypeError):
            blur_count = 0

        if blur_count < 0:
            return Response({
                'status': 'ERROR',
                'code': 'INVALID_METRIC',
                'message': 'Blur count cannot be negative.'
            }, status=status.HTTP_400_BAD_REQUEST)

        now = timezone.now()
        rem_secs = max(0, int((attempt.server_deadline - now).total_seconds()))

        # Update blur count if higher
        if blur_count > attempt.tab_switch_count:
            attempt.tab_switch_count = blur_count
            attempt.save(update_fields=['tab_switch_count', 'updated_at'])

        # Auto-submit if deadline expired beyond 30-second grace period
        if rem_secs == 0 and now > (attempt.server_deadline + timedelta(seconds=30)):
            if attempt.status == AttemptStatus.IN_PROGRESS:
                attempt.status = AttemptStatus.AUTO_SUBMITTED
                attempt.submitted_at = now
                attempt.save(update_fields=['status', 'submitted_at', 'updated_at'])

        max_switches = getattr(attempt.examination, 'max_window_switches', 3) or 3
        is_terminated = (attempt.tab_switch_count > max_switches) or (attempt.status in (AttemptStatus.SUBMITTED, AttemptStatus.AUTO_SUBMITTED))

        return Response({
            'status': 'SUCCESS',
            'server_time': now.isoformat(),
            'server_deadline': attempt.server_deadline.isoformat(),
            'remaining_seconds': rem_secs,
            'is_terminated': is_terminated,
            'tab_switch_count': attempt.tab_switch_count,
        }, status=status.HTTP_200_OK)


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
    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        try:
            # First check existence without lock
            if not ExaminationAttempt.objects.filter(id=id).exists():
                return Response({
                    'status': 'ERROR',
                    'code': 'ATTEMPT_NOT_FOUND',
                    'message': f'Attempt {id} not found.'
                }, status=status.HTTP_404_NOT_FOUND)
        except (ValueError, TypeError):
            return Response({
                'status': 'ERROR',
                'code': 'ATTEMPT_NOT_FOUND',
                'message': f'Attempt {id} not found.'
            }, status=status.HTTP_404_NOT_FOUND)

        reason = request.data.get('submission_reason', 'MANUAL_SUBMIT')
        now = timezone.now()

        with transaction.atomic():
            attempt = ExaminationAttempt.objects.select_for_update().get(id=id)

            if attempt.user != request.user and not request.user.is_staff:
                return Response({
                    'status': 'ERROR',
                    'code': 'UNAUTHORIZED',
                    'message': 'You do not have permission to access this attempt.'
                }, status=status.HTTP_403_FORBIDDEN)

            # Idempotent return if already submitted
            if attempt.status in (AttemptStatus.SUBMITTED, AttemptStatus.AUTO_SUBMITTED):
                return Response({
                    'status': 'SUCCESS',
                    'code': 'ALREADY_SUBMITTED',
                    'attempt_id': str(attempt.id),
                    'submission_status': 'SUBMITTED',
                    'submitted_at': attempt.submitted_at.isoformat() if attempt.submitted_at else now.isoformat(),
                    'message': 'Attempt was already recorded as submitted.'
                }, status=status.HTTP_200_OK)

            # Deadline boundary check for manual submission
            if now > (attempt.server_deadline + timedelta(seconds=30)) and reason != 'AUTO_TIMER_EXPIRY':
                return Response({
                    'status': 'ERROR',
                    'code': 'DEADLINE_EXPIRED',
                    'message': 'Manual submission rejected: Server deadline has expired.'
                }, status=status.HTTP_403_FORBIDDEN)

            if reason == 'AUTO_TIMER_EXPIRY':
                attempt.status = AttemptStatus.AUTO_SUBMITTED
            else:
                attempt.status = AttemptStatus.SUBMITTED
            attempt.submitted_at = now
            attempt.save(update_fields=['status', 'submitted_at', 'updated_at'])

        return Response({
            'status': 'SUCCESS',
            'attempt_id': str(attempt.id),
            'submission_status': 'SUBMITTED',
            'submitted_at': attempt.submitted_at.isoformat(),
            'message': 'Examination submitted successfully. Results will be published by faculty.'
        }, status=status.HTTP_200_OK)


class ResumeAttemptView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
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

        payload = build_attempt_payload(attempt, is_recovered=True)
        return Response(payload, status=status.HTTP_200_OK)


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
