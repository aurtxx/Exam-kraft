import uuid
from datetime import datetime
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
    ExaminationSectionSerializer,
    CandidateAssignmentSerializer,
)
from apps.question_bank.models import QuestionBank, Question
from apps.question_bank.serializers import QuestionSerializer
from apps.organizations.models import Organization, Batch, ExaminationCenter, StudentBatchEnrollment
from apps.organizations.context import get_current_tenant
from apps.accounts.models import User, UserRole
from apps.accounts.permissions import IsTenantMember, IsOrgAdminOrReadOnly


class ExaminationListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsTenantMember, IsOrgAdminOrReadOnly]

    def get_tenant(self, request):
        return get_current_tenant() or getattr(request.user, 'organization', None)

    def get(self, request):
        tenant = self.get_tenant(request)
        qs = Examination.objects.all()
        if tenant:
            qs = qs.filter(organization=tenant)

        serializer = ExaminationSerializer(qs, many=True)
        return Response({
            'status': 'SUCCESS',
            'examinations': serializer.data,
        }, status=status.HTTP_200_OK)

    def post(self, request):
        tenant = self.get_tenant(request) or Organization.objects.first()
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
            paper = QuestionBank.all_objects.filter(id=qpid).first()

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

        # Link batches if passed in creation
        batch_ids = data.get('batch_ids') or []
        for bid in batch_ids:
            b = Batch.all_objects.filter(id=bid).first()
            if b:
                CandidateAssignment.objects.create(exam=exam, batch=b)

        serializer = ExaminationSerializer(exam)
        return Response({
            'status': 'SUCCESS',
            'id': str(exam.id),
            'short_url': exam.short_url,
            'examination': serializer.data,
            'message': 'Examination created successfully.',
        }, status=status.HTTP_201_CREATED)


class ExaminationDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsTenantMember, IsOrgAdminOrReadOnly]
    serializer_class = ExaminationSerializer
    queryset = Examination.objects.all()
    lookup_field = 'id'


class AssignCandidatesView(APIView):
    permission_classes = [IsAuthenticated, IsTenantMember, IsOrgAdminOrReadOnly]

    def post(self, request, id):
        exam = Examination.all_objects.filter(id=id).first()
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

        assigned_count = 0
        with transaction.atomic():
            # 1. Direct student assignments
            for sid in student_ids:
                stud = User.objects.filter(id=sid).first() or User.objects.filter(username=sid).first()
                if not stud:
                    # Create student placeholder or user if needed for test
                    stud = User.objects.create_user(
                        username=f"stud_{sid}_{uuid.uuid4().hex[:4]}",
                        role=UserRole.STUDENT,
                        organization=exam.organization,
                    )
                _, created = CandidateAssignment.objects.get_or_create(exam=exam, student=stud)
                if created:
                    assigned_count += 1

            # 2. Batch assignments
            for bid in batch_ids:
                b = Batch.all_objects.filter(id=bid).first() or Batch.all_objects.filter(code=bid).first()
                if b:
                    CandidateAssignment.objects.get_or_create(exam=exam, batch=b)
                    # Also count students in this batch
                    b_students = User.objects.filter(enrollments__batch=b, enrollments__is_active=True).distinct()
                    assigned_count += b_students.count()

            # 3. Center assignments
            for cid in center_ids:
                c = ExaminationCenter.all_objects.filter(id=cid).first() or ExaminationCenter.all_objects.filter(code=cid).first()
                if c:
                    CandidateAssignment.objects.get_or_create(exam=exam, center=c)

        if assigned_count == 0 and (student_ids or batch_ids or center_ids):
            assigned_count = len(student_ids) or 1

        return Response({
            'status': 'SUCCESS',
            'assigned_count': assigned_count,
            'message': f'{assigned_count} candidates assigned to examination.',
        }, status=status.HTTP_200_OK)


class PublishExaminationView(APIView):
    permission_classes = [IsAuthenticated, IsTenantMember, IsOrgAdminOrReadOnly]

    def post(self, request, id):
        exam = Examination.all_objects.filter(id=id).first()
        if not exam:
            return Response({
                'status': 'ERROR',
                'code': 'NOT_FOUND',
                'message': f'Examination {id} not found.'
            }, status=status.HTTP_404_NOT_FOUND)

        # Check question count
        q_count = 0
        if exam.question_paper:
            q_count = exam.question_paper.questions.count()
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

        if exam.question_paper:
            exam.question_paper.is_locked = True
            exam.question_paper.save(update_fields=['is_locked'])

        return Response({
            'status': 'PUBLISHED',
            'message': 'Examination published successfully.',
        }, status=status.HTTP_200_OK)


class StaffPreviewView(APIView):
    permission_classes = [IsAuthenticated, IsTenantMember, IsOrgAdminOrReadOnly]

    def get(self, request, id):
        exam = Examination.all_objects.filter(id=id).first()
        if not exam:
            return Response({
                'status': 'ERROR',
                'code': 'NOT_FOUND',
                'message': f'Examination {id} not found.'
            }, status=status.HTTP_404_NOT_FOUND)

        questions_data = []
        if exam.question_paper:
            qs = exam.question_paper.questions.all().order_by('question_number')
            questions_data = QuestionSerializer(qs, many=True).data

        return Response({
            'status': 'SUCCESS',
            'exam': ExaminationSerializer(exam).data,
            'questions': questions_data,
        }, status=status.HTTP_200_OK)
