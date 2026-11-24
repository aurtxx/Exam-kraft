from django.urls import path
from .views import LoginView, CustomTokenRefreshView, MeView, LogoutView

urlpatterns = [
    path('login/', LoginView.as_view(), name='auth-login'),
    path('token/refresh/', CustomTokenRefreshView.as_view(), name='token-refresh'),
    path('me/', MeView.as_view(), name='auth-me'),
    path('logout/', LogoutView.as_view(), name='auth-logout'),
]
