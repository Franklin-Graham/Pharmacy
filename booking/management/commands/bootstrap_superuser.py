import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError


ENVIRONMENT_VARIABLES = (
    "BOOTSTRAP_SUPERUSER_USERNAME",
    "BOOTSTRAP_SUPERUSER_EMAIL",
    "BOOTSTRAP_SUPERUSER_PASSWORD",
)


class Command(BaseCommand):
    help = "Create the initial admin account from private environment variables."

    def handle(self, *args, **options):
        values = {name: os.environ.get(name, "") for name in ENVIRONMENT_VARIABLES}
        if not any(values.values()):
            self.stdout.write("No bootstrap credentials configured; skipped.")
            return
        if not all(values.values()):
            raise CommandError(
                "Set all BOOTSTRAP_SUPERUSER_* environment variables together."
            )

        User = get_user_model()
        username_field = User.USERNAME_FIELD
        email_field = getattr(User, "EMAIL_FIELD", "email")
        username = values["BOOTSTRAP_SUPERUSER_USERNAME"]
        email = values["BOOTSTRAP_SUPERUSER_EMAIL"]
        password = values["BOOTSTRAP_SUPERUSER_PASSWORD"]
        existing = User._default_manager.filter(
            **{username_field: username}
        ).first()

        if existing:
            if existing.is_superuser:
                self.stdout.write("Bootstrap superuser already exists; no changes made.")
                return
            raise CommandError(
                "The bootstrap username is already used by a non-admin account. "
                "Choose a different username."
            )

        user = User(**{username_field: username, email_field: email})
        try:
            validate_password(password, user=user)
        except ValidationError as error:
            raise CommandError("; ".join(error.messages)) from error

        User._default_manager.create_superuser(
            **{
                username_field: username,
                email_field: email,
                "password": password,
            }
        )
        self.stdout.write("Bootstrap superuser created.")
