from django.db import models
from django.utils import timezone
from accounts.models import CustomUser

class Plan(models.Model):
    name = models.CharField(max_length=100)
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2)
    price_yearly = models.DecimalField(max_digits=10, decimal_places=2)
    max_users = models.IntegerField()
    features = models.JSONField()
    razorpay_plan_id = models.CharField(max_length=100, blank=True)

class Subscription(models.Model):
    # organization = models.ForeignKey('accounts.Organization', on_delete=models.CASCADE)
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE)
    razorpay_subscription_id = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=[
        ('active', 'Active'),
        ('cancelled', 'Cancelled'),
        ('past_due', 'Past Due')
    ])
    current_period_start = models.DateTimeField()
    current_period_end = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

class Invoice(models.Model):
    # organization = models.ForeignKey('accounts.Organization', on_delete=models.CASCADE)
    invoice_number = models.CharField(max_length=50, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    gst_amount = models.DecimalField(max_digits=10, decimal_places=2)
    cgst = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    sgst = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    igst = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, default='unpaid')
    razorpay_payment_id = models.CharField(max_length=100, blank=True)
    pdf_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

# ============================================
# TICKET REPLY MODEL (PHASE 1-3)
# ============================================

class TicketReply(models.Model):
    """Model to store replies/comments on support tickets"""
    
    ticket = models.ForeignKey(
        'accounts.SupportTicket',
        on_delete=models.CASCADE,
        related_name='replies'
    )
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='ticket_replies'
    )
    message = models.TextField(
        help_text="Reply message content"
    )
    is_staff_reply = models.BooleanField(
        default=False,
        help_text="True if this is a support staff/admin reply"
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        auto_now=True
    )
    
    class Meta:
        ordering = ['created_at']
        verbose_name = "Ticket Reply"
        verbose_name_plural = "Ticket Replies"
        indexes = [
            models.Index(fields=['ticket', 'created_at']),
            models.Index(fields=['user']),
        ]
    
    def __str__(self):
        return f"Reply on {self.ticket.id} by {self.user.email} at {self.created_at}"
    
    def get_formatted_time(self):
        """Return formatted time for display"""
        now = timezone.now()
        diff = now - self.created_at
        
        if diff.total_seconds() < 60:
            return "just now"
        elif diff.total_seconds() < 3600:
            minutes = int(diff.total_seconds() // 60)
            return f"{minutes}m ago"
        elif diff.total_seconds() < 86400:
            hours = int(diff.total_seconds() // 3600)
            return f"{hours}h ago"
        else:
            days = int(diff.total_seconds() // 86400)
            return f"{days}d ago"
    
    def get_sender_name(self):
        """Get display name for the sender"""
        if self.is_staff_reply:
            return "Support Team"
        return self.user.get_full_name() or self.user.email

