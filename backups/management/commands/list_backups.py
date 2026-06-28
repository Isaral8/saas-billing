"""
Management command: list_backups
---------------------------------
Usage:
    python manage.py list_backups --email user@example.com
    python manage.py list_backups --email user@example.com --model Invoice
"""

from django.core.management.base import BaseCommand
from backups.backup_engine import BackupEngine


class Command(BaseCommand):
    help = "List backup records stored in the database."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True, help="User email to list backups for.")
        parser.add_argument("--model", help="Filter by model name (optional).")

    def handle(self, *args, **options):
        qs = BackupEngine.list_backups(
            user_email=options["email"],
            model_name=options.get("model"),
        )
        if not qs.exists():
            self.stdout.write("No backups found.")
            return

        self.stdout.write(f"\n{'ID':<38}  {'Model':<22}  {'Type':<10}  {'Rows':>5}  {'Created At'}")
        self.stdout.write("-" * 100)
        for rec in qs:
            self.stdout.write(
                f"{str(rec.id):<38}  {rec.model_name:<22}  {rec.backup_type:<10}  "
                f"{rec.record_count:>5}  {rec.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
            )
        self.stdout.write(f"\nTotal: {qs.count()} backup record(s).\n")
