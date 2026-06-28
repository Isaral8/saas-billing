"""
Management command: create_backup
----------------------------------
Usage:
    python manage.py create_backup
    python manage.py create_backup --email user@example.com
    python manage.py create_backup --model Invoice
    python manage.py create_backup --all-users
    python manage.py create_backup --trigger scheduled --notes "nightly job"
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from backups.backup_engine import BackupEngine

User = get_user_model()


class Command(BaseCommand):
    help = "Create a database backup of application data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            type=str,
            help="Back up data for a specific user email.",
        )
        parser.add_argument(
            "--model",
            type=str,
            help="Back up only this model (e.g. Invoice, Customer).",
        )
        parser.add_argument(
            "--all-users",
            action="store_true",
            help="Back up all users (for scheduled/admin use).",
        )
        parser.add_argument(
            "--trigger",
            type=str,
            default="manual",
            help='Trigger label stored on each record (default: "manual").',
        )
        parser.add_argument(
            "--notes",
            type=str,
            default="",
            help="Optional notes to attach to this backup.",
        )

    def handle(self, *args, **options):
        trigger = options["trigger"]
        notes   = options["notes"]

        if options["all_users"]:
            users = User.objects.filter(is_active=True)
        elif options["email"]:
            users = User.objects.filter(email=options["email"])
            if not users.exists():
                self.stderr.write(self.style.ERROR(f"No user found: {options['email']}"))
                return
        else:
            self.stderr.write(self.style.ERROR(
                "Provide --email <email> or --all-users"
            ))
            return

        total_users = 0
        for user in users:
            engine = BackupEngine(user=user, trigger=trigger, notes=notes)
            if options["model"]:
                try:
                    count = engine.backup_model(options["model"])
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"[{user.email}] {options['model']}: {count} rows backed up."
                        )
                    )
                except Exception as exc:
                    self.stderr.write(self.style.ERROR(f"[{user.email}] ERROR: {exc}"))
            else:
                summary = engine.backup_all()
                for model_name, count in summary.items():
                    self.stdout.write(
                        self.style.SUCCESS(f"[{user.email}] {model_name}: {count} rows")
                    )
            total_users += 1

        self.stdout.write(
            self.style.SUCCESS(f"\nBackup complete. {total_users} user(s) processed.")
        )
