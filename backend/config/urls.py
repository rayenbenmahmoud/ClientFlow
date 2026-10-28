from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from apps.accounts.views import LoginView, LogoutView, MeView, RefreshView, UserViewSet
from apps.activities.views import InteractionViewSet, NotificationViewSet, TaskViewSet
from apps.automation.views import RunWorkflowsView
from apps.core.views import HealthView
from apps.crm.views import CompanyViewSet, ContactViewSet, TagViewSet
from apps.dashboard.views import DashboardView
from apps.sales.views import DealViewSet, LeadViewSet

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")
router.register("tags", TagViewSet, basename="tag")
router.register("companies", CompanyViewSet, basename="company")
router.register("contacts", ContactViewSet, basename="contact")
router.register("leads", LeadViewSet, basename="lead")
router.register("deals", DealViewSet, basename="deal")
router.register("tasks", TaskViewSet, basename="task")
router.register("interactions", InteractionViewSet, basename="interaction")
router.register("notifications", NotificationViewSet, basename="notification")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", HealthView.as_view(), name="health"),
    path("api/auth/login/", LoginView.as_view(), name="auth-login"),
    path("api/auth/refresh/", RefreshView.as_view(), name="auth-refresh"),
    path("api/auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("api/auth/me/", MeView.as_view(), name="auth-me"),
    path("api/dashboard/", DashboardView.as_view(), name="dashboard"),
    path("api/automation/run/", RunWorkflowsView.as_view(), name="automation-run"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("api/", include(router.urls)),
]
