from django.utils import timezone
from django.db import models
from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Notice
from .serializers import NoticeSerializer
from apps.organizations.models import Organization, Batch, ExaminationCenter
from apps.organizations.context import get_current_tenant
from apps.accounts.permissions import IsTenantMember, IsOrgAdminOrReadOnly


class NoticeListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsTenantMember, IsOrgAdminOrReadOnly]

    def get_tenant(self, request):
        return get_current_tenant() or getattr(request.user, 'organization', None)

    def get(self, request):
        tenant = self.get_tenant(request)
        qs = Notice.objects.all()
        if tenant:
            qs = qs.filter(organization=tenant)

        active_only = request.query_params.get('active')
        if active_only and active_only.lower() in ('true', '1'):
            now = timezone.now()
            qs = qs.filter(is_active=True)
            # Filter active window if defined
            qs = qs.filter(
                models.Q(start_time__isnull=True) | models.Q(start_time__lte=now)
            ).filter(
                models.Q(end_time__isnull=True) | models.Q(end_time__gte=now)
            )

        serializer = NoticeSerializer(qs, many=True)
        return Response({
            'status': 'SUCCESS',
            'notices': serializer.data,
        }, status=status.HTTP_200_OK)

    def post(self, request):
        tenant = self.get_tenant(request) or Organization.objects.first()
        data = request.data

        title = data.get('title')
        if not title:
            return Response({
                'status': 'ERROR',
                'code': 'VALIDATION_FAILED',
                'message': 'Notice title is required.'
            }, status=status.HTTP_400_BAD_REQUEST)

        notice = Notice.all_objects.create(
            organization=tenant,
            title=title,
            content=data.get('content', ''),
            is_active=bool(data.get('is_active', True)),
            start_time=data.get('start_time'),
            end_time=data.get('end_time'),
            created_by=request.user if request.user.is_authenticated else None,
        )

        batch_ids = data.get('target_batch_ids', [])
        if batch_ids:
            batches = Batch.all_objects.filter(id__in=batch_ids)
            notice.target_batches.set(batches)

        center_ids = data.get('target_center_ids', [])
        if center_ids:
            centers = ExaminationCenter.all_objects.filter(id__in=center_ids)
            notice.target_centers.set(centers)

        serializer = NoticeSerializer(notice)
        return Response({
            'status': 'SUCCESS',
            'id': str(notice.id),
            'notice': serializer.data,
            'message': 'Notice published successfully.',
        }, status=status.HTTP_201_CREATED)


class NoticeDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsTenantMember, IsOrgAdminOrReadOnly]
    serializer_class = NoticeSerializer
    queryset = Notice.objects.all()
    lookup_field = 'id'
