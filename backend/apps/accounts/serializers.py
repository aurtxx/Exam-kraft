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


class FacultyMemberSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='profile.full_name', required=False)
    subjects = serializers.ListField(child=serializers.CharField(), required=False)
    department = serializers.CharField(source='faculty_profile.department', required=False, allow_blank=True)
    centre_ids = serializers.ListField(child=serializers.CharField(), required=False, write_only=True)
    batch_ids = serializers.ListField(child=serializers.CharField(), required=False, write_only=True)
    subject_ids = serializers.ListField(child=serializers.CharField(), required=False, write_only=True)
    centres = serializers.SerializerMethodField()
    batches = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'name',
            'email',
            'phone',
            'role',
            'department',
            'subjects',
            'subject_ids',
            'centres',
            'centre_ids',
            'batches',
            'batch_ids',
            'is_active',
            'date_joined',
        ]
        read_only_fields = ['id', 'date_joined']

    def get_centres(self, obj):
        if hasattr(obj, 'faculty_profile'):
            return [c.name for c in obj.faculty_profile.assigned_centers.all()]
        return []

    def get_batches(self, obj):
        if hasattr(obj, 'faculty_profile'):
            return [b.name for b in obj.faculty_profile.assigned_batches.all()]
        return []

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        # Ensure subjects comes from faculty_profile
        if hasattr(instance, 'faculty_profile') and instance.faculty_profile.subjects:
            ret['subjects'] = instance.faculty_profile.subjects
        else:
            ret['subjects'] = ret.get('subjects') or []
        ret['name'] = instance.profile.full_name if hasattr(instance, 'profile') else instance.username
        return ret


class StudentMemberSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='profile.full_name', required=False)
    roll_number = serializers.CharField(required=False)
    batch_id = serializers.CharField(required=False, write_only=True, allow_null=True)
    centre_id = serializers.CharField(required=False, write_only=True, allow_null=True)
    batch_name = serializers.SerializerMethodField()
    centre_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'name',
            'roll_number',
            'email',
            'phone',
            'role',
            'batch_id',
            'centre_id',
            'batch_name',
            'centre_name',
            'is_active',
            'date_joined',
        ]
        read_only_fields = ['id', 'date_joined']

    def get_enrollment(self, obj):
        if hasattr(obj, 'roster_enrollments'):
            return next(iter(obj.roster_enrollments), None)
        return obj.enrollments.filter(is_active=True).select_related('batch', 'center').first()

    def get_batch_name(self, obj):
        enrollment = self.get_enrollment(obj)
        return enrollment.batch.name if enrollment and enrollment.batch else None

    def get_centre_name(self, obj):
        enrollment = self.get_enrollment(obj)
        return enrollment.center.name if enrollment and enrollment.center else None

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['name'] = instance.profile.full_name if hasattr(instance, 'profile') else instance.username
        enrollment = self.get_enrollment(instance)
        ret['roll_number'] = enrollment.roll_number if enrollment else ''
        return ret

