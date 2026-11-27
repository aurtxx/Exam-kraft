from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.accounts.models import User, UserRole
try:
    from apps.examinations.candidates import candidate_examinations
except (ImportError, ModuleNotFoundError):
    def candidate_examinations(user):
        from django.db.models import Q
        from apps.organizations.models import StudentBatchEnrollment
        from apps.examinations.models import Examination, ExaminationStatus

        enrollments = StudentBatchEnrollment.objects.filter(
            student=user, is_active=True, batch__organization_id=user.organization_id
        )
        return Examination.all_objects.filter(
            organization_id=user.organization_id,
            status__in=(
                ExaminationStatus.PUBLISHED,
                ExaminationStatus.SCHEDULED,
                ExaminationStatus.IN_PROGRESS,
            ),
        ).filter(
            Q(candidate_assignments__isnull=True)
            | Q(candidate_assignments__student=user)
            | Q(candidate_assignments__batch_id__in=enrollments.values('batch_id'))
            | Q(candidate_assignments__center_id__in=enrollments.values('center_id'))
        ).distinct()
from apps.examinations.models import Examination, ExaminationQuestion, ExaminationStatus
from apps.question_bank.models import Question, QuestionType, normalize_question_type
from .models import (
    AttemptResponse,
    AttemptStatus,
    ExaminationAttempt,
    ProctoringEventType,
    ProctoringLog,
    ResponseStatus,
)
from .serializers import DeliveryQuestionSerializer, ProctoringEventInputSerializer

ATTEMPT_GRACE_PERIOD = timedelta(seconds=30)
FINAL_ATTEMPT_STATUSES = (AttemptStatus.SUBMITTED, AttemptStatus.AUTO_SUBMITTED)
ACTIVE_EXAM_STATUSES = (
    ExaminationStatus.PUBLISHED,
    ExaminationStatus.SCHEDULED,
    ExaminationStatus.IN_PROGRESS,
)
VALID_SUBMISSION_REASONS = ('MANUAL_SUBMIT', 'AUTO_TIMER_EXPIRY')
MAX_TIME_SPENT_SECONDS = 86400 * 7
MAX_PROCTORING_LOGS_PER_ATTEMPT = 100
MAX_PROCTORING_EVENTS_PER_MINUTE = 30
PROCTORING_TIMESTAMP_SKEW = timedelta(minutes=5)
RESPONSE_STATUS_ALIASES = {
    'ANSWERED_AND_MARKED_FOR_REVIEW': ResponseStatus.ANSWERED_AND_MARKED,
    'ANSWERED_AND_MARKED': ResponseStatus.ANSWERED_AND_MARKED,
    'ANSWERED_MARKED': ResponseStatus.ANSWERED_AND_MARKED,
    'MARKED_FOR_REVIEW': ResponseStatus.MARKED_FOR_REVIEW,
    'MARKED': ResponseStatus.MARKED_FOR_REVIEW,
    'ANSWERED': ResponseStatus.ANSWERED,
    'ATTEMPTED': ResponseStatus.ANSWERED,
    'UNANSWERED': ResponseStatus.UNANSWERED,
    'NOT_ANSWERED': ResponseStatus.UNANSWERED,
    'NOT_VISITED': ResponseStatus.NOT_VISITED,
    'UNVISITED': ResponseStatus.NOT_VISITED,
}


@dataclass(frozen=True)
class ServiceOutcome:
    """Structured domain outcome so atomic() commits state transitions (e.g. AUTO_SUBMITTED) even on 4xx."""
    ok: bool
    data: dict[str, Any]
    http_status: int = 200

    @classmethod
    def success(cls, data: dict[str, Any], http_status: int = 200) -> 'ServiceOutcome':
        return cls(ok=True, data=data, http_status=http_status)

    @classmethod
    def error(cls, code: str, message: str, http_status: int, **extra: Any) -> 'ServiceOutcome':
        payload: dict[str, Any] = {
            'status': 'ERROR',
            'code': code,
            'message': message,
        }
        payload.update(extra)
        return cls(ok=False, data=payload, http_status=http_status)


