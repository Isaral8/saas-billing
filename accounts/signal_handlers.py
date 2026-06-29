# accounts/signal_handlers.py - NOTIFICATION SIGNALS

"""
Django signals to automatically create notifications when models change.
PHASE 9: Auto-notification on Invoice, Customer, Product events.

IMPORTANT: This file must be imported in accounts/apps.py ready() method
to ensure signals are registered.
"""

from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone
from accounts.models import Invoice, Customer, Product, Notification
from accounts.services import NotificationFactory
import logging

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# HELPER: PREVENT DUPLICATE NOTIFICATIONS
# ─────────────────────────────────────────────────────────────────────

def has_recent_similar_notification(user, notification_type, related_object_id, minutes=5):
    """
    Check if a similar notification was created recently.
    Prevents duplicate notifications within specified time window.
    
    Args:
        user: CustomUser instance
        notification_type: Type of notification
        related_object_id: Related object ID
        minutes: Time window to check (default 5 minutes)
    
    Returns:
        bool: True if similar notification exists in time window
    """
    from datetime import timedelta
    
    cutoff_time = timezone.now() - timedelta(minutes=minutes)
    
    exists = Notification.objects.filter(
        user=user,
        notification_type=notification_type,
        related_object_id=related_object_id,
        created_at__gte=cutoff_time,
    ).exists()
    
    return exists


# ─────────────────────────────────────────────────────────────────────
# INVOICE SIGNALS - CORRECTED VERSION
# ─────────────────────────────────────────────────────────────────────

@receiver(pre_save, sender=Invoice)
def invoice_pre_save(sender, instance, **kwargs):
    """
    Store old status BEFORE the database is updated.
    This allows us to compare old vs new status in post_save.
    
    CRITICAL: post_save fires AFTER database update, so we must capture
    the old value here in pre_save.
    """
    try:
        # Fetch the current (old) version from database
        old_instance = Invoice.objects.get(pk=instance.pk)
        # Store it temporarily on the instance
        instance._old_status = old_instance.status
        logger.debug(f"Pre-save: Stored old status '{instance._old_status}' for invoice {instance.invoice_number}")
    except Invoice.DoesNotExist:
        # New invoice - no old status to store
        instance._old_status = None
        logger.debug(f"Pre-save: New invoice {instance.invoice_number} (no old status)")


@receiver(post_save, sender=Invoice)
def invoice_post_save(sender, instance, created, **kwargs):
    """
    Signal triggered when Invoice is created or updated.
    Creates appropriate notification.
    
    USES: instance._old_status (set in pre_save) to compare old vs new.
    """
    try:
        user = instance.user
        
        if created:
            # ─── NEW INVOICE CREATED ───
            if not has_recent_similar_notification(user, 'invoice_created', str(instance.id)):
                NotificationFactory.invoice_created(
                    user=user,
                    invoice=instance,
                    async_task=True,
                )
                logger.info(f"✅ Notification created for new invoice: {instance.invoice_number}")
        
        else:
            # ─── INVOICE UPDATED ───
            old_status = getattr(instance, '_old_status', None)
            new_status = instance.status
            
            logger.debug(f"Post-save: Invoice {instance.invoice_number} status changed from '{old_status}' to '{new_status}'")
            
            # Check if status changed to 'paid'
            if old_status != 'paid' and new_status == 'paid':
                if not has_recent_similar_notification(user, 'invoice_paid', str(instance.id)):
                    NotificationFactory.invoice_paid(
                        user=user,
                        invoice=instance,
                        async_task=True,
                    )
                    logger.info(f"✅ Invoice paid notification: {instance.invoice_number}")
            
            # Check if status changed to something else (not paid)
            elif old_status != new_status and new_status != 'paid':
                if not has_recent_similar_notification(user, 'invoice_updated', str(instance.id)):
                    NotificationFactory.invoice_updated(
                        user=user,
                        invoice=instance,
                        async_task=True,
                    )
                    logger.info(f"✅ Invoice updated notification: {instance.invoice_number}")
    
    except Exception as e:
        logger.error(f"❌ Error in invoice_post_save signal: {str(e)}", exc_info=True)


