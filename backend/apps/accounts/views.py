import io
import csv
import uuid
from django.db import transaction
from rest_framework import status, generics, exceptions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser, BaseParser
from rest_framework_simplejwt.views import TokenRefreshView
from .models import User, UserProfile, UserRole, FacultyProfile
from .serializers import (
    LoginSerializer,
    LogoutSerializer,
    UserSerializer,
    FacultyMemberSerializer,
    StudentMemberSerializer,
)
from apps.organizations.models import Organization, Batch, ExaminationCenter, StudentBatchEnrollment
from apps.organizations.serializers import OrganizationSerializer
from apps.organizations.context import get_current_tenant
from apps.accounts.permissions import IsOrgAdmin, IsTenantMember, IsOrgAdminOrReadOnly


class PlainTextOrCSVParser(BaseParser):
    media_type = 'text/csv'

    def parse(self, stream, media_type=None, parser_context=None):
        return stream.read()


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    'status': 'ERROR',
                    'code': 'INVALID_CREDENTIALS',
                    'message': 'Invalid username or password provided.',
                    'errors': serializer.errors,
                },
                status=status.HTTP_401_UNAUTHORIZED
            )

        user = serializer.validated_data['user']
        access = serializer.validated_data['access']
        refresh = serializer.validated_data['refresh']

        user_data = UserSerializer(user).data
        org_data = OrganizationSerializer(user.organization).data if user.organization else None

        return Response(
            {
                'status': 'SUCCESS',
                'access': access,
                'refresh': refresh,
                'user': user_data,
                'organization': org_data,
                'message': 'Authentication successful',
            },
            status=status.HTTP_200_OK
        )


class CustomTokenRefreshView(TokenRefreshView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            return Response(
                {
                    'status': 'SUCCESS',
                    'access': response.data.get('access'),
                    'refresh': response.data.get('refresh'),
                },
                status=status.HTTP_200_OK
            )
        return response


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_data = UserSerializer(request.user).data
        org_data = OrganizationSerializer(request.user.organization).data if request.user.organization else None
        return Response(
            {
                'status': 'SUCCESS',
                'user': user_data,
                'organization': org_data,
            },
            status=status.HTTP_200_OK
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=False)
        return Response(
            {
                'status': 'SUCCESS',
                'message': 'Successfully logged out.',
            },
            status=status.HTTP_200_OK
        )


# ==============================================================================
# Faculty Roster Management
# ==============================================================================

class FacultyListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsTenantMember, IsOrgAdminOrReadOnly]

    def get_tenant(self, request, kwargs):
        org_id = kwargs.get('org_id')
        if org_id:
            return Organization.objects.filter(id=org_id).first()
        return get_current_tenant() or getattr(request.user, 'organization', None)

    def get(self, request, *args, **kwargs):
        tenant = self.get_tenant(request, kwargs)
        qs = User.objects.filter(role=UserRole.FACULTY)
        if tenant:
            qs = qs.filter(organization=tenant)

        serializer = FacultyMemberSerializer(qs, many=True)
        return Response({
            'status': 'SUCCESS',
            'faculties': serializer.data,
        }, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        tenant = self.get_tenant(request, kwargs)
        data = request.data
        name = data.get('name') or data.get('full_name') or 'Faculty Member'
        email = data.get('email')
        phone = data.get('phone')
        username = data.get('username') or email or f"fac_{uuid.uuid4().hex[:8]}"
        password = data.get('password') or 'FacultyPass#2026'
        is_active = data.get('is_active', True)
        department = data.get('department', '')

        subjects = data.get('subjects') or data.get('subject_ids') or []
        batch_ids = data.get('batch_ids') or []
        centre_ids = data.get('centre_ids') or []

        with transaction.atomic():
            user = User.objects.create_user(
                username=username,
                email=email,
                phone=phone,
                password=password,
                role=UserRole.FACULTY,
                organization=tenant,
                is_active=is_active,
            )
            UserProfile.objects.create(user=user, full_name=name)
            fac_profile = FacultyProfile.objects.create(
                user=user,
                department=department,
                subjects=subjects,
            )
            if batch_ids:
                batches = Batch.all_objects.filter(id__in=batch_ids)
                fac_profile.assigned_batches.set(batches)
            if centre_ids:
                centers = ExaminationCenter.all_objects.filter(id__in=centre_ids)
                fac_profile.assigned_centers.set(centers)

        serializer = FacultyMemberSerializer(user)
        resp_data = serializer.data
        resp_data['status'] = 'SUCCESS'
        return Response(resp_data, status=status.HTTP_201_CREATED)


class FacultyDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsTenantMember, IsOrgAdminOrReadOnly]
    serializer_class = FacultyMemberSerializer
    queryset = User.objects.filter(role=UserRole.FACULTY)
    lookup_field = 'id'


