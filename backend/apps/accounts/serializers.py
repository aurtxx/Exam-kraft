from rest_framework import serializers
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User, UserProfile
from apps.organizations.serializers import OrganizationSerializer


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['full_name', 'avatar_url', 'parent_name', 'parent_phone', 'metadata']


class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)
    organization = OrganizationSerializer(read_only=True)
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'phone',
            'role',
            'is_active',
            'is_staff',
            'date_joined',
            'organization',
            'profile',
            'permissions',
        ]
        read_only_fields = ['id', 'date_joined']

    def get_permissions(self, obj) -> list[str]:
        perms = []
        if obj.is_superadmin:
            perms.extend(['manage_orgs', 'manage_exams', 'manage_users', 'view_reports'])
        elif obj.is_orgadmin:
            perms.extend(['manage_exams', 'manage_users', 'view_reports', 'edit_branding'])
        elif obj.is_faculty:
            perms.extend(['manage_exams', 'grade_exams', 'view_reports'])
        elif obj.is_student:
            perms.extend(['take_exam', 'view_results'])
        return perms


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)
    next = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')

        # Allow login via username, email, or phone
        user = None
        if '@' in username:
            user_obj = User.objects.filter(email__iexact=username, is_active=True).first()
            if user_obj:
                username = user_obj.username
        else:
            user_obj = User.objects.filter(phone=username, is_active=True).first()
            if user_obj:
                username = user_obj.username

        user = authenticate(username=username, password=password)
        if not user:
            raise serializers.ValidationError({
                'code': 'INVALID_CREDENTIALS',
                'message': 'Invalid username or password provided.',
            })

        if not user.is_active:
            raise serializers.ValidationError({
                'code': 'ACCOUNT_DISABLED',
                'message': 'This account has been deactivated.',
            })

        # Generate tokens
        refresh = RefreshToken.for_user(user)
        # Custom claims
        if user.organization_id:
            refresh['org_id'] = str(user.organization_id)
        refresh['role'] = user.role
        refresh['username'] = user.username

        attrs['user'] = user
        attrs['refresh'] = str(refresh)
        attrs['access'] = str(refresh.access_token)
        return attrs


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=True)

    def validate(self, attrs):
        refresh_token = attrs.get('refresh')
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            # Idempotent: even if token was already blacklisted or invalid, proceed
            pass
        return attrs
