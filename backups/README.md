# Database Backup System — `backups` app

Stores snapshots of your SaaS billing data inside the **same PostgreSQL
database** you already use.  No S3, no external file storage, no Excel.

---

## Quick start

### 1. Add to INSTALLED_APPS (core/settings.py)

```python
INSTALLED_APPS = [
    ...
    "backups",   # ← add this
]
```

### 2. Add URLs (core/urls.py)

```python
from django.urls import path, include

urlpatterns = [
    ...
    path("backups/", include("backups.urls")),
]
```

### 3. Run the migration

```bash
python manage.py migrate backups
```

---

## Using from the command line

```bash
# Back up all models for one user
python manage.py create_backup --email user@example.com

# Back up a single model
python manage.py create_backup --email user@example.com --model Invoice

# Scheduled / nightly backup for all active users
python manage.py create_backup --all-users --trigger scheduled --notes "nightly"

# List backups for a user
python manage.py list_backups --email user@example.com
python manage.py list_backups --email user@example.com --model Customer

# Restore from a specific backup
python manage.py restore_backup --id <uuid-from-list-output>
```

---

## REST API endpoints

| Method | URL | Description |
|--------|-----|-------------|
| POST | `/backups/create/` | Create backup for logged-in user |
| GET  | `/backups/list/`   | List backups (add `?model=Invoice` to filter) |
| POST | `/backups/<uuid>/restore/` | Restore a specific backup |

### Example — create backup from JS/frontend

```js
await fetch("/backups/create/", {
  method: "POST",
  headers: { "Content-Type": "application/json", "X-CSRFToken": getCookie("csrftoken") },
  body: JSON.stringify({ model: "Invoice", notes: "before bulk import" })
});
```

---

## Models backed up (in order)

- CustomUser, Customer, Product
- Invoice, InvoiceItem
- SupportTicket, Subscription
- ActivityLog, Notification
- CompanySettings, GSTSettings, SMTPSettings
- InvoiceBranding, UserProfileSettings, SettingsAuditLog
- billing.Plan, billing.Subscription, billing.Invoice, billing.TicketReply

---

## Django Admin

Go to **Admin → Backups → Backup Records** to:
- Browse all snapshots with filters (date, model, type)
- Click **Restore** on any row to re-insert missing rows

---

## Automate with Celery

Add this to your `automation` app or a `tasks.py`:

```python
from celery import shared_task
from django.contrib.auth import get_user_model
from backups.backup_engine import BackupEngine

@shared_task
def nightly_backup():
    User = get_user_model()
    for user in User.objects.filter(is_active=True):
        BackupEngine(user=user, trigger="scheduled", notes="nightly").backup_all()
```

Then schedule it in `core/celery.py`:

```python
app.conf.beat_schedule = {
    "nightly-backup": {
        "task": "automation.tasks.nightly_backup",
        "schedule": crontab(hour=2, minute=0),   # 2 AM every day
    },
}
```
