from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenRefreshView
from .serializers import LoginSerializer, LogoutSerializer, UserSerializer
from apps.organizations.serializers import OrganizationSerializer


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
