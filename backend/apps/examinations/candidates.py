from django.db.models import Q

from apps.organizations.models import StudentBatchEnrollment
from .models import Examination, ExaminationStatus


def candidate_examinations(user):
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
