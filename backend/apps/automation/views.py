from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsPrivileged

from . import rules


class RunWorkflowsView(APIView):
    """Run time-based workflow rules on demand (also available as `manage.py run_workflows`)."""

    permission_classes = [IsPrivileged]

    @extend_schema(
        request=None,
        responses=inline_serializer(
            "WorkflowRunResult", {"flagged": serializers.IntegerField(), "cleared": serializers.IntegerField()}
        ),
    )
    def post(self, request):
        return Response(rules.flag_overdue_leads())
