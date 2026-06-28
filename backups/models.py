"""
backups/models.py
-----------------
Database-backed backup system for the SaaS Billing application.

Each BackupRecord stores a full JSON snapshot of a model's data at a
point in time.  Records are stored in the same PostgreSQL database,
giving you a queryable, restorable audit trail without any external
file storage.
"""

import uuid
from django.db import models
from django.utils import timezone


class BackupRecord(models.Model):
    """
    One snapshot of one model's data for one user at one point in time.

    Fields
    ------
    id              Auto UUID primary key.
    user_email      Email of the owner – stored as plain text so the record
                    survives even if the user row is later deleted.
    model_name      e.g. "Customer", "Invoice", "Product"
    backup_type     "manual" (triggered by user/admin) or "auto" (scheduled).
    trigger         Short label: "manual", "scheduled", "pre_delete", etc.
    record_count    How many rows were captured in this snapshot.
    data            The full JSON snapshot (list of serialised objects).
    created_at      When the backup was taken.
    notes           Optional human-readable comment.
    """

    BACKUP_TYPE_CHOICES = [
        ("manual",    "Manual"),
        ("auto",      "Automatic"),
        ("pre_delete","Pre-Delete Safety"),
    ]

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_email   = models.EmailField(db_index=True)
    model_name   = models.CharField(max_length=100, db_index=True)
    backup_type  = models.CharField(max_length=20, choices=BACKUP_TYPE_CHOICES, default="manual")
    trigger      = models.CharField(max_length=50, default="manual")
    record_count = models.PositiveIntegerField(default=0)
    data         = models.JSONField(default=list)
    created_at   = models.DateTimeField(default=timezone.now, db_index=True)
    notes        = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user_email", "model_name", "-created_at"]),
            models.Index(fields=["backup_type", "-created_at"]),
        ]
        verbose_name        = "Backup Record"
        verbose_name_plural = "Backup Records"

    def __str__(self):
        return (
            f"[{self.backup_type.upper()}] {self.model_name} – "
            f"{self.user_email} – {self.record_count} rows – "
            f"{self.created_at.strftime('%Y-%m-%d %H:%M')}"
        )

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    @classmethod
    def latest_for(cls, user_email: str, model_name: str):
        """Return the most recent backup record for a user+model pair."""
        return (
            cls.objects
               .filter(user_email=user_email, model_name=model_name)
               .first()
        )

    @classmethod
    def count_for(cls, user_email: str) -> dict:
        """Return a dict of {model_name: backup_count} for a user."""
        from django.db.models import Count
        qs = (
            cls.objects
               .filter(user_email=user_email)
               .values("model_name")
               .annotate(total=Count("id"))
               .order_by("model_name")
        )
        return {row["model_name"]: row["total"] for row in qs}
