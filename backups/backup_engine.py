"""
backups/backup_engine.py
------------------------
Core logic for creating and restoring backups.

Usage
-----
    from backups.backup_engine import BackupEngine

    # Back up all models for a specific user
    engine = BackupEngine(user=request.user, trigger="manual")
    summary = engine.backup_all()

    # Back up just one model
    engine.backup_model("Invoice")

    # List available backups for a user
    records = BackupEngine.list_backups(user_email="someone@example.com")

    # Restore from a specific BackupRecord id
    BackupEngine.restore(backup_id="<uuid>")
"""

import logging
from django.apps import apps
from django.db import transaction

from .models import BackupRecord
from .serializers import serialize_qs

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Which models to back up, in dependency order
# ---------------------------------------------------------------------------
BACKUP_TARGETS = [
    ("accounts", "CustomUser"),
    ("accounts", "Customer"),
    ("accounts", "Product"),
    ("accounts", "Invoice"),
    ("accounts", "InvoiceItem"),
    ("accounts", "SupportTicket"),
    ("accounts", "Subscription"),
    ("accounts", "ActivityLog"),
    ("accounts", "Notification"),
    ("accounts", "CompanySettings"),
    ("accounts", "GSTSettings"),
    ("accounts", "SMTPSettings"),
    ("accounts", "InvoiceBranding"),
    ("accounts", "UserProfileSettings"),
    ("accounts", "SettingsAuditLog"),
    ("billing",  "Plan"),
    ("billing",  "Subscription"),
    ("billing",  "Invoice"),
    ("billing",  "TicketReply"),
]


class BackupEngine:
    """
    Creates and manages BackupRecord entries for a single user.

    Parameters
    ----------
    user        : CustomUser instance  (required for backup operations)
    trigger     : short label stored on every record  (default "manual")
    notes       : optional notes stored on every record
    """

    def __init__(self, user=None, trigger: str = "manual", notes: str = ""):
        self.user    = user
        self.trigger = trigger
        self.notes   = notes

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def backup_all(self) -> dict:
        """
        Back up every model in BACKUP_TARGETS that belongs to this user.
        Returns a summary dict  {model_name: record_count, ...}.
        """
        summary = {}
        for app_label, model_name in BACKUP_TARGETS:
            try:
                count = self.backup_model(model_name, app_label=app_label)
                summary[model_name] = count
            except Exception as exc:
                logger.warning("Backup skipped for %s.%s: %s", app_label, model_name, exc)
                summary[model_name] = f"ERROR: {exc}"
        return summary

    def backup_model(self, model_name: str, app_label: str = None) -> int:
        """
        Snapshot one model for the current user.
        Returns the number of rows captured.
        """
        model = self._get_model(model_name, app_label)
        qs    = self._filter_for_user(model)
        data  = serialize_qs(qs)

        BackupRecord.objects.create(
            user_email   = self.user.email,
            model_name   = model_name,
            backup_type  = "manual" if self.trigger == "manual" else "auto",
            trigger      = self.trigger,
            record_count = len(data),
            data         = data,
            notes        = self.notes,
        )
        logger.info("Backed up %d rows of %s for %s", len(data), model_name, self.user.email)
        return len(data)

    # ------------------------------------------------------------------
    # Class-level helpers (no user required)
    # ------------------------------------------------------------------

    @classmethod
    def list_backups(cls, user_email: str, model_name: str = None):
        """Return BackupRecord queryset filtered by user (and optionally model)."""
        qs = BackupRecord.objects.filter(user_email=user_email)
        if model_name:
            qs = qs.filter(model_name=model_name)
        return qs.order_by("-created_at")

    @classmethod
    def restore(cls, backup_id: str) -> dict:
        """
        Restore data from a BackupRecord.

        Strategy: INSERT rows that don't exist yet (matched by 'id' field).
        Existing rows are NOT overwritten to avoid data loss.

        Returns  {"inserted": N, "skipped": N, "errors": [...]}
        """
        record = BackupRecord.objects.get(pk=backup_id)
        model  = cls._resolve_model(record.model_name)

        inserted = 0
        skipped  = 0
        errors   = []

        with transaction.atomic():
            for row in record.data:
                pk = row.get("id")
                if pk and model.objects.filter(pk=pk).exists():
                    skipped += 1
                    continue
                try:
                    model.objects.create(**row)
                    inserted += 1
                except Exception as exc:
                    errors.append({"row_id": pk, "error": str(exc)})

        return {"inserted": inserted, "skipped": skipped, "errors": errors}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_model(model_name: str, app_label: str = None):
        if app_label:
            return apps.get_model(app_label, model_name)
        # Search all apps
        for app_cfg in apps.get_app_configs():
            try:
                return app_cfg.get_model(model_name)
            except LookupError:
                continue
        raise LookupError(f"Model '{model_name}' not found in any installed app.")

    @staticmethod
    def _resolve_model(model_name: str):
        """Find a model by name across all installed apps."""
        for app_cfg in apps.get_app_configs():
            try:
                return app_cfg.get_model(model_name)
            except LookupError:
                continue
        raise LookupError(f"Cannot restore: model '{model_name}' not found.")

    def _filter_for_user(self, model):
        """
        Return a queryset scoped to the current user.
        Tries common FK field names: user, owner, created_by.
        Falls back to .all() for models with no user FK (e.g. Plan).
        """
        for field_name in ("user", "owner", "created_by"):
            if hasattr(model, field_name):
                return model.objects.filter(**{field_name: self.user})
        return model.objects.all()