@receiver(post_delete, sender=Invoice)
def invoice_post_delete(sender, instance, **kwargs):
    """
    Signal triggered when Invoice is deleted.
    Creates deleted notification.
    """
    try:
        user = instance.user
        invoice_number = instance.invoice_number
        
        NotificationFactory.invoice_deleted(
            user=user,
            invoice_number=invoice_number,
            async_task=True,
        )
        logger.info(f"✅ Invoice deleted notification: {invoice_number}")
    
    except Exception as e:
        logger.error(f"❌ Error in invoice_post_delete signal: {str(e)}", exc_info=True)


# ─────────────────────────────────────────────────────────────────────
# CUSTOMER SIGNALS - IMPROVED VERSION
# ─────────────────────────────────────────────────────────────────────

@receiver(pre_save, sender=Customer)
def customer_pre_save(sender, instance, **kwargs):
    """
    Store old customer data BEFORE the database is updated.
    """
    try:
        old_instance = Customer.objects.get(pk=instance.pk)
        instance._old_name = old_instance.name
        instance._old_email = old_instance.email
        instance._old_company = old_instance.company
        logger.debug(f"Pre-save: Stored old customer data for {old_instance.name}")
    except Customer.DoesNotExist:
        # New customer
        instance._old_name = None
        instance._old_email = None
        instance._old_company = None
        logger.debug(f"Pre-save: New customer")


@receiver(post_save, sender=Customer)
def customer_post_save(sender, instance, created, **kwargs):
    """
    Signal triggered when Customer is created or updated.
    Creates appropriate notification.
    """
    try:
        user = instance.user
        
        # ─── NEW CUSTOMER CREATED ───
        if created and user.notif_new_customer:
            if not has_recent_similar_notification(user, 'customer_added', str(instance.id)):
                NotificationFactory.customer_added(
                    user=user,
                    customer=instance,
                    async_task=True,
                )
                logger.info(f"✅ Customer added notification: {instance.name}")
        
        # ─── CUSTOMER UPDATED ───
        elif not created:
            old_name = getattr(instance, '_old_name', None)
            old_email = getattr(instance, '_old_email', None)
            old_company = getattr(instance, '_old_company', None)
            
            # Only notify on significant changes (name, email, company)
            if (old_name != instance.name or
                old_email != instance.email or
                old_company != instance.company):
                
                if not has_recent_similar_notification(user, 'customer_updated', str(instance.id)):
                    NotificationFactory.customer_updated(
                        user=user,
                        customer=instance,
                        async_task=True,
                    )
                    logger.info(f"✅ Customer updated notification: {instance.name}")
    
    except Exception as e:
        logger.error(f"❌ Error in customer_post_save signal: {str(e)}", exc_info=True)


@receiver(post_delete, sender=Customer)
def customer_post_delete(sender, instance, **kwargs):
    """
    Signal triggered when Customer is deleted.
    Creates deleted notification.
    """
    try:
        user = instance.user
        customer_name = instance.name
        
        from accounts.services import NotificationService
        
        NotificationService.create_notification(
            user=user,
            title=f"Customer {customer_name} Deleted",
            message=f"Customer '{customer_name}' has been removed from your account.",
            notification_type='customer_deleted',
            priority='medium',
            icon='person-x',
            color='danger',
            async_task=True,
        )
        logger.info(f"✅ Customer deleted notification: {customer_name}")
    
    except Exception as e:
        logger.error(f"❌ Error in customer_post_delete signal: {str(e)}", exc_info=True)


# ─────────────────────────────────────────────────────────────────────
# PRODUCT SIGNALS - IMPROVED VERSION
# ─────────────────────────────────────────────────────────────────────

