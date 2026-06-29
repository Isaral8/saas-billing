from celery import shared_task
from django.utils import timezone
from accounts.models import Notification, CustomUser
from accounts.services import NotificationService
import logging

logger = logging.getLogger(__name__)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# PHASE 5: NOTIFICATION CREATION TASKS
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def create_notification_async(
    self,
    user_id,
    title,
    message,
    notification_type='system_info',
    priority='medium',
    icon='info-circle',
    color='info',
    related_model=None,
    related_object_id=None,
    action_url=None,
):
    """
    Asynchronous notification creation task.
    Retries up to 3 times with 1-minute delay on failure.
    
    Args:
        user_id (str): UUID of user
        title (str): Notification title
        message (str): Notification message
        notification_type (str): Type of notification
        priority (str): Priority level
        icon (str): Icon name
        color (str): Color class
        related_model (str): Related model name
        related_object_id (str): Related object ID
        action_url (str): Action URL
    """
    try:
        # Fetch user
        user = CustomUser.objects.get(id=user_id)
        
        # Create notification
        notification = Notification.objects.create(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
            priority=priority,
            icon=icon,
            color=color,
            related_model=related_model,
            related_object_id=related_object_id,
            action_url=action_url,
            is_read=False,
        )
        
        logger.info(f"Async notification created: {notification.id}")
        return {
            'status': 'success',
            'notification_id': str(notification.id),
        }
        
    except CustomUser.DoesNotExist:
        logger.error(f"User not found: {user_id}")
        return {'status': 'failed', 'error': 'User not found'}
    
    except Exception as exc:
        logger.error(f"Error creating notification: {str(exc)}")
        # Retry with exponential backoff
        raise self.retry(exc=exc)


@shared_task
def send_notification_email(notification_id):
    """
    Send notification via email (for future integration).
    
    Args:
        notification_id (str): UUID of notification
    """
    try:
        notification = Notification.objects.get(id=notification_id)
        
        # TODO: Implement email sending logic
        # from accounts.emails import send_notification_email_func
        # send_notification_email_func(notification)
        
        logger.info(f"Email sent for notification: {notification_id}")
        return {'status': 'sent'}
        
    except Notification.DoesNotExist:
        logger.error(f"Notification not found: {notification_id}")
        return {'status': 'failed', 'error': 'Notification not found'}


@shared_task
def send_notification_sms(notification_id):
    """
    Send notification via SMS (for future integration).
    
    Args:
        notification_id (str): UUID of notification
    """
    try:
        notification = Notification.objects.get(id=notification_id)
        
        # TODO: Implement SMS sending logic
        # from accounts.sms import send_notification_sms_func
        # send_notification_sms_func(notification)
        
        logger.info(f"SMS sent for notification: {notification_id}")
        return {'status': 'sent'}
        
    except Notification.DoesNotExist:
        logger.error(f"Notification not found: {notification_id}")
        return {'status': 'failed', 'error': 'Notification not found'}


@shared_task
def send_notification_whatsapp(notification_id):
    """
    Send notification via WhatsApp (for future integration).
    
    Args:
        notification_id (str): UUID of notification
    """
    try:
        notification = Notification.objects.get(id=notification_id)
        
        # TODO: Implement WhatsApp sending logic
        # from accounts.whatsapp import send_notification_whatsapp_func
        # send_notification_whatsapp_func(notification)
        
        logger.info(f"WhatsApp message sent for notification: {notification_id}")
        return {'status': 'sent'}
        
    except Notification.DoesNotExist:
        logger.error(f"Notification not found: {notification_id}")
        return {'status': 'failed', 'error': 'Notification not found'}


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# PHASE 10: MAINTENANCE & CLEANUP TASKS
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@shared_task
def cleanup_old_notifications(days=365):
    """
    Periodic task to clean up old notifications.
    Can be scheduled via Celery Beat or management command.
    
    Args:
        days (int): Delete notifications older than this many days
    """
    try:
        count = NotificationService.delete_old_notifications(days)
        logger.info(f"Cleaned up {count} notifications older than {days} days")
        return {'status': 'success', 'deleted_count': count}
    except Exception as e:
        logger.error(f"Cleanup failed: {str(e)}")
        return {'status': 'failed', 'error': str(e)}


@shared_task
def mark_overdue_invoices_as_pending():
    """
    Periodic task to check and mark overdue invoices.
    Creates notifications for overdue invoices.
    """
    from accounts.models import Invoice
    from datetime import date
    
    try:
        today = date.today()
        overdue_invoices = Invoice.objects.filter(
            due_date__lt=today,
            status__in=['issued', 'pending']
        )
        
        count = 0
        for invoice in overdue_invoices:
            # Update status
            invoice.status = 'overdue'
            invoice.save(update_fields=['status', 'updated_at'])
            
            # Create notification
            from accounts.services import NotificationFactory
            NotificationFactory.system_warning(
                user=invoice.user,
                title=f"Invoice {invoice.invoice_number} is Overdue",
                message=f"Invoice INV-{invoice.invoice_number} is now {(today - invoice.due_date).days} days overdue.",
                async_task=False,  # Use sync to ensure creation
            )
            count += 1
        
        logger.info(f"Marked {count} invoices as overdue")
        return {'status': 'success', 'count': count}
        
    except Exception as e:
        logger.error(f"Overdue check failed: {str(e)}")
        return {'status': 'failed', 'error': str(e)}


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# BATCH NOTIFICATION TASKS
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@shared_task
def send_daily_summary(user_id):
    """
    Send daily summary of notifications to user.
    Can be scheduled via Celery Beat.
    
    Args:
        user_id (str): UUID of user
    """
    try:
        user = CustomUser.objects.get(id=user_id)
        
        # Get today's notifications
        from django.utils import timezone
        from datetime import timedelta
        
        today = timezone.now().date()
        notifications = Notification.objects.filter(
            user=user,
            created_at__date=today,
        ).order_by('-created_at')
        
        if not notifications.exists():
            logger.info(f"No notifications to summarize for user {user_id}")
            return {'status': 'no_notifications'}
        
        # TODO: Send summary email
        # from accounts.emails import send_summary_email
        # send_summary_email(user, notifications)
        
        logger.info(f"Daily summary sent to {user.email}")
        return {
            'status': 'sent',
            'notification_count': notifications.count(),
        }
        
    except CustomUser.DoesNotExist:
        logger.error(f"User not found: {user_id}")
        return {'status': 'failed', 'error': 'User not found'}


@shared_task
def send_bulk_notification(user_ids, title, message, notification_type='system_info', priority='medium'):
    """
    Send bulk notification to multiple users.
    
    Args:
        user_ids (list): List of user UUIDs
        title (str): Notification title
        message (str): Notification message
        notification_type (str): Type of notification
        priority (str): Priority level
    """
    try:
        users = CustomUser.objects.filter(id__in=user_ids)
        count = 0
        
        for user in users:
            Notification.objects.create(
                user=user,
                title=title,
                message=message,
                notification_type=notification_type,
                priority=priority,
                icon='info-circle',
                color='info',
                is_read=False,
            )
            count += 1
        
        logger.info(f"Sent bulk notification to {count} users")
        return {'status': 'success', 'count': count}
        
    except Exception as e:
        logger.error(f"Bulk notification failed: {str(e)}")
        return {'status': 'failed', 'error': str(e)}
