import uuid
from django.utils.dateparse import parse_datetime
from django.db import transaction
from rest_framework import status, generics, exceptions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import (
    Examination,
    ExaminationSection,
    ExaminationQuestion,
    CandidateAssignment,
    ExaminationStatus,
)
from .serializers import (
    ExaminationSerializer,
)
from apps.question_bank.models import QuestionBank
from apps.question_bank.serializers import QuestionSerializer
from apps.organizations.models import Batch, ExaminationCenter
from apps.accounts.models import User, UserRole
from apps.accounts.permissions import (
    IsActiveTenantMember,
    IsOrgAdminOrFaculty,
    IsOrgAdminOrReadOnly,
    require_tenant,
)


class ExaminationListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsActiveTenantMember, IsOrgAdminOrReadOnly]

    def get(self, request):
        tenant = require_tenant(request)
        qs = Examination.objects.filter(organization=tenant)

        serializer = ExaminationSerializer(qs, many=True)
        return Response({
            'status': 'SUCCESS',
            'examinations': serializer.data,
        }, status=status.HTTP_200_OK)

    @transaction.atomic
    def post(self, request):
        tenant = require_tenant(request)
        data = request.data

        # 1. Validate duration
        duration_raw = data.get('duration_minutes', 60)
        try:
            duration = int(duration_raw)
        except (ValueError, TypeError):
            return Response({
                'status': 'ERROR',
                'code': 'INVALID_DURATION',
                'message': 'Duration must be an integer.'
            }, status=status.HTTP_400_BAD_REQUEST)

        if duration <= 0:
            return Response({
                'status': 'ERROR',
                'code': 'INVALID_DURATION',
                'message': 'Examination duration must be greater than zero.'
            }, status=status.HTTP_400_BAD_REQUEST)

        if duration > 1440:
            return Response({
                'status': 'ERROR',
                'code': 'DURATION_OVERFLOW',
                'message': 'Examination duration cannot exceed 1440 minutes (24 hours).'
            }, status=status.HTTP_400_BAD_REQUEST)

        # 2. Validate start and end windows
        start_raw = data.get('start_window')
        end_raw = data.get('end_window')
        start_dt = parse_datetime(start_raw) if start_raw else None
        end_dt = parse_datetime(end_raw) if end_raw else None

        if start_dt and end_dt and start_dt >= end_dt:
            return Response({
                'status': 'ERROR',
                'code': 'INVALID_WINDOW',
                'message': 'start_window must be chronologically before end_window.'
            }, status=status.HTTP_400_BAD_REQUEST)

        name = data.get('name') or data.get('title') or 'Untitled Examination'
        code = data.get('code') or f"EX_{uuid.uuid4().hex[:6].upper()}"
        slug = data.get('slug') or f"exam-{uuid.uuid4().hex[:6]}"

        qpid = data.get('question_paper_id')
        paper = None
        if qpid:
            paper = QuestionBank.all_objects.filter(id=qpid, organization=tenant).first() if is_valid_uuid(qpid) else None
            if paper is None:
                raise exceptions.ValidationError({'question_paper_id': 'Unknown question paper.'})

        batches = Batch.all_objects.filter(organization=tenant)
        batch_ids = set(data.get('batch_ids') or [])
        if any(not is_valid_uuid(bid) for bid in batch_ids):
            raise exceptions.ValidationError({'batch_ids': 'Invalid batch ID.'})
        selected_batches = list(batches.filter(id__in=batch_ids))
        if len(selected_batches) != len(batch_ids):
            raise exceptions.ValidationError({'batch_ids': 'Unknown batch.'})

        exam = Examination.all_objects.create(
            organization=tenant,
            name=name,
            code=code,
            slug=slug,
            question_paper=paper,
            instructions=data.get('instructions', ''),
            duration_minutes=duration,
            total_marks=data.get('total_marks', 0.00),
            passing_marks=data.get('passing_marks'),
            status=ExaminationStatus.DRAFT,
            start_window=start_dt,
            end_window=end_dt,
            shuffle_questions=bool(data.get('shuffle_questions', data.get('shuf', False))),
            shuffle_options=bool(data.get('shuffle_options', False)),
            camera_proctoring=bool(data.get('camera_proctoring', data.get('cam', False))),
            max_window_switches=int(data.get('max_window_switches', data.get('num_swics', 5))),
            allow_section_skip=bool(data.get('allow_section_skip', data.get('sec_skip', True))),
            practice_mode=bool(data.get('practice_mode', False)),
            pc_only=bool(data.get('pc_only', False)),
            hide_results=bool(data.get('hide_results', False)),
            hide_rank=bool(data.get('hide_rank', False)),
            hide_analytics=bool(data.get('hide_analytics', False)),
            short_url=f"ezex.in/{slug}",
            created_by=request.user if request.user.is_authenticated else None,
        )

        for batch in selected_batches:
            CandidateAssignment.objects.create(exam=exam, batch=batch)

        serializer = ExaminationSerializer(exam)
        return Response({
            'status': 'SUCCESS',
            'id': str(exam.id),
            'short_url': exam.short_url,
            'examination': serializer.data,
            'message': 'Examination created successfully.',
        }, status=status.HTTP_201_CREATED)


class ExaminationDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsActiveTenantMember, IsOrgAdminOrReadOnly]
    serializer_class = ExaminationSerializer
    lookup_field = 'id'

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    def get_queryset(self):
        queryset = Examination.objects.filter(organization=require_tenant(self.request))
        if self.request.method in ('PUT', 'PATCH'):
            return queryset.select_for_update()
        return queryset


