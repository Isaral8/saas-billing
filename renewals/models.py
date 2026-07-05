from django.db import models
class Renewal(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('invoice_created', 'Invoice Created'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    invoice_created = models.BooleanField(default=False)
    invoice = models.OneToOneField('accounts.Invoice', null=True, blank=True, on_delete=models.SET_NULL)
    processed_at = models.DateTimeField(null=True, blank=True)
    reminder_7_days_sent = models.BooleanField(default=False)
    reminder_30_days_sent = models.BooleanField(default=False)