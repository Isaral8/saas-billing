"""
Management command: restore_backup
------------------------------------
Usage:
    python manage.py restore_backup --id <backup-uuid>
"""

from django.core.management.base import BaseCommand
from backups.backup_engine import BackupEngine


class Command(BaseCommand):
    help = "Restore data from a specific BackupRecord."

    def add_arguments(self, parser):
        parser.add_argument("--id", required=True, help="UUID of the BackupRecord to restore.")

    def handle(self, *args, **options):
        backup_id = options["id"]
        self.stdout.write(f"Restoring from backup {backup_id} ...")
        result = BackupEngine.restore(backup_id=backup_id)
        self.stdout.write(self.style.SUCCESS(
            f"Done. Inserted: {result['inserted']}  Skipped (already exist): {result['skipped']}"
        ))
        if result["errors"]:
            self.stderr.write(f"{len(result['errors'])} error(s):")
            for err in result["errors"]:
                self.stderr.write(f"  row_id={err['row_id']}  error={err['error']}")
