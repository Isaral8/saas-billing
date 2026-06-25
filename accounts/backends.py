# accounts/backends.py
"""
Custom authentication backend for email-based login
"""

from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model

CustomUser = get_user_model()


class EmailAuthBackend(BaseBackend):
    """
    Authenticate using email instead of username
    """
    
    def authenticate(self, request, email=None, password=None, **kwargs):
        """
        Authenticate user by email and password
        """
        try:
            user = CustomUser.objects.get(email=email)
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
        except CustomUser.DoesNotExist:
            return None
        return None
    
    def get_user(self, user_id):
        """
        Get user by ID for session management
        """
        try:
            return CustomUser.objects.get(pk=user_id)
        except CustomUser.DoesNotExist:
            return None
    
    @staticmethod
    def user_can_authenticate(user):
        """
        Check if user is active and can authenticate
        """
        return user.is_active