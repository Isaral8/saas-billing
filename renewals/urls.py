from django.urls import path
from . import views

app_name = 'renewals'

urlpatterns = [
    path('',                              views.renewal_dashboard,           name='dashboard'),
    path('list/',                         views.renewal_list,                name='list'),
    path('<uuid:sub_id>/renew/',          views.renew_view,                  name='renew'),
    path('<uuid:sub_id>/history/',        views.renewal_history,             name='history'),
    path('reports/',                      views.renewal_reports,             name='reports'),
    path('api/preview/',                  views.preview_amount_api,          name='preview_api'),
    path('notify/',                       views.send_expiry_notifications_view, name='notify'),
]