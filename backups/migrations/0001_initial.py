"""Initial migration for the backups app."""

import uuid
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="BackupRecord",
            fields=[
                ("id",           models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("user_email",   models.EmailField(db_index=True, max_length=254)),
                ("model_name",   models.CharField(db_index=True, max_length=100)),
                ("backup_type",  models.CharField(
                    choices=[("manual", "Manual"), ("auto", "Automatic"), ("pre_delete", "Pre-Delete Safety")],
                    default="manual", max_length=20,
                )),
                ("trigger",      models.CharField(default="manual", max_length=50)),
                ("record_count", models.PositiveIntegerField(default=0)),
                ("data",         models.JSONField(default=list)),
                ("created_at",   models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ("notes",        models.TextField(blank=True)),
            ],
            options={
                "verbose_name":        "Backup Record",
                "verbose_name_plural": "Backup Records",
                "ordering":            ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="backuprecord",
            index=models.Index(
                fields=["user_email", "model_name", "-created_at"],
                name="backups_user_model_date_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="backuprecord",
            index=models.Index(
                fields=["backup_type", "-created_at"],
                name="backups_type_date_idx",
            ),
        ),
    ]
