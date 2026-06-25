from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings


class AccountAdapter(DefaultAccountAdapter):
    """Custom account adapter for email-based authentication"""

    def get_login_redirect_url(self, request):
        return settings.LOGIN_REDIRECT_URL


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """Custom social account adapter for CustomUser model"""

    def pre_social_login(self, request, sociallogin):
        """
        If a user with the same email already exists,
        connect the social account to the existing user
        instead of creating a duplicate.
        """
        if sociallogin.is_existing:
            return

        if not sociallogin.email_addresses:
            return

        email = sociallogin.email_addresses[0].email.lower()

        try:
            from accounts.models import CustomUser
            existing_user = CustomUser.objects.get(email=email)
            sociallogin.connect(request, existing_user)
        except CustomUser.DoesNotExist:
            pass

    def save_user(self, request, sociallogin, form=None):
        """
        Save user data from Google/Microsoft profile
        into our CustomUser model fields.
        """
        user = super().save_user(request, sociallogin, form)

        extra_data = sociallogin.account.extra_data

        if not user.first_name:
            user.first_name = extra_data.get('given_name', '')
        if not user.last_name:
            user.last_name = extra_data.get('family_name', '')

        user.save()
        return user