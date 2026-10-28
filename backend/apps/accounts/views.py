from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.core.permissions import IsAdminRole

from .models import User
from .serializers import LoginSerializer, UserSerializer, UserWriteSerializer


class LoginView(TokenObtainPairView):
    """Exchange username + password for JWT access/refresh tokens (rate limited)."""

    serializer_class = LoginSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"


class RefreshView(TokenRefreshView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"


class LogoutView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(
        request=inline_serializer("Logout", {"refresh": serializers.CharField()}),
        responses={204: None},
        auth=[],
    )
    def post(self, request):
        token = request.data.get("refresh")
        if token:
            try:
                RefreshToken(token).blacklist()
            except TokenError:
                pass  # already invalid/expired: logout is idempotent
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=UserSerializer)
    def get(self, request):
        return Response(UserSerializer(request.user).data)


class UserViewSet(viewsets.ModelViewSet):
    """Everyone can list active users (for owner pickers); only admins manage accounts.

    Users are deactivated rather than deleted so historical records keep their owner.
    """

    http_method_names = ["get", "post", "put", "patch", "head", "options"]
    search_fields = ["username", "first_name", "last_name", "email"]
    ordering_fields = ["first_name", "last_name", "username", "role"]
    filterset_fields = ["role", "is_active"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = User.objects.all()
        if getattr(self, "swagger_fake_view", False):
            return qs.none()
        user = self.request.user
        if not (user.is_superuser or user.role == User.Role.ADMIN):
            qs = qs.filter(is_active=True)
        return qs

    def get_serializer_class(self):
        return UserSerializer if self.action in ("list", "retrieve") else UserWriteSerializer
