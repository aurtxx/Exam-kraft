from uuid import UUID
from django.utils import timezone
from django.db import models, transaction
from rest_framework import status, generics, exceptions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Notice
from .serializers import NoticeSerializer
from apps.organizations.models import Batch, ExaminationCenter
from apps.accounts.permissions import IsActiveTenantMember, IsOrgAdminOrReadOnly, require_tenant


def resolve_targets(model, tenant, values, field):
    try:
        ids = {UUID(str(value)) for value in values}
    except (TypeError, ValueError):
        raise exceptions.ValidationError({field: 'Expected a list of valid IDs.'})
    targets = list(model.all_objects.filter(organization=tenant, pk__in=ids))
    if len(targets) != len(ids):
        raise exceptions.ValidationError({field: 'All targets must belong to the active organization.'})
    return targets


class NoticeListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsActiveTenantMember, IsOrgAdminOrReadOnly]

    def get(self, request):
        qs = Notice.objects.filter(organization=require_tenant(request))

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

    @transaction.atomic
    def post(self, request):
        tenant = require_tenant(request)
        data = request.data

        title = data.get('title')
        if not title:
            return Response({
                'status': 'ERROR',
                'code': 'VALIDATION_FAILED',
                'message': 'Notice title is required.'
            }, status=status.HTTP_400_BAD_REQUEST)

        batches = resolve_targets(Batch, tenant, data.get('target_batch_ids', []), 'target_batch_ids')
        centers = resolve_targets(ExaminationCenter, tenant, data.get('target_center_ids', []), 'target_center_ids')

        notice = Notice.all_objects.create(
            organization=tenant,
            title=title,
            content=data.get('content', ''),
            is_active=bool(data.get('is_active', True)),
            start_time=data.get('start_time'),
            end_time=data.get('end_time'),
            created_by=request.user if request.user.is_authenticated else None,
        )

        notice.target_batches.set(batches)
        notice.target_centers.set(centers)

        serializer = NoticeSerializer(notice)
        return Response({
            'status': 'SUCCESS',
            'id': str(notice.id),
            'notice': serializer.data,
            'message': 'Notice published successfully.',
        }, status=status.HTTP_201_CREATED)


class NoticeDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsActiveTenantMember, IsOrgAdminOrReadOnly]
    serializer_class = NoticeSerializer
    lookup_field = 'id'

    def get_queryset(self):
        return Notice.objects.filter(organization=require_tenant(self.request))

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    def perform_update(self, serializer):
        tenant = require_tenant(self.request)
        targets = {}
        for field, alias, model in (
            ('target_batches', 'target_batch_ids', Batch),
            ('target_centers', 'target_center_ids', ExaminationCenter),
        ):
            data = serializer.validated_data
            if alias in data:
                targets[field] = resolve_targets(model, tenant, data.pop(alias), alias)
            elif field in data:
                targets[field] = resolve_targets(model, tenant, [target.pk for target in data[field]], field)
        serializer.save(**targets)
