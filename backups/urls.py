"""backups/urls.py – include in core/urls.py as path('backups/', include('backups.urls'))"""

from django.urls import path
from . import views

app_name = "backups"

urlpatterns = [
    path("create/",                   views.create_backup_view,  name="create"),
    path("list/",                     views.list_backups_view,   name="list"),
    path("<uuid:backup_id>/restore/", views.restore_backup_view, name="restore"),
]
