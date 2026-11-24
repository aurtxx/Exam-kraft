from rest_framework import status, generics, exceptions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.accounts.permissions import IsOrgAdmin, IsTenantMember, IsOrgAdminOrReadOnly
from .models import Organization, ExaminationCenter, Batch
from .serializers import (
    OrganizationSerializer,
    OrganizationBrandingSerializer,
    ExaminationCenterSerializer,
    BatchSerializer,
)
from .context import get_current_tenant


class CurrentOrganizationView(APIView):
    permission_classes = [IsAuthenticated, IsTenantMember]

    def get_object(self):
        tenant = get_current_tenant()
        if not tenant and hasattr(self.request.user, 'organization'):
            tenant = self.request.user.organization
        return tenant

    def get(self, request):
        org = self.get_object()
        if not org:
            return Response(
                {
                    'status': 'ERROR',
                    'code': 'TENANT_NOT_FOUND',
                    'message': 'No active organization found in current context.',
                },
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = OrganizationSerializer(org)
        return Response(
            {
                'status': 'SUCCESS',
                'organization': serializer.data,
            },
            status=status.HTTP_200_OK
        )

    def patch(self, request):
        # Restricted to SuperAdmin or OrgAdmin
        if not (request.user.is_superadmin or request.user.is_orgadmin):
            return Response(
                {
                    'status': 'ERROR',
                    'code': 'PERMISSION_DENIED',
                    'message': 'Only organization administrators can update branding.',
                },
                status=status.HTTP_403_FORBIDDEN
            )

        org = self.get_object()
        if not org:
            return Response(
                {
                    'status': 'ERROR',
                    'code': 'TENANT_NOT_FOUND',
                    'message': 'No active organization found to update.',
                },
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = OrganizationBrandingSerializer(org, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    'status': 'SUCCESS',
                    'organization': OrganizationSerializer(org).data,
                    'message': 'Organization branding updated successfully.',
                },
                status=status.HTTP_200_OK
            )
        return Response(
            {
                'status': 'ERROR',
                'code': 'VALIDATION_FAILED',
                'errors': serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST
        )


class ExaminationCenterListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsTenantMember, IsOrgAdminOrReadOnly]
    serializer_class = ExaminationCenterSerializer

    def permission_denied(self, request, message=None, code=None):
        if request.authenticators and not request.successful_authenticator:
            raise exceptions.NotAuthenticated()
        raise exceptions.PermissionDenied(
            detail={
                'status': 'ERROR',
                'code': code or 'PERMISSION_DENIED',
                'message': message or 'Only organization administrators can create or modify examination centers.',
            },
            code=code or 'PERMISSION_DENIED'
        )

    def get_queryset(self):
        return ExaminationCenter.objects.all()

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'status': 'SUCCESS',
            'centers': serializer.data,
        })

    def create(self, request, *args, **kwargs):
        tenant = get_current_tenant() or getattr(request.user, 'organization', None)
        capacity = request.data.get('capacity')
        if capacity is not None:
            try:
                if int(capacity) <= 0:
                    return Response({
                        'status': 'ERROR',
                        'code': 'INVALID_CAPACITY',
                        'message': 'Examination center capacity must be greater than zero.'
                    }, status=status.HTTP_400_BAD_REQUEST)
            except (ValueError, TypeError):
                return Response({
                    'status': 'ERROR',
                    'code': 'INVALID_CAPACITY',
                    'message': 'Examination center capacity must be a valid integer.'
                }, status=status.HTTP_400_BAD_REQUEST)

        code = request.data.get('code')
        if code and tenant:
            if ExaminationCenter.all_objects.filter(organization=tenant, code=code).exists():
                return Response({
                    'status': 'ERROR',
                    'code': 'DUPLICATE_CODE',
                    'message': f'Examination center with code {code} already exists in this organization.'
                }, status=status.HTTP_409_CONFLICT)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        tenant = get_current_tenant() or self.request.user.organization
        serializer.save(organization=tenant)


class ExaminationCenterDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsTenantMember, IsOrgAdminOrReadOnly]
    serializer_class = ExaminationCenterSerializer
    lookup_field = 'id'

    def get_queryset(self):
        return ExaminationCenter.objects.all()

    def update(self, request, *args, **kwargs):
        capacity = request.data.get('capacity')
        if capacity is not None:
            try:
                if int(capacity) <= 0:
                    return Response({
                        'status': 'ERROR',
                        'code': 'INVALID_CAPACITY',
                        'message': 'Examination center capacity must be greater than zero.'
                    }, status=status.HTTP_400_BAD_REQUEST)
            except (ValueError, TypeError):
                return Response({
                    'status': 'ERROR',
                    'code': 'INVALID_CAPACITY',
                    'message': 'Examination center capacity must be a valid integer.'
                }, status=status.HTTP_400_BAD_REQUEST)

        return super().update(request, *args, **kwargs)


class BatchListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsTenantMember, IsOrgAdminOrReadOnly]
    serializer_class = BatchSerializer

    def permission_denied(self, request, message=None, code=None):
        if request.authenticators and not request.successful_authenticator:
            raise exceptions.NotAuthenticated()
        raise exceptions.PermissionDenied(
            detail={
                'status': 'ERROR',
                'code': code or 'PERMISSION_DENIED',
                'message': message or 'Only organization administrators can create or modify batches.',
            },
            code=code or 'PERMISSION_DENIED'
        )

    def get_queryset(self):
        return Batch.objects.all()

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'status': 'SUCCESS',
            'batches': serializer.data,
        })

    def create(self, request, *args, **kwargs):
        tenant = get_current_tenant() or getattr(request.user, 'organization', None)
        code = request.data.get('code')
        if code and tenant:
            if Batch.all_objects.filter(organization=tenant, code=code).exists():
                return Response({
                    'status': 'ERROR',
                    'code': 'DUPLICATE_CODE',
                    'message': f'Batch with code {code} already exists in this organization.'
                }, status=status.HTTP_409_CONFLICT)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        tenant = get_current_tenant() or self.request.user.organization
        serializer.save(organization=tenant)


class BatchDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsTenantMember, IsOrgAdminOrReadOnly]
    serializer_class = BatchSerializer
    lookup_field = 'id'

    def get_queryset(self):
        return Batch.objects.all()


class SelectFieldsView(APIView):
    permission_classes = [IsAuthenticated, IsTenantMember]

    def get(self, request):
        batches = Batch.objects.filter(is_active=True).values('id', 'name', 'code', 'stream')
        centers = ExaminationCenter.objects.filter(is_active=True).values('id', 'name', 'code', 'capacity')

        return Response(
            {
                'status': 'SUCCESS',
                'classes': list(batches),
                'centres': list(centers),
            },
            status=status.HTTP_200_OK
        )
