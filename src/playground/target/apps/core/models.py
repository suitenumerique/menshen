"""Target: core models."""

import logging
import uuid

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models

logger = logging.getLogger(__name__)


class UserManager(BaseUserManager):
    """Custom manager for User model with additional methods."""

    def get_user_by_sub_or_email(self, sub, email):
        """Fetch existing user by sub or email."""
        logger.debug("Getting user by sub: %s or email: %s", sub, email)
        try:
            return self.get(sub=sub)
        except self.model.DoesNotExist:
            if not email or not settings.OIDC_FALLBACK_TO_EMAIL_FOR_IDENTIFICATION:
                return None
            try:
                return self.get(email__iexact=email)
            except self.model.DoesNotExist:
                pass
        return None

    def _create_user(self, sub, password=None, **extra_fields):
        """Create user instance."""
        user = PlaygroundUser(sub=sub, email=extra_fields.get("email"))
        user.set_password(password)
        return user

    def create_user(self, sub, password=None, **extra_fields):
        """Create a user."""
        user = self._create_user(sub, password=password, **extra_fields)
        user.save()
        return user

    def create_superuser(self, sub, password=None, **extra_fields):
        """Create a super user."""
        user = self._create_user(sub, password=password, **extra_fields)
        user.is_staff = True
        user.is_superuser = True
        user.save()
        return user


class PlaygroundUser(AbstractBaseUser):
    """User model to work with OIDC only authentication."""

    sub = models.CharField(
        help_text="Required. 255 characters or fewer. ASCII characters only.",
        max_length=255,
        unique=True,
        blank=True,
        null=True,
    )
    email = models.EmailField("Identity email address", blank=True, null=True)
    name = models.CharField(
        help_text="Name of the user.", max_length=255, blank=True, null=True
    )
    is_staff = models.BooleanField(
        default=False,
        help_text="Whether the user can log into this admin site.",
    )
    is_superuser = models.BooleanField(
        default=False,
        help_text="Whether the user is a super user.",
    )

    objects = UserManager()

    USERNAME_FIELD = "sub"
    REQUIRED_FIELDS = []


class Item(models.Model):
    """Target item."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(help_text="Item name")
    type = models.CharField(help_text="File type")
    size = models.IntegerField(help_text="Item size (in bytes)")
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "items"
