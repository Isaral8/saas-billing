from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import json
from accounts.models import Notification
from accounts.services import NotificationService


class NotificationListView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = 'accounts/notification_list.html'
    paginate_by = 25
    context_object_name = 'notifications'
    
    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).select_related('user').order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_notifs = self.get_queryset()
        context['total_count'] = user_notifs.count()
        context['unread_count'] = user_notifs.filter(is_read=False).count()
        context['read_count'] = user_notifs.filter(is_read=True).count()
        return context


class NotificationDetailView(LoginRequiredMixin, DetailView):
    model = Notification
    template_name = 'accounts/notification_detail.html'
    context_object_name = 'notification'
    
    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)
    
    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        self.object.mark_as_read()
        return response


@login_required
@require_http_methods(["GET"])
def api_unread_count(request):
    count = NotificationService.get_unread_count(request.user)
    return JsonResponse({'status': 'success', 'unread_count': count})


@login_required
@require_http_methods(["GET"])
def api_recent_notifications(request):
    limit = int(request.GET.get('limit', 10))
    if limit > 50:
        limit = 50
    notifications = NotificationService.get_recent_notifications(request.user, limit=limit)
    data = {
        'status': 'success',
        'notifications': [
            {
                'id': str(notif.id),
                'title': notif.title,
                'message': notif.message,
                'icon': notif.icon,
                'color': notif.color,
                'is_read': notif.is_read,
                'created_at': notif.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'action_url': notif.action_url or '#',
            }
            for notif in notifications
        ]
    }
    return JsonResponse(data)


@login_required
@require_http_methods(["GET"])
def api_notification_dropdown(request):
    notifications = NotificationService.get_recent_notifications(request.user, limit=10)
    unread_count = NotificationService.get_unread_count(request.user)
    data = {
        'status': 'success',
        'unread_count': unread_count,
        'notifications': [
            {
                'id': str(notif.id),
                'title': notif.title,
                'message': notif.message,
                'icon': notif.icon,
                'color': notif.color,
                'is_read': notif.is_read,
                'created_at': notif.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'action_url': notif.action_url or '#',
            }
            for notif in notifications
        ]
    }
    return JsonResponse(data)


@login_required
@require_http_methods(["POST"])
def api_mark_as_read(request):
    try:
        data = json.loads(request.body)
        notification_id = data.get('notification_id')
        notification = get_object_or_404(Notification, id=notification_id, user=request.user)
        notification.mark_as_read()
        return JsonResponse({'status': 'success', 'is_read': notification.is_read})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def api_mark_as_unread(request):
    try:
        data = json.loads(request.body)
        notification_id = data.get('notification_id')
        notification = get_object_or_404(Notification, id=notification_id, user=request.user)
        notification.mark_as_unread()
        return JsonResponse({'status': 'success', 'is_read': notification.is_read})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def api_delete_notification(request):
    try:
        data = json.loads(request.body)
        notification_id = data.get('notification_id')
        notification = get_object_or_404(Notification, id=notification_id, user=request.user)
        notification.delete()
        return JsonResponse({'status': 'success', 'message': 'Notification deleted'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def api_mark_all_as_read(request):
    try:
        count = NotificationService.mark_all_as_read(request.user)
        return JsonResponse({'status': 'success', 'marked_count': count})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