@receiver(pre_save, sender=Product)
def product_pre_save(sender, instance, **kwargs):
    """
    Store old product data BEFORE the database is updated.
    """
    try:
        old_instance = Product.objects.get(pk=instance.pk)
        instance._old_name = old_instance.name
        instance._old_price = old_instance.price
        instance._old_current_stock = old_instance.current_stock
        logger.debug(f"Pre-save: Stored old product data for {old_instance.name}")
    except Product.DoesNotExist:
        # New product
        instance._old_name = None
        instance._old_price = None
        instance._old_current_stock = None
        logger.debug(f"Pre-save: New product")


@receiver(post_save, sender=Product)
def product_post_save(sender, instance, created, **kwargs):
    """
    Signal triggered when Product is created or updated.
    Checks for stock levels and creates notifications.
    """
    try:
        user = instance.user
        
        # ─── NEW PRODUCT CREATED ───
        if created:
            if not has_recent_similar_notification(user, 'product_added', str(instance.id)):
                NotificationFactory.product_added(
                    user=user,
                    product=instance,
                    async_task=True,
                )
                logger.info(f"✅ Product added notification: {instance.name}")
        
        # ─── PRODUCT UPDATED ───
        else:
            old_name = getattr(instance, '_old_name', None)
            old_price = getattr(instance, '_old_price', None)
            old_stock = getattr(instance, '_old_current_stock', None)
            
            # Check if stock status changed
            # Calculate stock status from OLD values
            old_low = old_stock is not None and old_stock <= instance.min_stock
            old_out = old_stock is not None and old_stock <= 0
            
            # Calculate stock status from NEW values
            new_low = instance.current_stock <= instance.min_stock
            new_out = instance.current_stock <= 0
            
            logger.debug(f"Product {instance.name}: old_stock={old_stock}, new_stock={instance.current_stock}")
            
            # ─── OUT OF STOCK ALERT ───
            if not old_out and new_out:
                # Just went out of stock
                if not has_recent_similar_notification(user, 'out_of_stock', str(instance.id)):
                    NotificationFactory.out_of_stock_alert(
                        user=user,
                        product=instance,
                        async_task=True,
                    )
                    logger.info(f"✅ Out of stock alert: {instance.name}")
            
            # ─── LOW STOCK ALERT ───
            elif not old_low and new_low and not new_out:
                # Just went to low stock (but not out)
                if not has_recent_similar_notification(user, 'low_stock', str(instance.id)):
                    NotificationFactory.low_stock_alert(
                        user=user,
                        product=instance,
                        async_task=True,
                    )
                    logger.info(f"✅ Low stock alert: {instance.name}")
            
            # ─── GENERIC UPDATE NOTIFICATION ───
            elif old_name != instance.name or old_price != instance.price:
                if not has_recent_similar_notification(user, 'product_updated', str(instance.id)):
                    NotificationFactory.product_updated(
                        user=user,
                        product=instance,
                        async_task=True,
                    )
                    logger.info(f"✅ Product updated notification: {instance.name}")
    
    except Exception as e:
        logger.error(f"❌ Error in product_post_save signal: {str(e)}", exc_info=True)


@receiver(post_delete, sender=Product)
def product_post_delete(sender, instance, **kwargs):
    """
    Signal triggered when Product is deleted.
    Creates deleted notification.
    """
    try:
        user = instance.user
        product_name = instance.name
        
        from accounts.services import NotificationService
        
        NotificationService.create_notification(
            user=user,
            title=f"Product {product_name} Deleted",
            message=f"Product '{product_name}' has been removed from your catalog.",
            notification_type='product_deleted',
            priority='medium',
            icon='box-seam-x',
            color='danger',
            async_task=True,
        )
        logger.info(f"✅ Product deleted notification: {product_name}")
    
    except Exception as e:
        logger.error(f"❌ Error in product_post_delete signal: {str(e)}", exc_info=True)