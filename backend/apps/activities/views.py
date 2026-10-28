from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.csv_export import CsvExportMixin
from apps.core.permissions import CrmObjectPermission, OwnerScopedMixin

from .filters import InteractionFilter, NotificationFilter, TaskFilter
from .models import Interaction, Notification, Task
from .serializers import InteractionSerializer, NotificationSerializer, TaskSerializer


class InteractionViewSet(viewsets.ModelViewSet):
    """Calls, meetings, emails and notes. Reps can edit/delete only their own entries; workflow notes are read-only."""

    serializer_class = InteractionSerializer
    permission_classes = [CrmObjectPermission]
    filterset_class = InteractionFilter
    search_fields = ["subject", "notes"]
    ordering_fields = ["occurred_at", "created_at", "type"]
    ordering = ["-occurred_at", "-id"]
    owner_field = "created_by"
    rep_can_delete_own = True
    rep_edit_own_only = True

    def get_queryset(self):
        return Interaction.objects.select_related("contact", "company", "deal", "lead", "created_by")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def _guard_system(self, instance):
        if instance.is_system:
            raise PermissionDenied("Automatically generated entries cannot be changed.")

    def perform_update(self, serializer):
        self._guard_system(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self._guard_system(instance)
        instance.delete()


class TaskViewSet(OwnerScopedMixin, CsvExportMixin, viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    permission_classes = [CrmObjectPermission]
    filterset_class = TaskFilter
    search_fields = ["title", "description"]
    ordering_fields = ["due_date", "created_at", "title", "status"]
    ordering = ["due_date", "id"]
    owner_field = "assignee"
    rep_can_delete_own = True
    csv_basename = "tasks"
    csv_fields = [
        ("ID", "id"),
        ("Title", "title"),
        ("Due date", "due_date"),
        ("Status", "get_status_display"),
        ("Priority", "get_priority_display"),
        ("Assignee", "assignee.display_name"),
        ("Overdue", "is_overdue"),
        ("Lead", "lead.full_name"),
        ("Deal", "deal.title"),
        ("Contact", "contact.full_name"),
        ("Completed at", "completed_at"),
        ("Automatic", "auto_created"),
    ]

    def get_queryset(self):
        return self.scope(Task.objects.select_related("assignee", "lead", "deal", "contact"))

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @extend_schema(request=None, responses=TaskSerializer)
    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        task = self.get_object()
        if task.status != Task.Status.DONE:
            task.status = Task.Status.DONE
            task.completed_at = timezone.now()
            task.save(update_fields=["status", "completed_at", "updated_at"])
        return Response(self.get_serializer(task).data)

    @extend_schema(request=None, responses=TaskSerializer)
    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        task = self.get_object()
        if task.status != Task.Status.OPEN:
            task.status = Task.Status.OPEN
            task.completed_at = None
            task.save(update_fields=["status", "completed_at", "updated_at"])
        return Response(self.get_serializer(task).data)


class NotificationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """In-app notifications for the current user only."""

    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = NotificationFilter
    ordering_fields = ["created_at"]
    ordering = ["-created_at", "-id"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Notification.objects.none()
        return Notification.objects.filter(recipient=self.request.user)

    @extend_schema(request=None, responses=NotificationSerializer)
    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        notification = self.get_object()
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at"])
        return Response(self.get_serializer(notification).data)

    @extend_schema(request=None, responses=inline_serializer("MarkedRead", {"marked": serializers.IntegerField()}))
    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request):
        marked = self.get_queryset().filter(read_at__isnull=True).update(read_at=timezone.now())
        return Response({"marked": marked})

    @extend_schema(responses=inline_serializer("UnreadCount", {"unread": serializers.IntegerField()}))
    @action(detail=False, methods=["get"], url_path="unread-count", pagination_class=None)
    def unread_count(self, request):
        return Response({"unread": self.get_queryset().filter(read_at__isnull=True).count()})
