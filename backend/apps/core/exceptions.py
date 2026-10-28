from django.db import IntegrityError
from django.db.models import ProtectedError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.views import set_rollback


def api_exception_handler(exc, context):
    """DRF handler plus friendly 409 responses for database-level conflicts."""
    if isinstance(exc, ProtectedError):
        set_rollback()
        return Response({"detail": "This record cannot be deleted because other records depend on it."}, status=409)
    if isinstance(exc, IntegrityError):
        set_rollback()
        return Response({"detail": "The change conflicts with existing data."}, status=409)
    return drf_exception_handler(exc, context)
