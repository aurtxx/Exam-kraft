import uuid
from typing import Optional
from django.utils.deprecation import MiddlewareMixin
from rest_framework_simplejwt.tokens import AccessToken
from .models import Organization
from .context import set_current_tenant, clear_current_tenant


class TenantMiddleware(MiddlewareMixin):
    """
    Resolves the active tenant Organization from:
    1. Authenticated User / JWT token claims
    2. 'X-Tenant-ID' request header (UUID or slug)
    3. Host subdomain mapping (e.g. {slug}.examkraft.in)
    and binds it to thread/task context via contextvars.
    """

    def process_request(self, request):
        if request.path_info in ("/healthz/", "/readyz/"):
            return None
        tenant: Optional[Organization] = None

        # 1. Try to resolve from Authorization header (JWT)
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Bearer '):
            token_str = auth_header.split(' ')[1].strip()
            try:
                token = AccessToken(token_str)
                org_id = token.get('org_id')
                if org_id:
                    tenant = self._get_organization(str(org_id))
            except Exception:
                pass

        # 2. Try X-Tenant-ID header
        if not tenant:
            header_tenant = request.META.get('HTTP_X_TENANT_ID')
            if header_tenant:
                tenant = self._get_organization(header_tenant.strip())

        # 3. Try Host Subdomain
        if not tenant:
            host = request.get_host().split(':')[0].lower()
            # Check domain direct match
            tenant = Organization.objects.filter(domain=host, is_active=True).first()
            if not tenant:
                parts = host.split('.')
                if len(parts) >= 3 and parts[0] not in ('www', 'api', 'app', 'localhost'):
                    tenant = Organization.objects.filter(slug=parts[0], is_active=True).first()

        # 4. Fallback to authenticated user's organization if available
        if not tenant and hasattr(request, 'user') and request.user.is_authenticated:
            tenant = getattr(request.user, 'organization', None)

        request.tenant = tenant
        set_current_tenant(tenant)

    def process_response(self, request, response):
        clear_current_tenant()
        return response

    def process_exception(self, request, exception):
        clear_current_tenant()
        return None

    def _get_organization(self, identifier: str) -> Optional[Organization]:
        """Fetch active organization by UUID, slug, or domain."""
        try:
            val_uuid = uuid.UUID(identifier)
            org = Organization.objects.filter(id=val_uuid, is_active=True).first()
            if org:
                return org
        except (ValueError, TypeError):
            pass

        # Try slug
        org = Organization.objects.filter(slug=identifier, is_active=True).first()
        if org:
            return org

        # Try domain
        return Organization.objects.filter(domain=identifier, is_active=True).first()
