from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.common.models.base import UUIDModel


class UserRole(models.TextChoices):
    ADMIN = "ADMIN", "Admin"
    SALES_AGENT = "SALES_AGENT", "Sales Agent"
    B2B_PARTNER = "B2B_PARTNER", "B2B Partner"
    CUSTOMER = "CUSTOMER", "Customer"


class UserManager(BaseUserManager):
    """
    Custom manager for User model where email is the unique identifier
    for authentication instead of usernames.
    """

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        extra_fields.setdefault("role", UserRole.CUSTOMER)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", UserRole.ADMIN)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser, UUIDModel):
    """
    Custom user model where email is the unique identifier.
    Inherits UUIDv4 primary key from UUIDModel.
    """

    username = None  # Removes AbstractUser.username field entirely
    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=50, blank=True)
    whatsapp_number = models.CharField(max_length=50, blank=True)
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.CUSTOMER,
        db_index=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []  # Removes 'username' from createsuperuser prompt

    objects = UserManager()

    class Meta:
        db_table = "users"
        indexes = [
            models.Index(fields=["email"], name="users_email_idx"),
            models.Index(fields=["role", "is_active"], name="users_role_active_idx"),
        ]

    @property
    def full_name(self) -> str:
        name = f"{self.first_name} {self.last_name}".strip()
        return name if name else self.email

    def __str__(self) -> str:
        return f"{self.email} ({self.role})"
