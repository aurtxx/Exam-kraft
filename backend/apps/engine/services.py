from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import User, UserRole
from apps.examinations.candidates import candidate_examinations
from apps.examinations.models import Examination, ExaminationStatus
from .models import (
    AttemptStatus,
    ExaminationAttempt,
    ResponseStatus,
)
from .serializers import DeliveryQuestionSerializer

ATTEMPT_GRACE_PERIOD = timedelta(seconds=30)
FINAL_ATTEMPT_STATUSES = (AttemptStatus.SUBMITTED, AttemptStatus.AUTO_SUBMITTED)
ACTIVE_EXAM_STATUSES = (
    ExaminationStatus.PUBLISHED,
    ExaminationStatus.SCHEDULED,
    ExaminationStatus.IN_PROGRESS,
)


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

    exam_sections = exam.sections.all().order_by('order')
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
