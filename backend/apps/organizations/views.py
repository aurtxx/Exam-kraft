from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.accounts.permissions import IsOrgAdmin, IsTenantMember
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
    permission_classes = [IsAuthenticated, IsTenantMember]
    serializer_class = ExaminationCenterSerializer

    def get_queryset(self):
        # TenantManager automatically filters by current tenant
        return ExaminationCenter.objects.all()

    def perform_create(self, serializer):
        tenant = get_current_tenant() or self.request.user.organization
        serializer.save(organization=tenant)


class BatchListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsTenantMember]
    serializer_class = BatchSerializer

    def get_queryset(self):
        return Batch.objects.all()

    def perform_create(self, serializer):
        tenant = get_current_tenant() or self.request.user.organization
        serializer.save(organization=tenant)


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
