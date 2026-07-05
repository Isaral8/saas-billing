from celery import shared_task
from django.utils import timezone
from accounts.models import Notification, CustomUser
from accounts.services import NotificationService
import logging

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────
# PHASE 5: NOTIFICATION CREATION TASKS
# ────────────────────────────────────────────────────────────

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
    """
    try:
        user = CustomUser.objects.get(id=user_id)
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
        raise self.retry(exc=exc)


@shared_task
def send_notification_email(notification_id):
    """Send notification via email (for future integration)."""
    try:
        notification = Notification.objects.get(id=notification_id)
        logger.info(f"Email sent for notification: {notification_id}")
        return {'status': 'sent'}
    except Notification.DoesNotExist:
        logger.error(f"Notification not found: {notification_id}")
        return {'status': 'failed', 'error': 'Notification not found'}


@shared_task
def send_notification_sms(notification_id):
    """Send notification via SMS (for future integration)."""
    try:
        notification = Notification.objects.get(id=notification_id)
        logger.info(f"SMS sent for notification: {notification_id}")
        return {'status': 'sent'}
    except Notification.DoesNotExist:
        logger.error(f"Notification not found: {notification_id}")
        return {'status': 'failed', 'error': 'Notification not found'}


@shared_task
def send_notification_whatsapp(notification_id):
    """Send notification via WhatsApp (for future integration)."""
    try:
        notification = Notification.objects.get(id=notification_id)
        logger.info(f"WhatsApp message sent for notification: {notification_id}")
        return {'status': 'sent'}
    except Notification.DoesNotExist:
        logger.error(f"Notification not found: {notification_id}")
        return {'status': 'failed', 'error': 'Notification not found'}


# ────────────────────────────────────────────────────────────
# PHASE 10: MAINTENANCE & CLEANUP TASKS
# ────────────────────────────────────────────────────────────

@shared_task
def cleanup_old_notifications(days=365):
    """Periodic task to clean up old notifications."""
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
    from accounts.services import NotificationFactory
    from datetime import date

    try:
        today = date.today()
        overdue_invoices = Invoice.objects.filter(
            due_date__lt=today,
            status__in=['issued', 'sent', 'pending']
        )

        count = 0
        for invoice in overdue_invoices:
            invoice.status = 'overdue'
            invoice.save(update_fields=['status', 'updated_at'])

            NotificationFactory.system_warning(
                user=invoice.user,
                title=f"Invoice {invoice.invoice_number} is Overdue",
                message=f"Invoice INV-{invoice.invoice_number} is now {(today - invoice.due_date).days} days overdue.",
                async_task=False,
            )
            count += 1

        logger.info(f"Marked {count} invoices as overdue")
        return {'status': 'success', 'count': count}
    except Exception as e:
        logger.error(f"Overdue check failed: {str(e)}")
        return {'status': 'failed', 'error': str(e)}


# ────────────────────────────────────────────────────────────
# BATCH NOTIFICATION TASKS
# ────────────────────────────────────────────────────────────

@shared_task
def send_daily_summary(user_id):
    """Send daily summary of notifications to user."""
    try:
        user = CustomUser.objects.get(id=user_id)
        from django.utils import timezone as tz
        today = tz.now().date()
        notifications = Notification.objects.filter(
            user=user,
            created_at__date=today,
        ).order_by('-created_at')

        if not notifications.exists():
            logger.info(f"No notifications to summarize for user {user_id}")
            return {'status': 'no_notifications'}

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
    """Send bulk notification to multiple users."""
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


# ────────────────────────────────────────────────────────────
# FEATURE 1: PAYMENT REMINDER TASKS
# ────────────────────────────────────────────────────────────

@shared_task
def send_payment_reminders():
    """
    Send payment reminders for pending invoices
    Reminders sent on: 7 days, 14 days, 30 days overdue
    """
    from datetime import timedelta
    from accounts.models import Invoice
    from accounts.emails import send_invoice_reminder_email

    today = timezone.now().date()
    sent_count = 0

    try:
        pending_invoices = Invoice.objects.filter(
            status__in=['draft', 'sent', 'pending'],
            created_by__isnull=False
        )

        for invoice in pending_invoices:
            days_since_due = (today - invoice.due_date).days

            if days_since_due < 0:
                continue  # Not yet due

            should_send = False

            if days_since_due >= 30 and not invoice.reminder_30_days_sent:
                should_send = True
                invoice.reminder_30_days_sent = True
            elif days_since_due >= 14 and not invoice.reminder_14_days_sent:
                should_send = True
                invoice.reminder_14_days_sent = True
            elif days_since_due >= 7 and not invoice.reminder_7_days_sent:
                should_send = True
                invoice.reminder_7_days_sent = True

            if should_send:
                if send_invoice_reminder_email(invoice):
                    invoice.reminder_sent_count = (invoice.reminder_sent_count or 0) + 1
                    invoice.last_reminder_sent_at = timezone.now()
                    invoice.save()
                    sent_count += 1
                    logger.info(f"Reminder sent for Invoice {invoice.invoice_number}")

        logger.info(f"Payment reminders task completed. Sent {sent_count} reminders.")
        return {'status': 'success', 'sent': sent_count}
    except Exception as e:
        logger.error(f"Payment reminders task failed: {str(e)}")
        return {'status': 'failed', 'error': str(e)}


# ────────────────────────────────────────────────────────────
# FEATURE 2: RENEWAL TASKS
# ────────────────────────────────────────────────────────────

@shared_task
def process_renewal_invoices():
    """Create invoices for renewals due today."""
    from renewals.models import Renewal
    from renewals.services import RenewalService

    try:
        today = timezone.now().date()

        due_renewals = Renewal.objects.filter(
            status='pending',
            renewal_date__lte=today,
            invoice_created=False,
        )

        created_count = 0
        for renewal in due_renewals:
            if RenewalService.create_renewal_invoice(renewal):
                created_count += 1

        logger.info(f"Created {created_count} renewal invoices")
        return {'status': 'success', 'created': created_count}
    except Exception as e:
        logger.error(f"process_renewal_invoices failed: {str(e)}")
        return {'status': 'failed', 'error': str(e)}


@shared_task
def send_renewal_reminders():
    """Send reminders for upcoming renewals."""
    from renewals.services import RenewalService

    try:
        result = RenewalService.send_renewal_reminders()
        logger.info(f"Renewal reminders task completed: {result}")
        return {'status': 'success', **(result or {})}
    except Exception as e:
        logger.error(f"send_renewal_reminders failed: {str(e)}")
        return {'status': 'failed', 'error': str(e)}