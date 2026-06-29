
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
    
    def ready(self):
        """
        Import signal handlers when app is ready.
        This ensures signals are registered for model events.
        PHASE 9: Register notification signals
        """
        import accounts.signal_handlers
