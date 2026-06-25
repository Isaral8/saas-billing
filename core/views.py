from django.views.generic import TemplateView

class LandingPageView(TemplateView):
    """Landing page view for iSaral SaaS."""
    template_name = 'home.html'