def compute_server_deadline(exam: Examination, started_at: datetime) -> datetime:
    """Unified server deadline: min(started_at + duration_minutes, exam.end_window)."""
    deadline = started_at + timedelta(minutes=exam.duration_minutes)
    if exam.end_window is not None and exam.end_window < deadline:
        deadline = exam.end_window
    return deadline


def hard_deadline(attempt: ExaminationAttempt) -> datetime:
    """Authoritative deadline including the server-side network grace period."""
    return attempt.server_deadline + ATTEMPT_GRACE_PERIOD


def is_finalized(attempt: ExaminationAttempt) -> bool:
    return attempt.status in FINAL_ATTEMPT_STATUSES


def compute_remaining_seconds(
    attempt: ExaminationAttempt,
    now: datetime | None = None,
    *,
    from_start: bool = False,
) -> int:
    """Unified remaining seconds; always 0 for finalized or past-deadline attempts."""
    if is_finalized(attempt):
        return 0
    ref = attempt.started_at if from_start else (now or timezone.now())
    delta = (attempt.server_deadline - ref).total_seconds()
    if delta <= 0:
        return 0
    return int(round(delta)) if from_start else int(delta)


def max_allowed_switches(attempt: ExaminationAttempt) -> int:
    return getattr(attempt.examination, 'max_window_switches', 3) or 3


def lock_attempt(
    attempt_id,
    user=None,
    *,
    allow_staff: bool = False,
    tenant=None,
) -> tuple[ExaminationAttempt | None, ServiceOutcome | None]:
    """
    Acquire an exclusive row lock on ONLY the ExaminationAttempt row (of=('self',))
    without select_related('examination') inside an active transaction.atomic() block.
    """
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError('lock_attempt() must be called inside transaction.atomic().')

    try:
        attempt_uuid = uuid.UUID(str(attempt_id))
    except (ValueError, TypeError, AttributeError):
        return None, ServiceOutcome.error('ATTEMPT_NOT_FOUND', f'Attempt {attempt_id} not found.', 404)

    try:
        attempt = (
            ExaminationAttempt.objects
            .select_for_update(of=('self',))
            .get(id=attempt_uuid)
        )
    except (ExaminationAttempt.DoesNotExist, ValidationError):
        return None, ServiceOutcome.error('ATTEMPT_NOT_FOUND', f'Attempt {attempt_id} not found.', 404)

    exam = attempt.examination
    exam_org_id = exam.organization_id

    if user is not None:
        is_superadmin = (
            getattr(user, 'role', None) == UserRole.SUPERADMIN
            or getattr(user, 'is_superuser', False)
        )
        if tenant is not None and not is_superadmin and str(tenant.pk) != str(exam_org_id):
            return None, ServiceOutcome.error('ATTEMPT_NOT_FOUND', f'Attempt {attempt_id} not found.', 404)

        is_owner = (attempt.user_id == user.id) and (user.organization_id == exam_org_id)
        is_authorized_staff = allow_staff and (
            is_superadmin
            or (
                (user.is_staff or getattr(user, 'role', None) in (UserRole.ORG_ADMIN, UserRole.FACULTY))
                and user.organization_id == exam_org_id
            )
        )
        if not (is_owner or is_authorized_staff):
            return None, ServiceOutcome.error(
                'UNAUTHORIZED',
                'You do not have permission to access this attempt.',
                403,
            )

    return attempt, None


