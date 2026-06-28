"""
backups/views.py
----------------
Simple view endpoints for backup management.
Wire these into your accounts/urls.py or a dedicated backups/urls.py.
"""

import json
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST, require_GET

from .backup_engine import BackupEngine
from .models import BackupRecord


@login_required
@require_POST
def create_backup_view(request):
    """
    POST /backups/create/
    Body (optional JSON): {"model": "Invoice", "notes": "before import"}
    Creates a backup for the logged-in user and returns a summary.
    """
    body  = {}
    if request.body:
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            pass

    model_name = body.get("model")
    notes      = body.get("notes", "")
    engine     = BackupEngine(user=request.user, trigger="manual", notes=notes)

    if model_name:
        count   = engine.backup_model(model_name)
        summary = {model_name: count}
    else:
        summary = engine.backup_all()

    return JsonResponse({"status": "ok", "summary": summary})


@login_required
@require_GET
def list_backups_view(request):
    """
    GET /backups/list/?model=Invoice
    Lists all backups for the logged-in user (optionally filtered by model).
    """
    model_name = request.GET.get("model")
    qs = BackupEngine.list_backups(
        user_email=request.user.email,
        model_name=model_name,
    )
    records = [
        {
            "id":           str(r.id),
            "model_name":   r.model_name,
            "backup_type":  r.backup_type,
            "trigger":      r.trigger,
            "record_count": r.record_count,
            "created_at":   r.created_at.isoformat(),
            "notes":        r.notes,
        }
        for r in qs
    ]
    return JsonResponse({"backups": records, "total": len(records)})


@login_required
@require_POST
def restore_backup_view(request, backup_id):
    """
    POST /backups/<uuid>/restore/
    Restores data from the given BackupRecord.
    Only allowed if the backup belongs to the logged-in user.
    """
    try:
        record = BackupRecord.objects.get(pk=backup_id, user_email=request.user.email)
    except BackupRecord.DoesNotExist:
        return HttpResponseBadRequest("Backup not found or access denied.")

    result = BackupEngine.restore(backup_id=str(record.pk))
    return JsonResponse({"status": "ok", "result": result})
