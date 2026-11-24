import uuid
from django.db import transaction
from rest_framework import status, generics, exceptions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import (
    QuestionBank,
    Section,
    Tag,
    Question,
    Option,
    QuestionType,
    normalize_question_type,
)
from .serializers import (
    QuestionBankSerializer,
    SectionSerializer,
    TagSerializer,
    QuestionSerializer,
    OptionSerializer,
)
from apps.organizations.models import Organization
from apps.organizations.context import get_current_tenant
from apps.accounts.permissions import IsTenantMember, IsOrgAdminOrReadOnly


class QuestionBankListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsTenantMember, IsOrgAdminOrReadOnly]

    def get_tenant(self, request):
        return get_current_tenant() or getattr(request.user, 'organization', None)

    def get(self, request):
        tenant = self.get_tenant(request)
        qs = QuestionBank.objects.all()
        if tenant:
            qs = qs.filter(organization=tenant)

        serializer = QuestionBankSerializer(qs, many=True)
        return Response({
            'status': 'SUCCESS',
            'question_papers': serializer.data,
            'question_banks': serializer.data,
        }, status=status.HTTP_200_OK)

    def post(self, request):
        tenant = self.get_tenant(request)
        if not tenant:
            # Fallback or create default org if needed for testing
            tenant = Organization.objects.first()

        data = request.data
        name = data.get('name') or data.get('title') or 'Untitled Question Paper'
        exam_type = data.get('exam_type', 'GENERAL')
        duration_minutes = int(data.get('duration_minutes', 60))
        instructions = data.get('instructions', '')
        description = data.get('description', '')

        qp = QuestionBank.all_objects.create(
            organization=tenant,
            name=name,
            exam_type=exam_type,
            duration_minutes=duration_minutes,
            instructions=instructions,
            description=description,
            created_by=request.user if request.user.is_authenticated else None,
        )

        return Response({
            'status': 'SUCCESS',
            'id': str(qp.id),
            'name': qp.name,
            'message': 'Question paper initialized.',
            'question_paper': QuestionBankSerializer(qp).data,
        }, status=status.HTTP_201_CREATED)


class QuestionBankDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsTenantMember, IsOrgAdminOrReadOnly]
    serializer_class = QuestionBankSerializer
    queryset = QuestionBank.objects.all()
    lookup_field = 'id'


class QuestionListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsTenantMember, IsOrgAdminOrReadOnly]

    def get_paper(self, paper_id):
        if not paper_id:
            return None
        return QuestionBank.all_objects.filter(id=paper_id).first()

    def get(self, request, paper_id=None):
        if paper_id:
            paper = self.get_paper(paper_id)
            if not paper:
                return Response({
                    'status': 'ERROR',
                    'code': 'NOT_FOUND',
                    'message': f'Question paper {paper_id} not found.'
                }, status=status.HTTP_404_NOT_FOUND)

            questions = paper.questions.all().order_by('question_number')
            q_serializer = QuestionSerializer(questions, many=True)
            return Response({
                'status': 'SUCCESS',
                'metadata': {
                    'id': str(paper.id),
                    'name': paper.name,
                    'duration_minutes': paper.duration_minutes,
                    'total_questions': questions.count(),
                },
                'questions': q_serializer.data,
            }, status=status.HTTP_200_OK)

        # General questions listing
        tenant = get_current_tenant() or getattr(request.user, 'organization', None)
        qs = Question.objects.all()
        if tenant:
            qs = qs.filter(question_bank__organization=tenant)

        section_filter = request.query_params.get('section')
        if section_filter:
            qs = qs.filter(section_name__iexact=section_filter)

        qtype_filter = request.query_params.get('question_type')
        if qtype_filter:
            qs = qs.filter(question_type=normalize_question_type(qtype_filter))

        serializer = QuestionSerializer(qs, many=True)
        return Response({
            'status': 'SUCCESS',
            'questions': serializer.data,
        }, status=status.HTTP_200_OK)

    def post(self, request, paper_id=None):
        data = request.data
        qpid = paper_id or data.get('question_bank_id') or data.get('question_paper_id')
        paper = self.get_paper(qpid)

        if not paper:
            # Fallback: create or find a default question bank
            tenant = get_current_tenant() or getattr(request.user, 'organization', None) or Organization.objects.first()
            paper = QuestionBank.all_objects.filter(organization=tenant).first()
            if not paper:
                paper = QuestionBank.all_objects.create(
                    organization=tenant,
                    name='Default Bank',
                    exam_type='GENERAL',
                    created_by=request.user if request.user.is_authenticated else None
                )

        # Check paper lock
        if paper.is_locked:
            return Response({
                'status': 'ERROR',
                'code': 'LOCKED',
                'message': 'Cannot modify questions in a locked or published question paper.'
            }, status=status.HTTP_403_FORBIDDEN)

        # Validate question type
        raw_type = data.get('question_type')
        if not raw_type:
            return Response({
                'status': 'ERROR',
                'code': 'INVALID_QUESTION_TYPE',
                'message': 'question_type is required.'
            }, status=status.HTTP_400_BAD_REQUEST)

        normalized_type = normalize_question_type(raw_type)
        if normalized_type not in QuestionType.values:
            return Response({
                'status': 'ERROR',
                'code': 'INVALID_QUESTION_TYPE',
                'message': f"Unsupported question type '{raw_type}'."
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validate positive & negative markings
        try:
            pos_marks = float(data.get('positive_marks', data.get('cmk', 4.0)))
            neg_marks = float(data.get('negative_marks', data.get('imk', 0.0)))
            part_marks = float(data.get('partial_marks', data.get('pmk', 0.0)))
        except (ValueError, TypeError):
            return Response({
                'status': 'ERROR',
                'code': 'INVALID_MARKING',
                'message': 'Marking values must be numbers.'
            }, status=status.HTTP_400_BAD_REQUEST)

        if neg_marks > pos_marks:
            return Response({
                'status': 'ERROR',
                'code': 'INVALID_MARKING',
                'message': f'Negative penalty ({neg_marks}) cannot exceed positive marks ({pos_marks}).'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validate MCQ options
        options_data = data.get('options', [])
        if normalized_type in (QuestionType.MCQ_SINGLE, QuestionType.MCQ_MULTI):
            if not options_data or len(options_data) == 0:
                return Response({
                    'status': 'ERROR',
                    'code': 'MISSING_OPTIONS',
                    'message': 'Multiple choice questions require at least one option choice.'
                }, status=status.HTTP_400_BAD_REQUEST)

        # Validate Numerical key
        key_val = str(data.get('key', '')).strip()
        if normalized_type == QuestionType.NUMERICAL:
            if not key_val:
                return Response({
                    'status': 'ERROR',
                    'code': 'INVALID_KEY',
                    'message': 'Numerical question requires an answer key.'
                }, status=status.HTTP_400_BAD_REQUEST)
            try:
                float(key_val)
            except ValueError:
                return Response({
                    'status': 'ERROR',
                    'code': 'INVALID_KEY',
                    'message': f"Numerical question answer key must be numeric, got '{key_val}'."
                }, status=status.HTTP_400_BAD_REQUEST)

        section_name = data.get('section') or data.get('section_name') or 'General'
        content_text = data.get('content_text', '')
        explanation = data.get('explanation', '')
        difficulty = data.get('difficulty', 'MEDIUM')
        if isinstance(difficulty, int):
            difficulty = 'EASY' if difficulty == 1 else ('HARD' if difficulty == 3 else 'MEDIUM')

        # Auto-compute question number
        next_qnum = paper.questions.count() + 1
        qnum = data.get('question_number', next_qnum)

        with transaction.atomic():
            question = Question.objects.create(
                question_bank=paper,
                section_name=section_name,
                question_number=qnum,
                question_type=normalized_type,
                content_text=content_text,
                content_html=data.get('content_html', ''),
                explanation=explanation,
                image_url=data.get('image_url'),
                difficulty=difficulty,
                key=key_val,
                positive_marks=pos_marks,
                negative_marks=neg_marks,
                partial_marks=part_marks,
                is_cancelled=bool(data.get('is_cancelled', data.get('canc', False))),
                numerical_min=data.get('numerical_min'),
                numerical_max=data.get('numerical_max'),
                coding_language=data.get('coding_language', ''),
                code_boilerplate=data.get('code_boilerplate', ''),
                test_cases=data.get('test_cases', []),
            )

            # Create options
            for idx, opt in enumerate(options_data):
                opt_key = opt.get('key') or opt.get('option_key') or chr(65 + idx)
                opt_text = opt.get('text') or opt.get('content_text') or ''
                is_correct = opt.get('is_correct', False)
                # If key matches opt_key, mark correct
                if not is_correct and key_val:
                    if normalized_type == QuestionType.MCQ_SINGLE:
                        is_correct = (opt_key.strip().upper() == key_val.strip().upper())
                    elif normalized_type == QuestionType.MCQ_MULTI:
                        correct_keys = [k.strip().upper() for k in key_val.replace(',', '+').split('+')]
                        is_correct = opt_key.strip().upper() in correct_keys

                Option.objects.create(
                    question=question,
                    option_key=opt_key,
                    content_text=opt_text,
                    content_html=opt.get('content_html', ''),
                    is_correct=is_correct,
                    order=opt.get('order', idx),
                )

        serializer = QuestionSerializer(question)
        ret_data = serializer.data
        return Response({
            'status': 'SUCCESS',
            'id': str(question.id),
            'question': ret_data,
            'message': 'Question authored successfully.',
        }, status=status.HTTP_201_CREATED)


class QuestionDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsTenantMember, IsOrgAdminOrReadOnly]
    serializer_class = QuestionSerializer
    queryset = Question.objects.all()
    lookup_field = 'id'


class SectionListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsTenantMember, IsOrgAdminOrReadOnly]
    serializer_class = SectionSerializer

    def get_queryset(self):
        paper_id = self.kwargs.get('paper_id')
        if paper_id:
            return Section.objects.filter(question_bank_id=paper_id)
        return Section.objects.all()

    def perform_create(self, serializer):
        paper_id = self.kwargs.get('paper_id')
        tenant = get_current_tenant() or self.request.user.organization
        serializer.save(organization=tenant, question_bank_id=paper_id)


class TagListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsTenantMember, IsOrgAdminOrReadOnly]
    serializer_class = TagSerializer

    def get_queryset(self):
        return Tag.objects.all()

    def perform_create(self, serializer):
        tenant = get_current_tenant() or self.request.user.organization
        serializer.save(organization=tenant)
