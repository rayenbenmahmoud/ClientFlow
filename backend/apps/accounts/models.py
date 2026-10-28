from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.db.models.functions import Lower


class Role(models.TextChoices):
    ADMIN = "admin", "Admin"
    MANAGER = "manager", "Manager"
    SALES_REP = "sales_rep", "Sales rep"


class CrmUserManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", Role.ADMIN)
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    Role = Role

    email = models.EmailField("email address", max_length=254)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.SALES_REP)

    objects = CrmUserManager()

    class Meta:
        ordering = ["first_name", "last_name", "username"]
        constraints = [models.UniqueConstraint(Lower("email"), name="uniq_user_email_ci")]

    @property
    def display_name(self) -> str:
        return self.get_full_name() or self.username
