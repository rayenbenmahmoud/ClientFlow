from rest_framework import serializers

from apps.core.serializers import OwnerAssignmentMixin, ensure_unique_ci

from .models import Company, Contact, Tag


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "color"]

    def validate_name(self, value):
        value = value.strip()
        ensure_unique_ci(Tag, "name", value, self.instance, "A tag with this name already exists.")
        return value


class CompanySerializer(OwnerAssignmentMixin, serializers.ModelSerializer):
    owner_name = serializers.CharField(source="owner.display_name", read_only=True, allow_null=True)
    contact_count = serializers.IntegerField(read_only=True)
    deal_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Company
        fields = [
            "id",
            "name",
            "industry",
            "website",
            "email",
            "phone",
            "address",
            "city",
            "country",
            "notes",
            "owner",
            "owner_name",
            "contact_count",
            "deal_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]
        extra_kwargs = {"owner": {"required": False, "allow_null": True}}

    def validate_name(self, value):
        value = value.strip()
        ensure_unique_ci(Company, "name", value, self.instance, "A company with this name already exists.")
        return value

    def validate_email(self, value):
        return value.strip().lower()


class ContactSerializer(OwnerAssignmentMixin, serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True, allow_null=True)
    owner_name = serializers.CharField(source="owner.display_name", read_only=True, allow_null=True)
    tags = TagSerializer(many=True, read_only=True)
    tag_ids = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Tag.objects.all(), source="tags", write_only=True, required=False
    )

    class Meta:
        model = Contact
        fields = [
            "id",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "phone",
            "job_title",
            "company",
            "company_name",
            "notes",
            "tags",
            "tag_ids",
            "owner",
            "owner_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]
        extra_kwargs = {
            "owner": {"required": False, "allow_null": True},
            "company": {"required": False, "allow_null": True},
        }

    def validate_email(self, value):
        value = value.strip().lower()
        if value:
            ensure_unique_ci(Contact, "email", value, self.instance, "A contact with this email already exists.")
        return value
