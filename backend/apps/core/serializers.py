from rest_framework import serializers

from .permissions import is_privileged


def ensure_unique_ci(model, field: str, value: str, instance=None, message: str = "Already exists."):
    qs = model.objects.filter(**{f"{field}__iexact": value})
    if instance is not None:
        qs = qs.exclude(pk=instance.pk)
    if qs.exists():
        raise serializers.ValidationError(message)


class OwnerAssignmentMixin:
    """Defaults the owner to the current user and stops reps assigning records to others."""

    owner_field = "owner"

    def validate(self, attrs):
        attrs = super().validate(attrs)
        user = self.context["request"].user
        field = self.owner_field
        if field in attrs and attrs[field] is not None:
            target = attrs[field]
            if not target.is_active:
                raise serializers.ValidationError({field: "This user is inactive."})
            if not is_privileged(user) and target != user:
                raise serializers.ValidationError({field: "You can only assign records to yourself."})
        elif self.instance is None:
            attrs[field] = user
        return attrs
