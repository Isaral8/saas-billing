"""
backups/admin.py
----------------
Django admin integration for BackupRecord.
Gives super-admins a full UI to view, filter, and restore backups.
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import BackupRecord


@admin.register(BackupRecord)
class BackupRecordAdmin(admin.ModelAdmin):
    list_display  = (
        "id", "user_email", "model_name", "backup_type",
        "record_count", "trigger", "created_at", "restore_link",
    )
    list_filter   = ("backup_type", "model_name", "trigger")
    search_fields = ("user_email", "model_name", "notes")
    readonly_fields = (
        "id", "user_email", "model_name", "backup_type",
        "trigger", "record_count", "data", "created_at",
    )
    ordering = ("-created_at",)
    date_hierarchy = "created_at"

    def restore_link(self, obj):
        url = f"/admin/backups/backuprecord/{obj.pk}/restore/"
        return format_html('<a href="{}">Restore</a>', url)
    restore_link.short_description = "Restore"

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom = [
            path(
                "<uuid:pk>/restore/",
                self.admin_site.admin_view(self.restore_view),
                name="backup-restore",
            )
        ]
        return custom + urls

    def restore_view(self, request, pk):
        from django.http import HttpResponseRedirect
        from django.contrib import messages
        from backups.backup_engine import BackupEngine

        try:
            result = BackupEngine.restore(backup_id=str(pk))
            messages.success(
                request,
                f"Restore complete: {result['inserted']} inserted, "
                f"{result['skipped']} skipped, {len(result['errors'])} errors."
            )
        except Exception as exc:
            messages.error(request, f"Restore failed: {exc}")

        return HttpResponseRedirect(
            f"/admin/backups/backuprecord/{pk}/change/"
        )
