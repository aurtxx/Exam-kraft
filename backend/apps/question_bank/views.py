import uuid
from django.db import transaction
from django.shortcuts import get_object_or_404
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
    mcq_options_error,
    prepare_options,
)
from apps.accounts.permissions import IsActiveTenantMember, IsOrgAdminOrFaculty, require_tenant


def ensure_paper_unlocked(paper):
    if paper.is_locked:
        raise exceptions.ValidationError({
            'status': 'ERROR',
            'code': 'LOCKED',
            'message': 'Cannot modify a locked or published question paper.',
        })


class QuestionBankListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsActiveTenantMember, IsOrgAdminOrFaculty]

    def get(self, request):
        tenant = require_tenant(request)
        qs = QuestionBank.objects.filter(organization=tenant)

        serializer = QuestionBankSerializer(qs, many=True)
        return Response({
            'status': 'SUCCESS',
            'question_papers': serializer.data,
            'question_banks': serializer.data,
        }, status=status.HTTP_200_OK)

    def post(self, request):
        tenant = require_tenant(request)
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
    permission_classes = [IsAuthenticated, IsActiveTenantMember, IsOrgAdminOrFaculty]
    serializer_class = QuestionBankSerializer
    lookup_field = 'id'

    def get_queryset(self):
        queryset = QuestionBank.objects.filter(organization=require_tenant(self.request))
        if self.request.method in ('PUT', 'PATCH'):
            return queryset.select_for_update()
        return queryset

    def get_object(self):
        instance = super().get_object()
        if self.request.method in ('PUT', 'PATCH'):
            ensure_paper_unlocked(instance)
        return instance

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)


class QuestionListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsActiveTenantMember, IsOrgAdminOrFaculty]

    def get_paper(self, paper_id, tenant):
        if not paper_id:
            return None
        try:
            uuid.UUID(str(paper_id))
        except (ValueError, TypeError, AttributeError):
            return None
        return QuestionBank.all_objects.filter(id=paper_id, organization=tenant).first()

    def get(self, request, paper_id=None):
        tenant = require_tenant(request)
        if paper_id:
            paper = self.get_paper(paper_id, tenant)
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
        qs = Question.objects.filter(question_bank__organization=tenant)

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

    @transaction.atomic
    def post(self, request, paper_id=None):
        data = request.data
        question_number = None
        if 'question_number' in data:
            raw_qnum = data.get('question_number')
            try:
                if isinstance(raw_qnum, (bool, float)):
                    raise ValueError
                if isinstance(raw_qnum, str) and not raw_qnum.isdigit():
                    raise ValueError
                question_number = int(raw_qnum)
                if not 1 <= question_number <= 2147483647:
                    raise ValueError
            except (ValueError, TypeError, OverflowError):
                return Response({
                    'status': 'ERROR',
                    'code': 'INVALID_QUESTION_NUMBER',
                    'message': 'question_number must be an integer between 1 and 2147483647.',
                }, status=status.HTTP_400_BAD_REQUEST)

        qpid = paper_id or data.get('question_bank_id') or data.get('question_paper_id')
        tenant = require_tenant(request)
        paper = self.get_paper(qpid, tenant)
        if qpid and not paper:
            raise exceptions.NotFound('Question paper not found.')

        if not paper:
            paper = QuestionBank.all_objects.filter(organization=tenant).first()

        if paper:
            paper = QuestionBank.all_objects.select_for_update().get(pk=paper.pk, organization=tenant)
            ensure_paper_unlocked(paper)

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

        if not neg_marks <= pos_marks:
            return Response({
                'status': 'ERROR',
                'code': 'INVALID_MARKING',
                'message': f'Negative penalty ({neg_marks}) cannot exceed positive marks ({pos_marks}).'
            }, status=status.HTTP_400_BAD_REQUEST)

        key_val = str(data.get('key', '')).strip()
        options_serializer = OptionSerializer(data=data.get('options', []), many=True)
        options_serializer.is_valid(raise_exception=True)
        options = prepare_options(normalized_type, key_val, options_serializer.validated_data)
        error = mcq_options_error(normalized_type, [option['is_correct'] for option in options])
        if error:
            code, message = error
            return Response({
                'status': 'ERROR',
                'code': code,
                'message': message,
            }, status=status.HTTP_400_BAD_REQUEST)

        if normalized_type == QuestionType.MCQ_SINGLE:
            key_val = next(option['option_key'] for option in options if option['is_correct'])

        # Validate Numerical key
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

        if not paper:
            paper = QuestionBank.all_objects.create(
                organization=tenant,
                name='Default Bank',
                exam_type='GENERAL',
                created_by=request.user if request.user.is_authenticated else None,
            )

        if question_number is None:
            question_number = paper.questions.count() + 1

        question = Question.objects.create(
            question_bank=paper,
            section_name=section_name,
            question_number=question_number,
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
        Option.objects.bulk_create(Option(question=question, **option) for option in options)

        serializer = QuestionSerializer(question)
        ret_data = serializer.data
        return Response({
            'status': 'SUCCESS',
            'id': str(question.id),
            'question': ret_data,
            'message': 'Question authored successfully.',
        }, status=status.HTTP_201_CREATED)


class QuestionDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsActiveTenantMember, IsOrgAdminOrFaculty]
    serializer_class = QuestionSerializer
    queryset = Question.objects.all()
    lookup_field = 'id'

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset().filter(question_bank__organization=require_tenant(self.request))
        if self.request.method in ('PUT', 'PATCH', 'DELETE'):
            return queryset.select_for_update()
        return queryset

    def get_object(self):
        question = super().get_object()
        if self.request.method in ('PUT', 'PATCH', 'DELETE'):
            paper = QuestionBank.all_objects.select_for_update().get(pk=question.question_bank_id, organization=require_tenant(self.request))
            ensure_paper_unlocked(paper)
        return question

    def perform_update(self, serializer):
        paper = serializer.validated_data.get('question_bank')
        if paper and paper.pk != serializer.instance.question_bank_id:
            tenant = require_tenant(self.request)
            if paper.organization_id != tenant.pk:
                raise exceptions.ValidationError({'question_bank': 'Unknown question paper.'})
            ensure_paper_unlocked(QuestionBank.all_objects.select_for_update().get(pk=paper.pk, organization=tenant))
        serializer.save()


class SectionListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsActiveTenantMember, IsOrgAdminOrFaculty]
    serializer_class = SectionSerializer

    def get_queryset(self):
        sections = Section.objects.filter(question_bank__organization=require_tenant(self.request))
        paper_id = self.kwargs.get('paper_id')
        if paper_id:
            return sections.filter(question_bank_id=paper_id)
        return sections

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        paper = get_object_or_404(QuestionBank.objects.select_for_update(), organization=require_tenant(request), pk=self.kwargs['paper_id'])
        ensure_paper_unlocked(paper)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(organization=paper.organization, question_bank=paper)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class TagListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsActiveTenantMember, IsOrgAdminOrFaculty]
    serializer_class = TagSerializer

    def get_queryset(self):
        return Tag.objects.filter(organization=require_tenant(self.request))

    def perform_create(self, serializer):
        tenant = require_tenant(self.request)
        serializer.save(organization=tenant)