def expire_if_due(attempt: ExaminationAttempt, *, now: datetime | None = None) -> bool:
    """
    Transition an overdue IN_PROGRESS attempt to AUTO_SUBMITTED under lock.
    Returns True iff this call transitioned the attempt from IN_PROGRESS -> AUTO_SUBMITTED.
    Never overwrites already-finalized attempts.
    """
    if is_finalized(attempt):
        return False
    check_now = now or timezone.now()
    if check_now > hard_deadline(attempt):
        attempt.status = AttemptStatus.AUTO_SUBMITTED
        attempt.submitted_at = check_now
        attempt.save(update_fields=['status', 'submitted_at', 'updated_at'])
        return True
    return False


def build_attempt_payload(
    attempt: ExaminationAttempt,
    is_recovered: bool = False,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Constructs complete CBT attempt session payload including sections, questions, responses, and palette."""
    exam = attempt.examination
    remaining_secs = compute_remaining_seconds(attempt, now=now, from_start=not is_recovered)

    sections_data = []
    total_q_count = 0

    exam_sections = exam.sections.prefetch_related('exam_questions__question__options').all().order_by('order')
    if exam_sections.exists():
        for sec in exam_sections:
            eq_qs = sec.exam_questions.all().order_by('order')
            sec_qids = []
            sec_questions = []
            for eq in eq_qs:
                q = eq.question
                sec_qids.append(q.id)
                sec_questions.append(DeliveryQuestionSerializer(q).data)

            if not sec_questions:
                continue
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

    if not total_q_count and exam.question_paper:
        sections_data.clear()
        paper_questions = exam.question_paper.questions.all().order_by('question_number', 'created_at')
        grouped = defaultdict(list)
        for q in paper_questions:
            s_name = q.section_name or (q.section.name if q.section else 'General')
            grouped[s_name].append(q)

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
        'candidate': {
            'roll_number': attempt.user.enrollments.filter(
                is_active=True, batch__organization_id=exam.organization_id
            ).values_list('roll_number', flat=True).first(),
        },
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


@transaction.atomic
def start_attempt(user, exam_id, *, tenant=None, now: datetime | None = None) -> ServiceOutcome:
    """Start a new attempt or recover an active IN_PROGRESS attempt atomically."""
    if not exam_id:
        return ServiceOutcome.error('EXAM_NOT_FOUND', 'Examination ID is required.', 404)

    try:
        is_superadmin = (
            getattr(user, 'role', None) == UserRole.SUPERADMIN
            or getattr(user, 'is_superuser', False)
        )
        if user.role == UserRole.STUDENT:
            exams = candidate_examinations(user)
        else:
            exams = Examination.all_objects.filter(status__in=ACTIVE_EXAM_STATUSES)
            if not is_superadmin:
                exams = exams.filter(organization_id=user.organization_id)
        exam = exams.get(id=exam_id)
    except (Examination.DoesNotExist, ValueError, ValidationError):
        return ServiceOutcome.error('EXAM_NOT_FOUND', f'Examination {exam_id} not found.', 404)

    if tenant is not None and not is_superadmin and str(exam.organization_id) != str(tenant.pk):
        return ServiceOutcome.error('EXAM_NOT_FOUND', f'Examination {exam_id} not found.', 404)

    check_now = now or timezone.now()

    if exam.start_window and check_now < exam.start_window:
        return ServiceOutcome.error('EXAM_NOT_STARTED', 'Examination has not started yet.', 403)

    if exam.end_window and check_now >= exam.end_window:
        return ServiceOutcome.error('EXAM_EXPIRED', 'Examination window has passed.', 403)

    User.objects.select_for_update().get(pk=user.pk)

    existing_attempt = (
        ExaminationAttempt.objects
        .select_for_update(of=('self',))
        .filter(examination=exam, user=user)
        .order_by('-started_at')
        .first()
    )

    if existing_attempt is not None:
        expire_if_due(existing_attempt, now=check_now)
        if is_finalized(existing_attempt):
            return ServiceOutcome.error('ALREADY_SUBMITTED', 'Attempt already completed.', 409)
        return ServiceOutcome.success(
            build_attempt_payload(existing_attempt, is_recovered=True, now=check_now)
        )

    server_deadline = compute_server_deadline(exam, check_now)
    try:
        with transaction.atomic():
            attempt = ExaminationAttempt.objects.create(
                user=user,
                examination=exam,
                started_at=check_now,
                server_deadline=server_deadline,
                status=AttemptStatus.IN_PROGRESS,
                tab_switch_count=0,
            )
            return ServiceOutcome.success(
                build_attempt_payload(attempt, is_recovered=False, now=check_now)
            )
    except IntegrityError:
        winning = (
            ExaminationAttempt.objects
            .select_for_update(of=('self',))
            .filter(examination=exam, user=user, status=AttemptStatus.IN_PROGRESS)
            .order_by('-started_at')
            .first()
        )
        if winning is not None:
            expire_if_due(winning, now=check_now)
            if is_finalized(winning):
                return ServiceOutcome.error('ALREADY_SUBMITTED', 'Attempt already completed.', 409)
            return ServiceOutcome.success(
                build_attempt_payload(winning, is_recovered=True, now=check_now)
            )
        raise


def resume_attempt(
    attempt_id,
    user,
    *,
    tenant=None,
    now: datetime | None = None,
) -> ServiceOutcome:
    """Resume an existing attempt under row lock, expiring overdue attempts cleanly."""
    with transaction.atomic():
        attempt, err = lock_attempt(attempt_id, user, allow_staff=True, tenant=tenant)
        if err is not None:
            return err

        check_now = now or timezone.now()
        expire_if_due(attempt, now=check_now)
        if is_finalized(attempt):
            return ServiceOutcome.error('ALREADY_SUBMITTED', 'Attempt already completed.', 409)

        return ServiceOutcome.success(
            build_attempt_payload(attempt, is_recovered=True, now=check_now)
        )


def heartbeat_attempt(
    attempt_id,
    user,
    blur_count_raw: Any = 0,
    *,
    tenant=None,
    now: datetime | None = None,
) -> ServiceOutcome:
    """Record heartbeat under row lock, sync blur count, and enforce deadline/blur auto-submit."""
    if isinstance(blur_count_raw, bool):
        return ServiceOutcome.error('INVALID_METRIC', 'Blur count must be an integer.', 400)
    try:
        blur_count = int(blur_count_raw) if blur_count_raw is not None else 0
    except (ValueError, TypeError):
        blur_count = 0

    if blur_count < 0:
        return ServiceOutcome.error('INVALID_METRIC', 'Blur count cannot be negative.', 400)

    with transaction.atomic():
        attempt, err = lock_attempt(attempt_id, user, allow_staff=True, tenant=tenant)
        if err is not None:
            return err

        check_now = now or timezone.now()
        expire_if_due(attempt, now=check_now)

        max_switches = max_allowed_switches(attempt)
        if not is_finalized(attempt):
            update_fields = []
            if blur_count > attempt.tab_switch_count:
                attempt.tab_switch_count = blur_count
                update_fields.append('tab_switch_count')
            if attempt.tab_switch_count > max_switches:
                attempt.status = AttemptStatus.AUTO_SUBMITTED
                attempt.submitted_at = check_now
                update_fields.extend(['status', 'submitted_at'])
            if update_fields:
                update_fields.append('updated_at')
                attempt.save(update_fields=update_fields)

        rem_secs = compute_remaining_seconds(attempt, now=check_now)
        is_terminated = (attempt.tab_switch_count > max_switches) or is_finalized(attempt)

        return ServiceOutcome.success({
            'status': 'SUCCESS',
            'server_time': check_now.isoformat(),
            'server_deadline': attempt.server_deadline.isoformat(),
            'remaining_seconds': rem_secs,
            'is_terminated': is_terminated,
            'tab_switch_count': attempt.tab_switch_count,
        })


def submit_attempt(
    attempt_id,
    user,
    *,
    reason: str = 'MANUAL_SUBMIT',
    tenant=None,
    now: datetime | None = None,
) -> ServiceOutcome:
    """
    Atomically lock `attempt`, enforce idempotency and deadline expiry, and finalize submission.
    """
    if reason is None:
        reason = 'MANUAL_SUBMIT'
    if not isinstance(reason, str) or reason not in VALID_SUBMISSION_REASONS:
        return ServiceOutcome.error(
            'INVALID_SUBMISSION_REASON',
            f"Invalid submission_reason '{reason}'.",
            400,
        )

    with transaction.atomic():
        attempt, err = lock_attempt(attempt_id, user, allow_staff=False, tenant=tenant)
        if err is not None:
            return err

        check_now = now or timezone.now()

        if is_finalized(attempt):
            submitted_ts = attempt.submitted_at or check_now
            return ServiceOutcome.success({
                'status': 'SUCCESS',
                'code': 'ALREADY_SUBMITTED',
                'attempt_id': str(attempt.id),
                'submission_status': 'SUBMITTED',
                'submitted_at': submitted_ts.isoformat(),
                'message': 'Attempt was already recorded as submitted.',
            })

        if reason != 'AUTO_TIMER_EXPIRY' and expire_if_due(attempt, now=check_now):
            return ServiceOutcome.error(
                'DEADLINE_EXPIRED',
                'Manual submission rejected: Server deadline has expired.',
                403,
            )

        attempt.status = (
            AttemptStatus.AUTO_SUBMITTED
            if reason == 'AUTO_TIMER_EXPIRY'
            else AttemptStatus.SUBMITTED
        )
        attempt.submitted_at = check_now
        attempt.save(update_fields=['status', 'submitted_at', 'updated_at'])

        return ServiceOutcome.success({
            'status': 'SUCCESS',
            'attempt_id': str(attempt.id),
            'submission_status': 'SUBMITTED',
            'submitted_at': attempt.submitted_at.isoformat(),
            'message': 'Examination submitted successfully. Results will be published by faculty.',
        })


def scoped_exam_questions(examination: Examination):
    """
    Return the Question queryset strictly belonging to `examination` and its tenant.
    Mirrors `build_attempt_payload`: uses ExaminationQuestion links if any exist on the exam,
    otherwise falls back to `examination.question_paper`.
    """
    if ExaminationQuestion.objects.filter(exam_section__exam=examination).exists():
        return Question.objects.filter(
            exam_instances__exam_section__exam=examination,
            question_bank__organization_id=examination.organization_id,
        ).distinct()
    if examination.question_paper_id:
        return Question.objects.filter(
            question_bank_id=examination.question_paper_id,
            question_bank__organization_id=examination.organization_id,
        )
    return Question.objects.none()


def resolve_exam_question(
    attempt: ExaminationAttempt,
    question_identifier: Any,
) -> tuple[Question | None, ServiceOutcome | None]:
    """Resolve a question by UUID strictly within `attempt.examination` and its tenant."""
    if (
        question_identifier is None
        or isinstance(question_identifier, (bool, dict, list))
        or not str(question_identifier).strip()
    ):
        return None, ServiceOutcome.error('INVALID_PAYLOAD', 'question_id is required.', 400)

    try:
        qid_uuid = uuid.UUID(str(question_identifier).strip())
    except (ValueError, TypeError, AttributeError):
        return None, ServiceOutcome.error('INVALID_QUESTION_ID', 'question_id must be a valid UUID.', 400)

    question = (
        scoped_exam_questions(attempt.examination)
        .prefetch_related('options')
        .filter(id=qid_uuid)
        .first()
    )
    if question is None:
        return None, ServiceOutcome.error(
            'QUESTION_NOT_FOUND',
            f'Question {question_identifier} not found in this examination.',
            404,
        )
    return question, None


def validate_answer_payload(
    question: Question,
    answer_payload: Any,
) -> tuple[dict[str, Any] | None, ServiceOutcome | None]:
    """Validate and normalize answer payload against Question type, options, and DB bounds."""
    if not isinstance(answer_payload, dict):
        return None, ServiceOutcome.error('INVALID_PAYLOAD', 'Request payload must be a JSON object.', 400)

    kind = normalize_question_type(question.question_type)

    # 1. selected_options (explicit null must be rejected to avoid NOT NULL IntegrityError)
    if 'selected_options' in answer_payload:
        raw_selected = answer_payload.get('selected_options')
    else:
        raw_selected = []
    if not isinstance(raw_selected, list):
        return None, ServiceOutcome.error('INVALID_RESPONSE', 'selected_options must be a list.', 400)

    cleaned_options: list[str] = []
    seen_opts: set[str] = set()
    for item in raw_selected:
        if not isinstance(item, str) or not item.strip() or len(item.strip()) > 50:
            return None, ServiceOutcome.error(
                'INVALID_RESPONSE',
                'Each selected option must be a non-empty string.',
                400,
            )
        token = item.strip()
        norm = token.upper()
        if norm not in seen_opts:
            seen_opts.add(norm)
            cleaned_options.append(token)

    # 2. numerical_value
    raw_num = answer_payload.get('numerical_value')
    if raw_num is None:
        cleaned_numerical = None
    elif isinstance(raw_num, (bool, list, dict)):
        return None, ServiceOutcome.error(
            'INVALID_RESPONSE',
            'numerical_value must be a string or number.',
            400,
        )
    else:
        num_str = str(raw_num).strip()
        if num_str == '':
            cleaned_numerical = None
        elif len(num_str) > 100:
            return None, ServiceOutcome.error(
                'INVALID_RESPONSE',
                'numerical_value exceeds maximum length of 100 characters.',
                400,
            )
        else:
            cleaned_numerical = num_str

    # 3. Cross-field validation by question_type
    if kind in (QuestionType.MCQ_SINGLE, QuestionType.MCQ_MULTI, QuestionType.TRUE_FALSE):
        if cleaned_numerical is not None:
            return None, ServiceOutcome.error(
                'INVALID_RESPONSE',
                'numerical_value is not allowed for choice questions.',
                400,
            )
        if kind in (QuestionType.MCQ_SINGLE, QuestionType.TRUE_FALSE) and len(cleaned_options) > 1:
            return None, ServiceOutcome.error(
                'INVALID_RESPONSE',
                'Single-choice questions accept at most one option.',
                400,
            )
        configured = list(question.options.all())
        if configured and cleaned_options:
            valid_tokens = (
                {opt.option_key.strip().upper() for opt in configured}
                | {str(opt.pk).upper() for opt in configured}
            )
            if any(opt.upper() not in valid_tokens for opt in cleaned_options):
                return None, ServiceOutcome.error(
                    'INVALID_RESPONSE',
                    'Selected option does not belong to this question.',
                    400,
                )
    elif kind in (QuestionType.NUMERICAL, QuestionType.SINGLE_DIGIT):
        if cleaned_options:
            return None, ServiceOutcome.error(
                'INVALID_RESPONSE',
                'selected_options is not allowed for numerical questions.',
                400,
            )
        if cleaned_numerical is not None:
            try:
                dec = Decimal(cleaned_numerical)
            except InvalidOperation:
                return None, ServiceOutcome.error(
                    'INVALID_RESPONSE',
                    'numerical_value must be a valid finite number.',
                    400,
                )
            if not dec.is_finite():
                return None, ServiceOutcome.error(
                    'INVALID_RESPONSE',
                    'numerical_value must be a valid finite number.',
                    400,
                )
    else:
        # ONE_WORD / SUBJECTIVE / CODING
        if cleaned_options:
            return None, ServiceOutcome.error(
                'INVALID_RESPONSE',
                'selected_options is not allowed for text/code questions.',
                400,
            )

    # 4. time_spent_seconds
    raw_time = answer_payload.get('time_spent_seconds', 0)
    if isinstance(raw_time, bool):
        return None, ServiceOutcome.error(
            'INVALID_RESPONSE',
            'time_spent_seconds must be a non-negative integer.',
            400,
        )
    try:
        time_spent = int(raw_time) if raw_time is not None else 0
    except (ValueError, TypeError):
        return None, ServiceOutcome.error(
            'INVALID_RESPONSE',
            'time_spent_seconds must be a non-negative integer.',
            400,
        )
    if time_spent < 0 or time_spent > MAX_TIME_SPENT_SECONDS:
        return None, ServiceOutcome.error(
            'INVALID_RESPONSE',
            'time_spent_seconds is out of valid range.',
            400,
        )

    # 5. status
    raw_status = answer_payload.get('status')
    if raw_status is not None and str(raw_status).strip() != '':
        if not isinstance(raw_status, str):
            return None, ServiceOutcome.error('INVALID_RESPONSE', 'status must be a string.', 400)
        resp_status = RESPONSE_STATUS_ALIASES.get(raw_status.strip().upper())
        if resp_status is None:
            return None, ServiceOutcome.error(
                'INVALID_RESPONSE',
                f"Invalid response status '{raw_status}'.",
                400,
            )
    else:
        if cleaned_options or cleaned_numerical is not None:
            resp_status = ResponseStatus.ANSWERED
        else:
            resp_status = ResponseStatus.UNANSWERED

    return {
        'selected_options': cleaned_options,
        'numerical_value': cleaned_numerical,
        'status': resp_status,
        'time_spent_seconds': time_spent,
    }, None


def save_response(
    attempt_id,
    user,
    question_identifier: Any,
    answer_payload: Any,
    *,
    tenant=None,
    now: datetime | None = None,
) -> ServiceOutcome:
    """
    Lock attempt, enforce status & deadline expiry, resolve question strictly within
    `attempt.examination`, validate payload, and persist AttemptResponse atomically.
    """
    with transaction.atomic():
        attempt, err = lock_attempt(attempt_id, user, allow_staff=False, tenant=tenant)
        if err is not None:
            return err

        if is_finalized(attempt):
            return ServiceOutcome.error('ATTEMPT_LOCKED', 'Attempt is locked and submitted.', 403)

        check_now = now or timezone.now()
        if expire_if_due(attempt, now=check_now):
            return ServiceOutcome.error(
                'DEADLINE_EXPIRED',
                'Response rejected: Server deadline + grace period has expired.',
                403,
            )

        question, q_err = resolve_exam_question(attempt, question_identifier)
        if q_err is not None:
            return q_err

        cleaned, val_err = validate_answer_payload(question, answer_payload)
        if val_err is not None:
            return val_err

        response_obj, _ = AttemptResponse.objects.update_or_create(
            attempt=attempt,
            question=question,
            defaults=cleaned,
        )
        rem_secs = compute_remaining_seconds(attempt, now=check_now)
        return ServiceOutcome.success({
            'status': 'SUCCESS',
            'saved_at': response_obj.saved_at.isoformat(),
            'question_id': str(question.id),
            'remaining_seconds': rem_secs,
        })


def record_proctoring_event(
    attempt_id,
    user,
    event_data: Any,
    *,
    tenant=None,
    now: datetime | None = None,
) -> ServiceOutcome:
    """
    Validate and record a proctoring event atomically under the attempt row lock.
    Enforces:
      - Owner + same-organization check
      - Strict IN_PROGRESS status check (rejects SUBMITTED / AUTO_SUBMITTED)
      - Deadline expiration reconciliation (commits AUTO_SUBMITTED, returns 403 DEADLINE_EXPIRED)
      - Event type enum + details schema/size/timestamp bounds
      - Per-attempt log cap (100) and sliding-window rate cap (30/min)
    """
    if event_data is None:
        event_data = {}
    if not isinstance(event_data, dict):
        return ServiceOutcome.error('INVALID_PAYLOAD', 'Proctoring event payload must be a JSON object.', 400)

    serializer = ProctoringEventInputSerializer(data=event_data)
    if not serializer.is_valid():
        return ServiceOutcome.error(
            'INVALID_PAYLOAD',
            'Invalid proctoring event payload.',
            400,
            details=serializer.errors,
        )

    event_type = serializer.validated_data.get('event_type', ProctoringEventType.TAB_SWITCH)
    details = dict(serializer.validated_data.get('details') or {})
    check_now = now or timezone.now()

    parsed_ts = None
    if 'timestamp' in details:
        ts_raw = details['timestamp']
        parsed_ts = parse_datetime(ts_raw) if isinstance(ts_raw, str) else None
        if parsed_ts is None or timezone.is_naive(parsed_ts):
            return ServiceOutcome.error(
                'INVALID_PAYLOAD',
                'Invalid ISO-8601 timestamp in details.',
                400,
            )

    with transaction.atomic():
        attempt, err = lock_attempt(attempt_id, user, allow_staff=False, tenant=tenant)
        if err is not None:
            return err

        if attempt.status != AttemptStatus.IN_PROGRESS:
            return ServiceOutcome.error(
                'ATTEMPT_LOCKED',
                'Attempt is already finalized.',
                403,
            )

        if expire_if_due(attempt, now=check_now):
            return ServiceOutcome.error(
                'DEADLINE_EXPIRED',
                'Proctoring event rejected: Server deadline + grace period has expired.',
                403,
            )

        if parsed_ts is not None:
            if (
                parsed_ts < (attempt.started_at - PROCTORING_TIMESTAMP_SKEW)
                or parsed_ts > (check_now + PROCTORING_TIMESTAMP_SKEW)
            ):
                return ServiceOutcome.error(
                    'INVALID_PAYLOAD',
                    'Proctoring event timestamp is outside the valid attempt window.',
                    400,
                )

        total_logs = ProctoringLog.objects.filter(attempt=attempt).count()
        if total_logs >= MAX_PROCTORING_LOGS_PER_ATTEMPT:
            return ServiceOutcome.error(
                'PROCTORING_RATE_LIMIT',
                'Maximum proctoring event limit reached for this attempt.',
                429,
            )

        recent_logs = ProctoringLog.objects.filter(
            attempt=attempt,
            timestamp__gte=check_now - timedelta(seconds=60),
        ).count()
        if recent_logs >= MAX_PROCTORING_EVENTS_PER_MINUTE:
            return ServiceOutcome.error(
                'PROCTORING_RATE_LIMIT',
                'Too many proctoring events submitted. Please slow down.',
                429,
            )

        ProctoringLog.objects.create(
            attempt=attempt,
            event_type=event_type,
            details=details,
        )

        max_switches = max_allowed_switches(attempt)
        if event_type in (ProctoringEventType.TAB_SWITCH, ProctoringEventType.WINDOW_BLUR):
            from django.db.models import F
            ExaminationAttempt.objects.filter(pk=attempt.pk).update(
                tab_switch_count=F('tab_switch_count') + 1,
                updated_at=check_now,
            )
            attempt.refresh_from_db(fields=['tab_switch_count'])
            if attempt.tab_switch_count > max_switches:
                attempt.status = AttemptStatus.AUTO_SUBMITTED
                attempt.submitted_at = check_now
                attempt.save(update_fields=['status', 'submitted_at', 'updated_at'])

        return ServiceOutcome.success({
            'status': 'SUCCESS',
            'tab_switch_count': attempt.tab_switch_count,
            'max_allowed': max_switches,
            'auto_submitted': attempt.status == AttemptStatus.AUTO_SUBMITTED,
        })