def is_valid_uuid(val):
    try:
        uuid.UUID(str(val))
        return True
    except (ValueError, TypeError, AttributeError):
        return False


class AssignCandidatesView(APIView):
    permission_classes = [IsAuthenticated, IsActiveTenantMember, IsOrgAdminOrReadOnly]

    @transaction.atomic
    def post(self, request, id):
        tenant = require_tenant(request)
        if not is_valid_uuid(id):
            return Response({
                'status': 'ERROR',
                'code': 'NOT_FOUND',
                'message': f'Examination {id} not found.'
            }, status=status.HTTP_404_NOT_FOUND)

        exam = Examination.all_objects.select_for_update().filter(id=id, organization=tenant).first()
        if not exam:
            return Response({
                'status': 'ERROR',
                'code': 'NOT_FOUND',
                'message': f'Examination {id} not found.'
            }, status=status.HTTP_404_NOT_FOUND)

        data = request.data
        student_ids = data.get('student_ids', [])
        batch_ids = data.get('batch_ids', [])
        center_ids = data.get('centre_ids', data.get('center_ids', []))

        students = User.objects.filter(organization=tenant, role=UserRole.STUDENT)
        batches = Batch.all_objects.filter(organization=tenant)
        centers = ExaminationCenter.all_objects.filter(organization=tenant)
        assigned_count = 0
        for field, identifiers, queryset, alternate in (
            ('student', student_ids, students, 'username'),
            ('batch', batch_ids, batches, 'code'),
            ('center', center_ids, centers, 'code'),
        ):
            for identifier in identifiers:
                target = queryset.filter(pk=identifier).first() if is_valid_uuid(identifier) else None
                if target is None:
                    target = queryset.filter(**{alternate: identifier}).first()
                if target is not None:
                    _, created = CandidateAssignment.objects.get_or_create(exam=exam, **{field: target})
                    assigned_count += int(created)

        return Response({
            'status': 'SUCCESS',
            'assigned_count': assigned_count,
            'message': f'{assigned_count} candidates assigned to examination.',
        }, status=status.HTTP_200_OK)


class PublishExaminationView(APIView):
    permission_classes = [IsAuthenticated, IsActiveTenantMember, IsOrgAdminOrReadOnly]

    @transaction.atomic
    def post(self, request, id):
        tenant = require_tenant(request)
        if not is_valid_uuid(id):
            return Response({
                'status': 'ERROR',
                'code': 'NOT_FOUND',
                'message': f'Examination {id} not found.'
            }, status=status.HTTP_404_NOT_FOUND)

        exam = Examination.objects.select_for_update().filter(id=id, organization=tenant).first()
        if not exam:
            return Response({
                'status': 'ERROR',
                'code': 'NOT_FOUND',
                'message': f'Examination {id} not found.'
            }, status=status.HTTP_404_NOT_FOUND)

        if exam.status != ExaminationStatus.DRAFT:
            return Response({
                'status': 'ERROR',
                'code': 'INVALID_STATUS',
                'message': 'Only draft examinations can be published.',
            }, status=status.HTTP_400_BAD_REQUEST)

        if exam.start_window and exam.end_window and exam.start_window >= exam.end_window:
            return Response({
                'status': 'ERROR',
                'code': 'INVALID_WINDOW',
                'message': 'The examination end window must be after the start window.',
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check question count
        q_count = 0
        paper = None
        if exam.question_paper_id:
            paper = QuestionBank.all_objects.select_for_update().filter(pk=exam.question_paper_id, organization=tenant).first()
            if paper is None:
                raise exceptions.ValidationError({'question_paper_id': 'Unknown question paper.'})
            q_count = paper.questions.count()
        if q_count == 0:
            q_count = exam.sections.filter(exam_questions__isnull=False).count()

        if q_count == 0:
            return Response({
                'status': 'ERROR',
                'code': 'EMPTY_EXAM',
                'message': 'Cannot publish an examination with zero questions. Please add questions first.'
            }, status=status.HTTP_400_BAD_REQUEST)

        exam.status = ExaminationStatus.PUBLISHED
        exam.save(update_fields=['status'])

        if paper:
            paper.is_locked = True
            paper.save(update_fields=['is_locked'])

        return Response({
            'status': 'PUBLISHED',
            'message': 'Examination published successfully.',
        }, status=status.HTTP_200_OK)


class StaffPreviewView(APIView):
    permission_classes = [IsAuthenticated, IsActiveTenantMember, IsOrgAdminOrFaculty]

    def get(self, request, id):
        tenant = require_tenant(request)
        if not is_valid_uuid(id):
            return Response({
                'status': 'ERROR',
                'code': 'NOT_FOUND',
                'message': f'Examination {id} not found.'
            }, status=status.HTTP_404_NOT_FOUND)

        exam = Examination.all_objects.filter(id=id, organization=tenant).first()
        if not exam:
            return Response({
                'status': 'ERROR',
                'code': 'NOT_FOUND',
                'message': f'Examination {id} not found.'
            }, status=status.HTTP_404_NOT_FOUND)

        questions_data = []
        paper = QuestionBank.all_objects.filter(pk=exam.question_paper_id, organization=tenant).first()
        if paper:
            qs = paper.questions.all().order_by('question_number')
            questions_data = QuestionSerializer(qs, many=True).data

        return Response({
            'status': 'SUCCESS',
            'exam': ExaminationSerializer(exam).data,
            'questions': questions_data,
        }, status=status.HTTP_200_OK)
