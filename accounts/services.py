from django.db.models import Q
from accounts.models import Notification, CustomUser
from django.urls import reverse
import logging

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Centralized notification creation and management service.
    Supports Celery async with graceful fallback to sync execution.
    """
    
    @staticmethod
    def create_notification(
        user,
        title,
        message,
        notification_type='system_info',
        priority='medium',
        icon='info-circle',
        color='info',
        related_model=None,
        related_object_id=None,
        action_url=None,
        async_task=True
    ):
        """
        Create a notification for a user.
        
        Args:
            user: CustomUser instance
            title (str): Notification title (max 200 chars)
            message (str): Notification message/description
            notification_type (str): Type from Notification.TYPE_CHOICES
            priority (str): Priority level (low, medium, high, critical)
            icon (str): Bootstrap icon name (e.g., "bell", "check-circle")
            color (str): Bootstrap color class (success, danger, warning, info, primary)
            related_model (str): Related model name (e.g., "Invoice", "Customer")
            related_object_id (str): UUID/ID of related object
            action_url (str): URL to navigate to when clicked
            async_task (bool): Use Celery if available, else sync
        
        Returns:
            Notification instance or None if creation failed
        """
        
        # Validate inputs
        if not isinstance(user, CustomUser):
            logger.warning(f"Invalid user type: {type(user)}")
            return None
        
        if not title or not message:
            logger.warning("Title and message are required")
            return None
        
        # Try async with Celery first
        if async_task:
            try:
                from accounts.tasks import create_notification_async
                task = create_notification_async.delay(
                    user_id=str(user.id),
                    title=title,
                    message=message,
                    notification_type=notification_type,
                    priority=priority,
                    icon=icon,
                    color=color,
                    related_model=related_model,
                    related_object_id=related_object_id,
                    action_url=action_url,
                )
                logger.info(f"Async notification created (task_id: {task.id})")
                return task
            except ImportError:
                logger.debug("Celery not available, falling back to sync")
                async_task = False
            except Exception as e:
                logger.warning(f"Celery error: {str(e)}, falling back to sync")
                async_task = False
        
        # Fallback to synchronous creation
        try:
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
            logger.info(f"Notification created (id: {notification.id})")
            return notification
        except Exception as e:
            logger.error(f"Failed to create notification: {str(e)}")
            return None
    
    @staticmethod
    def get_unread_count(user):
        """
        Get count of unread notifications for a user.
        
        Args:
            user: CustomUser instance
        
        Returns:
            int: Count of unread notifications
        """
        return Notification.objects.filter(user=user, is_read=False).count()
    
    @staticmethod
    def get_unread_notifications(user, limit=10):
        """
        Get unread notifications for a user.
        
        Args:
            user: CustomUser instance
            limit (int): Maximum number of notifications to return
        
        Returns:
            QuerySet: Unread notifications ordered by recency
        """
        return Notification.objects.filter(
            user=user,
            is_read=False
        ).select_related('user').order_by('-created_at')[:limit]
    
    @staticmethod
    def get_recent_notifications(user, limit=10):
        """
        Get recent notifications for a user (read and unread).
        
        Args:
            user: CustomUser instance
            limit (int): Maximum number of notifications to return
        
        Returns:
            QuerySet: Recent notifications ordered by recency
        """
        return Notification.objects.filter(
            user=user
        ).select_related('user').order_by('-created_at')[:limit]
    
    @staticmethod
    def mark_as_read(notification):
        """
        Mark a single notification as read.
        
        Args:
            notification: Notification instance
        
        Returns:
            bool: True if marked, False if already read
        """
        return notification.mark_as_read()
    
    @staticmethod
    def mark_all_as_read(user):
        """
        Mark all unread notifications as read for a user.
        
        Args:
            user: CustomUser instance
        
        Returns:
            int: Count of notifications marked as read
        """
        count, _ = Notification.objects.filter(
            user=user,
            is_read=False
        ).update(is_read=True)
        return count
    
    @staticmethod
    def delete_notification(notification):
        """
        Delete a notification.
        
        Args:
            notification: Notification instance
        
        Returns:
            bool: True if deleted
        """
        try:
            notification.delete()
            return True
        except Exception as e:
            logger.error(f"Failed to delete notification: {str(e)}")
            return False
    
    @staticmethod
    def delete_old_notifications(days=365):
        """
        Delete notifications older than specified days.
        Useful for cleanup management command.
        
        Args:
            days (int): Delete notifications older than this many days
        
        Returns:
            int: Count of deleted notifications
        """
        from datetime import timedelta
        from django.utils import timezone
        
        cutoff_date = timezone.now() - timedelta(days=days)
        count, _ = Notification.objects.filter(
            created_at__lt=cutoff_date
        ).delete()
        return count
    
    @staticmethod
    def search_notifications(user, query, notification_type=None, priority=None, is_read=None):
        """
        Search notifications with filters.
        
        Args:
            user: CustomUser instance
            query (str): Search in title and message
            notification_type (str): Filter by type
            priority (str): Filter by priority
            is_read (bool): Filter by read status
        
        Returns:
            QuerySet: Filtered notifications
        """
        qs = Notification.objects.filter(user=user)
        
        # Text search
        if query:
            qs = qs.filter(
                Q(title__icontains=query) |
                Q(message__icontains=query)
            )
        
        # Type filter
        if notification_type:
            qs = qs.filter(notification_type=notification_type)
        
        # Priority filter
        if priority:
            qs = qs.filter(priority=priority)
        
        # Read status filter
        if is_read is not None:
            qs = qs.filter(is_read=is_read)
        
        return qs.order_by('-created_at')


# ─────────────────────────────────────────────────────────────────────
# NOTIFICATION FACTORY METHODS
# ─────────────────────────────────────────────────────────────────────

class NotificationFactory:
    """
    Factory for creating specific types of notifications with preset values.
    Reduces code duplication across the project.
    """
    
    @staticmethod
    def invoice_created(user, invoice, async_task=True):
        """Invoice created notification."""
        return NotificationService.create_notification(
            user=user,
            title=f"Invoice {invoice.invoice_number} Created",
            message=f"Invoice INV-{invoice.invoice_number} has been created successfully.",
            notification_type='invoice_created',
            priority='medium',
            icon='file-earmark-plus',
            color='info',
            related_model='Invoice',
            related_object_id=str(invoice.id),
            action_url=reverse('accounts:invoice_detail', args=[invoice.id]),
            async_task=async_task,
        )
    
    @staticmethod
    def invoice_paid(user, invoice, async_task=True):
        """Invoice paid notification."""
        return NotificationService.create_notification(
            user=user,
            title=f"Invoice {invoice.invoice_number} Paid",
            message=f"Payment received for invoice INV-{invoice.invoice_number}. Amount: ₹{invoice.total:,.2f}",
            notification_type='invoice_paid',
            priority='high',
            icon='check-circle',
            color='success',
            related_model='Invoice',
            related_object_id=str(invoice.id),
            action_url=reverse('accounts:invoice_detail', args=[invoice.id]),
            async_task=async_task,
        )
    
    @staticmethod
    def invoice_updated(user, invoice, async_task=True):
        """Invoice updated notification."""
        return NotificationService.create_notification(
            user=user,
            title=f"Invoice {invoice.invoice_number} Updated",
            message=f"Invoice INV-{invoice.invoice_number} has been updated.",
            notification_type='invoice_updated',
            priority='medium',
            icon='file-earmark-check',
            color='info',
            related_model='Invoice',
            related_object_id=str(invoice.id),
            action_url=reverse('accounts:invoice_detail', args=[invoice.id]),
            async_task=async_task,
        )
    
    @staticmethod
    def invoice_deleted(user, invoice_number, async_task=True):
        """Invoice deleted notification."""
        return NotificationService.create_notification(
            user=user,
            title=f"Invoice {invoice_number} Deleted",
            message=f"Invoice INV-{invoice_number} has been permanently deleted.",
            notification_type='invoice_deleted',
            priority='medium',
            icon='file-earmark-x',
            color='danger',
            async_task=async_task,
        )
    
    @staticmethod
    def customer_added(user, customer, async_task=True):
        """Customer added notification."""
        return NotificationService.create_notification(
            user=user,
            title=f"Customer {customer.name} Added",
            message=f"New customer '{customer.name}' has been added to your account.",
            notification_type='customer_added',
            priority='medium',
            icon='person-plus',
            color='primary',
            related_model='Customer',
            related_object_id=str(customer.id),
            async_task=async_task,
        )
    
    @staticmethod
    def customer_updated(user, customer, async_task=True):
        """Customer updated notification."""
        return NotificationService.create_notification(
            user=user,
            title=f"Customer {customer.name} Updated",
            message=f"Customer '{customer.name}' profile has been updated.",
            notification_type='customer_updated',
            priority='low',
            icon='person-check',
            color='info',
            related_model='Customer',
            related_object_id=str(customer.id),
            async_task=async_task,
        )
    
    @staticmethod
    def product_added(user, product, async_task=True):
        """Product added notification."""
        return NotificationService.create_notification(
            user=user,
            title=f"Product {product.name} Added",
            message=f"New product '{product.name}' has been added to your catalog.",
            notification_type='product_added',
            priority='medium',
            icon='box-seam',
            color='primary',
            related_model='Product',
            related_object_id=str(product.id),
            async_task=async_task,
        )
    
    @staticmethod
    def product_updated(user, product, async_task=True):
        """Product updated notification."""
        return NotificationService.create_notification(
            user=user,
            title=f"Product {product.name} Updated",
            message=f"Product '{product.name}' has been updated.",
            notification_type='product_updated',
            priority='low',
            icon='box-seam',
            color='info',
            related_model='Product',
            related_object_id=str(product.id),
            async_task=async_task,
        )
    
    @staticmethod
    def low_stock_alert(user, product, async_task=True):
        """Low stock alert notification."""
        return NotificationService.create_notification(
            user=user,
            title=f"Low Stock Alert: {product.name}",
            message=f"Product '{product.name}' stock ({product.current_stock}) is below minimum ({product.min_stock}).",
            notification_type='low_stock',
            priority='high',
            icon='exclamation-triangle',
            color='warning',
            related_model='Product',
            related_object_id=str(product.id),
            async_task=async_task,
        )
    
    @staticmethod
    def out_of_stock_alert(user, product, async_task=True):
        """Out of stock alert notification."""
        return NotificationService.create_notification(
            user=user,
            title=f"Out of Stock: {product.name}",
            message=f"Product '{product.name}' is out of stock!",
            notification_type='out_of_stock',
            priority='critical',
            icon='exclamation-circle',
            color='danger',
            related_model='Product',
            related_object_id=str(product.id),
            async_task=async_task,
        )
    
    @staticmethod
    def backup_created(user, backup_name, async_task=True):
        """Backup created notification."""
        return NotificationService.create_notification(
            user=user,
            title=f"Backup Created: {backup_name}",
            message=f"Database backup '{backup_name}' has been created successfully.",
            notification_type='backup_created',
            priority='medium',
            icon='cloud-check',
            color='success',
            async_task=async_task,
        )
    
    @staticmethod
    def backup_failed(user, backup_name, error_msg, async_task=True):
        """Backup failed notification."""
        return NotificationService.create_notification(
            user=user,
            title=f"Backup Failed: {backup_name}",
            message=f"Database backup failed. Error: {error_msg}",
            notification_type='backup_failed',
            priority='critical',
            icon='cloud-x',
            color='danger',
            async_task=async_task,
        )
    
    @staticmethod
    def system_success(user, title, message, async_task=True):
        """Generic success notification."""
        return NotificationService.create_notification(
            user=user,
            title=title,
            message=message,
            notification_type='system_success',
            priority='low',
            icon='check-circle',
            color='success',
            async_task=async_task,
        )
    
    @staticmethod
    def system_warning(user, title, message, async_task=True):
        """Generic warning notification."""
        return NotificationService.create_notification(
            user=user,
            title=title,
            message=message,
            notification_type='system_warning',
            priority='high',
            icon='exclamation-triangle',
            color='warning',
            async_task=async_task,
        )
    
    @staticmethod
    def system_error(user, title, message, async_task=True):
        """Generic error notification."""
        return NotificationService.create_notification(
            user=user,
            title=title,
            message=message,
            notification_type='system_error',
            priority='critical',
            icon='x-circle',
            color='danger',
            async_task=async_task,
        )
