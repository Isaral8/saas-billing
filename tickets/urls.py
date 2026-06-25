from django.urls import path
from . import views

app_name = 'tickets'

urlpatterns = [
    path('', views.tickets_view, name='list'),
    path('create/', views.create_ticket_view, name='create'),
    path('<uuid:ticket_id>/', views.ticket_detail_view, name='detail'),
    path('<uuid:ticket_id>/update/', views.update_ticket_status_view, name='update'),
]