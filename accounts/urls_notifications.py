from django.urls import path
from accounts import views_notifications

app_name = 'notifications'

urlpatterns = [
    path('', views_notifications.NotificationListView.as_view(), name='list'),
    path('<uuid:pk>/', views_notifications.NotificationDetailView.as_view(), name='detail'),
    path('api/notifications/unread-count/', views_notifications.api_unread_count, name='api_unread_count'),
    path('api/notifications/recent/', views_notifications.api_recent_notifications, name='api_recent'),
    path('api/notifications/dropdown/', views_notifications.api_notification_dropdown, name='api_dropdown'),
    path('api/notifications/mark-read/', views_notifications.api_mark_as_read, name='api_mark_read'),
    path('api/notifications/mark-unread/', views_notifications.api_mark_as_unread, name='api_mark_unread'),
    path('api/notifications/delete/', views_notifications.api_delete_notification, name='api_delete'),
    path('api/notifications/mark-all-read/', views_notifications.api_mark_all_as_read, name='api_mark_all_read'),
]
