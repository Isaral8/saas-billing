"""
backups/serializers.py
----------------------
Pure-Python serialisation helpers (no Django REST Framework required).
Each function returns a plain Python dict / list that is safe to store
in a JSONField.
"""

from decimal import Decimal
import datetime


def _clean(value):
    """Convert types that are not JSON-serialisable."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    if hasattr(value, "hex"):          # UUID
        return str(value)
    return value


def serialize_qs(queryset) -> list:
    """
    Serialise a Django queryset to a list of plain dicts.
    Works with any model that has a .values() method.
    """
    rows = []
    for obj in queryset.values():
        rows.append({k: _clean(v) for k, v in obj.items()})
    return rows