# ==============================================================================
# Student Roster Management & Pagination
# ==============================================================================

class StudentListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsTenantMember, IsOrgAdminOrReadOnly]

    def get_tenant(self, request, kwargs):
        org_id = kwargs.get('org_id')
        if org_id:
            return Organization.objects.filter(id=org_id).first()
        return get_current_tenant() or getattr(request.user, 'organization', None)

    def get(self, request, *args, **kwargs):
        tenant = self.get_tenant(request, kwargs)

        page_size_param = request.query_params.get('page_size', '25')
        try:
            page_size = int(page_size_param)
            if page_size <= 0:
                return Response({
                    'status': 'ERROR',
                    'code': 'INVALID_PAGE_SIZE',
                    'message': 'page_size must be greater than zero.'
                }, status=status.HTTP_400_BAD_REQUEST)
        except ValueError:
            return Response({
                'status': 'ERROR',
                'code': 'INVALID_PAGE_SIZE',
                'message': 'page_size must be a valid integer.'
            }, status=status.HTTP_400_BAD_REQUEST)

        page_param = request.query_params.get('page', '1')
        try:
            page = max(1, int(page_param))
        except ValueError:
            page = 1

        qs = User.objects.filter(role=UserRole.STUDENT)
        if tenant:
            qs = qs.filter(organization=tenant)

        search = request.query_params.get('search')
        if search:
            qs = qs.filter(
                username__icontains=search
            ) | qs.filter(
                profile__full_name__icontains=search
            ) | qs.filter(
                enrollments__roll_number__icontains=search
            ) | qs.filter(
                email__icontains=search
            )

        batch_id = request.query_params.get('batch_id')
        if batch_id:
            qs = qs.filter(enrollments__batch_id=batch_id)

        centre_id = request.query_params.get('centre_id')
        if centre_id:
            qs = qs.filter(enrollments__center_id=centre_id)

        qs = qs.distinct()
        total_count = qs.count()
        total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1

        start = (page - 1) * page_size
        end = start + page_size

        if start >= total_count and total_count > 0:
            student_list = []
        else:
            page_qs = qs[start:end]
            serializer = StudentMemberSerializer(page_qs, many=True)
            student_list = serializer.data

        return Response({
            'status': 'SUCCESS',
            'count': total_count,
            'total_pages': total_pages,
            'current_page': page,
            'students': student_list,
        }, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        tenant = self.get_tenant(request, kwargs)
        data = request.data
        roll_number = str(data.get('roll_number', '')).strip()
        name = data.get('name') or data.get('full_name') or 'Candidate Student'
        email = data.get('email')
        phone = data.get('phone')
        password = data.get('password') or 'StudentPass#2026'
        batch_id = data.get('batch_id')
        centre_id = data.get('centre_id')
        is_active = data.get('is_active', True)

        if not roll_number:
            return Response({
                'status': 'ERROR',
                'code': 'VALIDATION_FAILED',
                'message': 'roll_number is required.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check duplicate roll number in tenant
        if tenant:
            dup = StudentBatchEnrollment.objects.filter(
                batch__organization=tenant,
                roll_number=roll_number
            ).exists()
            if dup:
                return Response({
                    'status': 'ERROR',
                    'code': 'DUPLICATE_ROLL',
                    'message': f'Roll number {roll_number} is already registered in this organization.'
                }, status=status.HTTP_409_CONFLICT)
        else:
            dup = StudentBatchEnrollment.objects.filter(roll_number=roll_number).exists()
            if dup:
                return Response({
                    'status': 'ERROR',
                    'code': 'DUPLICATE_ROLL',
                    'message': f'Roll number {roll_number} already exists.'
                }, status=status.HTTP_409_CONFLICT)

        batch = None
        if batch_id:
            batch = Batch.all_objects.filter(id=batch_id).first()
        if not batch and tenant:
            batch = Batch.all_objects.filter(organization=tenant).first()
            if not batch:
                batch = Batch.all_objects.create(
                    organization=tenant,
                    name='Default Batch',
                    code=f'DEF_{uuid.uuid4().hex[:4].upper()}'
                )

        center = None
        if centre_id:
            center = ExaminationCenter.all_objects.filter(id=centre_id).first()

        username = data.get('username') or f"stud_{roll_number}_{uuid.uuid4().hex[:4]}"

        with transaction.atomic():
            user = User.objects.create_user(
                username=username,
                email=email,
                phone=phone,
                password=password,
                role=UserRole.STUDENT,
                organization=tenant,
                is_active=is_active,
            )
            UserProfile.objects.create(user=user, full_name=name)
            if batch:
                StudentBatchEnrollment.objects.create(
                    student=user,
                    batch=batch,
                    center=center,
                    roll_number=roll_number,
                    is_active=is_active,
                )

        serializer = StudentMemberSerializer(user)
        data = serializer.data
        return Response({
            'status': 'SUCCESS',
            'id': str(user.id),
            'student': data,
            'message': 'Student created successfully.'
        }, status=status.HTTP_201_CREATED)


class StudentDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsTenantMember, IsOrgAdminOrReadOnly]
    serializer_class = StudentMemberSerializer
    queryset = User.objects.filter(role=UserRole.STUDENT)
    lookup_field = 'id'


# ==============================================================================
# Bulk Student CSV/Excel Ingestion with Transaction Rollback
# ==============================================================================

class StudentBulkImportView(APIView):
    permission_classes = [IsAuthenticated, IsTenantMember, IsOrgAdminOrReadOnly]
    parser_classes = [MultiPartParser, FormParser, JSONParser, PlainTextOrCSVParser]

    def post(self, request, *args, **kwargs):
        org_id = kwargs.get('org_id')
        tenant = None
        if org_id:
            tenant = Organization.objects.filter(id=org_id).first()
        if not tenant:
            tenant = get_current_tenant() or getattr(request.user, 'organization', None)

        # Extract file / content
        content = None
        if 'file' in request.FILES:
            uploaded = request.FILES['file']
            content = uploaded.read()
        elif isinstance(request.data, (bytes, str)):
            content = request.data
        elif request.body:
            content = request.body

        if not content:
            return Response({
                'status': 'ERROR',
                'code': 'MALFORMED_HEADER',
                'message': 'Uploaded file is empty.'
            }, status=status.HTTP_400_BAD_REQUEST)

        if isinstance(content, bytes):
            try:
                text = content.decode('utf-8-sig')
            except UnicodeDecodeError:
                text = content.decode('latin-1')
        else:
            text = content

        text = text.strip()
        if not text:
            return Response({
                'status': 'ERROR',
                'code': 'MALFORMED_HEADER',
                'message': 'File contains no text.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Parse CSV
        reader = csv.reader(io.StringIO(text))
        try:
            headers = next(reader)
        except StopIteration:
            return Response({
                'status': 'ERROR',
                'code': 'MALFORMED_HEADER',
                'message': 'No headers found in file.'
            }, status=status.HTTP_400_BAD_REQUEST)

        header_map = {}
        for idx, h in enumerate(headers):
            clean_h = h.strip().lower().replace('_', '').replace(' ', '')
            header_map[clean_h] = idx

        # Required headers check
        # RollNumber (rollnumber, rollno)
        # Name (name, studentname)
        # BatchCode (batchcode, batch)
        has_roll = any(k in header_map for k in ['rollnumber', 'rollno', 'roll'])
        has_name = any(k in header_map for k in ['name', 'studentname', 'fullname'])
        has_batch = any(k in header_map for k in ['batchcode', 'batch', 'classcode'])

        if not (has_roll and has_name and has_batch):
            return Response({
                'status': 'ERROR',
                'code': 'MALFORMED_HEADER',
                'message': 'Missing mandatory CSV headers. Required: RollNumber, Name, BatchCode.'
            }, status=status.HTTP_400_BAD_REQUEST)

        roll_idx = next(header_map[k] for k in ['rollnumber', 'rollno', 'roll'] if k in header_map)
        name_idx = next(header_map[k] for k in ['name', 'studentname', 'fullname'] if k in header_map)
        batch_idx = next(header_map[k] for k in ['batchcode', 'batch', 'classcode'] if k in header_map)
        email_idx = next((header_map[k] for k in ['email', 'emailaddress'] if k in header_map), None)
        phone_idx = next((header_map[k] for k in ['phone', 'phonenumber', 'mobile'] if k in header_map), None)
        centre_idx = next((header_map[k] for k in ['centrecode', 'centercode', 'center', 'centre'] if k in header_map), None)
        pass_idx = next((header_map[k] for k in ['password', 'pin'] if k in header_map), None)

        rows = list(reader)
        errors = []
        seen_rolls = set()
        to_create = []

        # Validate rows
        for row_num, row in enumerate(rows, start=2):
            if not row or all(not cell.strip() for cell in row):
                continue

            if len(row) <= max(roll_idx, name_idx, batch_idx):
                errors.append(f"Row {row_num}: Missing required columns.")
                continue

            r_num = row[roll_idx].strip()
            r_name = row[name_idx].strip()
            r_batch_code = row[batch_idx].strip()
            r_email = row[email_idx].strip() if email_idx is not None and len(row) > email_idx else ''
            r_phone = row[phone_idx].strip() if phone_idx is not None and len(row) > phone_idx else ''
            r_centre_code = row[centre_idx].strip() if centre_idx is not None and len(row) > centre_idx else ''
            r_pass = row[pass_idx].strip() if pass_idx is not None and len(row) > pass_idx else 'StudentPass#2026'

            if not r_num:
                errors.append(f"Row {row_num}: Roll number is empty.")
            if not r_name:
                errors.append(f"Row {row_num}: Student name is empty.")
            if not r_batch_code:
                errors.append(f"Row {row_num}: Batch code is empty.")

            if r_num in seen_rolls:
                errors.append(f"Row {row_num}: Duplicate roll number '{r_num}' within CSV file.")
            seen_rolls.add(r_num)

            # Check if batch exists
            batch = None
            if tenant:
                batch = Batch.all_objects.filter(organization=tenant, code=r_batch_code).first()
            else:
                batch = Batch.all_objects.filter(code=r_batch_code).first()

            if not batch:
                # If batch doesn't exist, create it or report error
                # In reference, batch is resolved or created
                if tenant:
                    batch = Batch.all_objects.create(
                        organization=tenant,
                        name=f"Batch {r_batch_code}",
                        code=r_batch_code,
                    )

            # Check if center exists
            center = None
            if r_centre_code:
                if tenant:
                    center = ExaminationCenter.all_objects.filter(organization=tenant, code=r_centre_code).first()
                else:
                    center = ExaminationCenter.all_objects.filter(code=r_centre_code).first()
                if not center and tenant:
                    center = ExaminationCenter.all_objects.create(
                        organization=tenant,
                        name=f"Center {r_centre_code}",
                        code=r_centre_code,
                        capacity=100
                    )

            # Check DB duplicate roll
            if tenant and StudentBatchEnrollment.objects.filter(batch__organization=tenant, roll_number=r_num).exists():
                errors.append(f"Row {row_num}: Roll number '{r_num}' already exists in database.")

            to_create.append({
                'roll_number': r_num,
                'name': r_name,
                'email': r_email,
                'phone': r_phone,
                'batch': batch,
                'center': center,
                'password': r_pass,
            })

        # If any validation errors, fail completely and rollback
        if errors:
            return Response({
                'status': 'ERROR',
                'code': 'VALIDATION_FAILED',
                'created': 0,
                'created_count': 0,
                'total_processed': len(to_create),
                'errors': errors,
            }, status=status.HTTP_400_BAD_REQUEST)

        created_count = 0
        with transaction.atomic():
            for item in to_create:
                u_name = f"stud_{item['roll_number']}_{uuid.uuid4().hex[:4]}"
                user = User.objects.create_user(
                    username=u_name,
                    email=item['email'] or None,
                    phone=item['phone'] or None,
                    password=item['password'],
                    role=UserRole.STUDENT,
                    organization=tenant,
                )
                UserProfile.objects.create(user=user, full_name=item['name'])
                if item['batch']:
                    StudentBatchEnrollment.objects.create(
                        student=user,
                        batch=item['batch'],
                        center=item['center'],
                        roll_number=item['roll_number'],
                    )
                created_count += 1

        return Response({
            'status': 'SUCCESS',
            'created': created_count,
            'created_count': created_count,
            'total_processed': created_count,
            'updated_count': 0,
            'errors': [],
            'message': f'Successfully imported {created_count} students.',
        }, status=status.HTTP_200_OK)
