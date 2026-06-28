# accounts/models.py - COMPLETE UPDATED VERSION

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError
from decimal import Decimal
import uuid


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user  = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True')
        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [
        ('owner',  'Owner'),
        ('admin',  'Admin'),
        ('member', 'Member'),
    ]

    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email         = models.EmailField(unique=True, db_index=True)
    first_name    = models.CharField(max_length=100, blank=True)
    last_name     = models.CharField(max_length=100, blank=True)
    company_name  = models.CharField(max_length=255, blank=True)
    phone         = models.CharField(max_length=15,  blank=True)
    profile_photo = models.ImageField(upload_to='profile_photos/', blank=True, null=True)
    role          = models.CharField(max_length=20, choices=ROLE_CHOICES, default='owner')

    # Business / GST details
    business_state   = models.CharField(max_length=100, blank=True)
    gstin            = models.CharField(max_length=15,  blank=True)
    pan_number       = models.CharField(max_length=10,  blank=True)
    business_type    = models.CharField(max_length=50,  blank=True, default='Proprietorship')
    default_gst_rate = models.IntegerField(default=18)
    business_address = models.TextField(blank=True)
    invoice_prefix   = models.CharField(max_length=10,  blank=True, default='INV')

    # Subscription
    current_plan = models.CharField(max_length=50, default='free')
    plan_expires = models.DateTimeField(null=True, blank=True)

    # Notification preferences
    notif_invoice_paid   = models.BooleanField(default=True)
    notif_overdue        = models.BooleanField(default=True)
    notif_new_ticket     = models.BooleanField(default=True)
    notif_new_customer   = models.BooleanField(default=False)
    notif_weekly_summary = models.BooleanField(default=True)
    notif_gst_reminders  = models.BooleanField(default=True)

    # Django internals
    is_active    = models.BooleanField(default=True)
    is_staff     = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    objects = CustomUserManager()

    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return f"{self.email} ({self.first_name} {self.last_name})"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email


class Customer(models.Model):
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user       = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='customers')
    name       = models.CharField(max_length=255)
    email      = models.EmailField()
    phone      = models.CharField(max_length=15, blank=True)
    company    = models.CharField(max_length=255, blank=True)
    gstin      = models.CharField(max_length=15,  blank=True)
    state      = models.CharField(max_length=100, blank=True)
    address    = models.TextField(blank=True)
    notes      = models.TextField(blank=True)
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['email']),
        ]

    def __str__(self):
        return f"{self.name} ({self.company})"


class Invoice(models.Model):
    STATUS_CHOICES = [
        ('draft',     'Draft'),
        ('issued',    'Issued'),
        ('pending',   'Pending'),
        ('paid',      'Paid'),
        ('overdue',   'Overdue'),
        ('cancelled', 'Cancelled'),
    ]

    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user           = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='invoices')
    customer       = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)
    invoice_number = models.CharField(max_length=50, db_index=True)
    issued_date    = models.DateField(default=timezone.now)
    due_date       = models.DateField(null=True, blank=True)
    hsn_sac_code   = models.CharField(max_length=20, blank=True)
    description    = models.TextField(blank=True)
    notes          = models.TextField(blank=True)

    subtotal    = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    gst_rate    = models.DecimalField(max_digits=5,  decimal_places=2, default=Decimal('18.00'))
    gst_amount  = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    cgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    sgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    igst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    total       = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))

    status     = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Invoice {self.invoice_number}"

    def calculate_from_items(self):
        """
        Recalculate invoice totals from all associated InvoiceItem records.
        Call after all items have been saved.
        """
        from decimal import Decimal
        items = self.items.all()
        if not items.exists():
            return
        
        self.subtotal = sum(item.subtotal for item in items) or Decimal('0.00')
        self.gst_amount = sum(item.gst_amount for item in items) or Decimal('0.00')
        self.cgst_amount = sum(item.cgst_amount for item in items) or Decimal('0.00')
        self.sgst_amount = sum(item.sgst_amount for item in items) or Decimal('0.00')
        self.igst_amount = sum(item.igst_amount for item in items) or Decimal('0.00')
        self.total = self.subtotal + self.gst_amount
        
        # Calculate average GST rate
        if self.subtotal > 0:
            avg_rate = sum(item.gst_rate * item.subtotal for item in items) / self.subtotal
            self.gst_rate = round(avg_rate, 2)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['invoice_number']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"Invoice {self.invoice_number}"
        
class ProductCategory(models.Model):
    """Product categories for organising the product catalog."""

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user        = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='product_categories')
    name        = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name        = 'Product Category'
        verbose_name_plural = 'Product Categories'
        indexes = [
            models.Index(fields=['user', 'is_active']),
        ]

    def __str__(self):
        return self.name


class Product(models.Model):
    """Reusable product/service catalog for quick invoice line entry"""

    UNIT_CHOICES = [
        ('pcs',  'Pieces'),
        ('nos',  'Numbers'),
        ('kg',   'Kilograms'),
        ('g',    'Grams'),
        ('l',    'Litres'),
        ('ml',   'Millilitres'),
        ('m',    'Metres'),
        ('sqft', 'Sq. Feet'),
        ('hr',   'Hours'),
        ('day',  'Days'),
        ('month','Months'),
        ('set',  'Set'),
        ('box',  'Box'),
        ('pack', 'Pack'),
    ]

    GST_RATE_CHOICES = [
        (Decimal('0'),    '0%'),
        (Decimal('5'),    '5%'),
        (Decimal('12'),   '12%'),
        (Decimal('18'),   '18%'),
        (Decimal('28'),   '28%'),
    ]

    # ── Existing fields (unchanged) ──────────────────────────────────
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user        = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='products')
    name        = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    hsn_sac     = models.CharField(max_length=20, blank=True)
    price       = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    gst_rate    = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('18.00'))
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    # ── New fields ───────────────────────────────────────────────────
    category       = models.ForeignKey(ProductCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    product_code   = models.CharField(max_length=50, blank=True, db_index=True)
    sku            = models.CharField(max_length=100, blank=True, db_index=True)
    brand          = models.CharField(max_length=100, blank=True)
    unit           = models.CharField(max_length=10, choices=UNIT_CHOICES, default='pcs')
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    min_stock      = models.PositiveIntegerField(default=0)
    current_stock  = models.IntegerField(default=0)
    opening_stock  = models.IntegerField(default=0)
    barcode        = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['user', 'category']),
            models.Index(fields=['sku']),
            models.Index(fields=['product_code']),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Auto-generate product_code on first save if not provided
        if not self.product_code:
            prefix = 'PRD'
            import random, string
            suffix = ''.join(random.choices(string.digits, k=6))
            self.product_code = f"{prefix}-{suffix}"
        super().save(*args, **kwargs)

    @property
    def is_low_stock(self):
        return self.current_stock <= self.min_stock

    @property
    def is_out_of_stock(self):
        return self.current_stock <= 0

    @property
    def profit_margin(self):
        if self.purchase_price > 0:
            return round(((self.price - self.purchase_price) / self.price) * 100, 2)
        return Decimal('0')

class InvoiceItem(models.Model):
    """A single product/service line on an invoice. An Invoice has many InvoiceItems."""

    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('partial', 'Partial'),
        ('paid', 'Paid'),
    ]

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice      = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    product      = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoice_items')

    product_name = models.CharField(max_length=255)
    description  = models.TextField(blank=True)
    hsn_sac_code = models.CharField(max_length=20, blank=True)

    quantity   = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('1'))
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))

    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0'))
    discount_amount  = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))

    gst_rate    = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('18.00'))
    cgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    sgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    igst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    gst_amount  = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))

    subtotal   = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))   # qty * unit_price, before discount
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))   # subtotal - discount + gst
    
    # ← NEW: Payment tracking fields
    amount_paid     = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    payment_status  = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['invoice']),
            models.Index(fields=['payment_status']),  # ← NEW: for faster queries
        ]

    def __str__(self):
        return f"{self.product_name} x{self.quantity} ({self.invoice.invoice_number})"

    def calculate(self, same_state: bool):
        """
        Recalculate this line's discount, GST split, and total.
        same_state: True if customer.state == user.business_state (CGST+SGST), else IGST.
        Call this before saving; does not save itself.
        """
        qty = self.quantity or Decimal('0')
        price = self.unit_price or Decimal('0')
        gst_rate = self.gst_rate or Decimal('0')
        discount_pct = self.discount_percent or Decimal('0')

        self.subtotal = (qty * price).quantize(Decimal('0.01'))

        if self.discount_amount and not discount_pct:
            # explicit discount amount takes precedence if percent wasn't given
            discount = self.discount_amount
        else:
            discount = (self.subtotal * discount_pct / Decimal('100')).quantize(Decimal('0.01'))
            self.discount_amount = discount

        taxable_value = self.subtotal - discount

        total_gst = (taxable_value * gst_rate / Decimal('100')).quantize(Decimal('0.01'))
        self.gst_amount = total_gst

        if same_state:
            half = (total_gst / Decimal('2')).quantize(Decimal('0.01'))
            self.cgst_amount = half
            self.sgst_amount = total_gst - half  # avoids rounding loss
            self.igst_amount = Decimal('0')
        else:
            self.cgst_amount = Decimal('0')
            self.sgst_amount = Decimal('0')
            self.igst_amount = total_gst

        self.line_total = (taxable_value + total_gst).quantize(Decimal('0.01'))
        
        # ← NEW: Update payment status
        self._update_payment_status()
        
        return self.line_total

    # ← NEW METHODS
    def _update_payment_status(self):
        """Update payment_status based on amount_paid vs line_total."""
        if self.line_total <= 0:
            self.payment_status = 'paid'
        elif self.amount_paid >= self.line_total:
            self.payment_status = 'paid'
        elif self.amount_paid > 0:
            self.payment_status = 'partial'
        else:
            self.payment_status = 'pending'

    def get_payment_status_display_badge(self):
        """Return a formatted badge for the payment status."""
        colors = {
            'paid': '✓ Paid',
            'partial': '⊘ Partial',
            'pending': '⧗ Pending',
        }
        return colors.get(self.payment_status, 'Unknown')

    def get_outstanding_amount(self):
        """Calculate remaining amount to be paid."""
        return max(Decimal('0.00'), self.line_total - self.amount_paid)

    @property
    def is_fully_paid(self):
        """Check if item is fully paid."""
        return self.payment_status == 'paid'

    @property
    def is_partially_paid(self):
        """Check if item is partially paid."""
        return self.payment_status == 'partial'

    @property
    def is_pending(self):
        """Check if item is still pending."""
        return self.payment_status == 'pending'

class SupportTicket(models.Model):
    PRIORITY_CHOICES = [
        ('low',    'Low'),
        ('medium', 'Medium'),
        ('high',   'High'),
    ]
    STATUS_CHOICES = [
        ('open',        'Open'),
        ('in_progress', 'In Progress'),
        ('resolved',    'Resolved'),
        ('closed',      'Closed'),
    ]

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user            = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='tickets')
    ticket_number   = models.CharField(max_length=50, unique=True)
    customer_name   = models.CharField(max_length=255)
    customer_mobile = models.CharField(max_length=15, blank=True)
    customer_email  = models.EmailField(blank=True)
    subject         = models.CharField(max_length=255)
    description     = models.TextField()
    priority        = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES,   default='open')
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.ticket_number} - {self.subject}"


class Subscription(models.Model):
    PLAN_CHOICES = [
        ('free',       'Free'),
        ('starter',    'Starter'),
        ('pro',        'Pro'),
        ('enterprise', 'Enterprise'),
    ]

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user       = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='subscription')
    plan       = models.CharField(max_length=50, choices=PLAN_CHOICES, default='free')
    is_active  = models.BooleanField(default=True)
    started_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} - {self.plan}"


class ActivityLog(models.Model):
    ACTION_CHOICES = [
        ('login',   'Login'),
        ('logout',  'Logout'),
        ('create',  'Create'),
        ('update',  'Update'),
        ('delete',  'Delete'),
        ('export',  'Export'),
        ('view',    'View'),
    ]

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user       = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='activity_logs')
    action     = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100, blank=True)
    object_id  = models.CharField(max_length=100, blank=True)
    detail     = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['action']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.action}"


class Notification(models.Model):
    TYPE_CHOICES = [
        ('invoice_paid',    'Invoice Paid'),
        ('invoice_overdue', 'Invoice Overdue'),
        ('ticket_new',      'New Ticket'),
        ('ticket_resolved', 'Ticket Resolved'),
        ('plan_expiry',     'Plan Expiry'),
        ('system',          'System'),
    ]

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user       = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notifications')
    type       = models.CharField(max_length=30, choices=TYPE_CHOICES, default='system')
    title      = models.CharField(max_length=200)
    message    = models.TextField()
    is_read    = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['is_read']),
        ]

    def __str__(self):
        return f"{self.title} - {self.user.email}"


# ============================================
# SETTINGS MODULE MODELS
# ============================================

class CompanySettings(models.Model):
    """Store company profile and settings for each user"""
    
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='company_settings'
    )
    
    # Basic Company Info
    company_name = models.CharField(
        max_length=200,
        help_text="Official company name"
    )
    gstin = models.CharField(
        max_length=15,
        unique=False,
        blank=True,
        null=True,
        help_text="Goods and Services Tax Identification Number (15 digits)"
    )
    pan = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        help_text="Permanent Account Number"
    )
    
    # Address
    address = models.TextField(
        help_text="Full street address"
    )
    city = models.CharField(
        max_length=100,
        help_text="City name"
    )
    state = models.CharField(
        max_length=100,
        help_text="State/Province name"
    )
    pincode = models.CharField(
        max_length=6,
        help_text="Postal code (6 digits for India)"
    )
    
    # Contact Info
    phone = models.CharField(
        max_length=15,
        help_text="Primary contact number"
    )
    email = models.EmailField(
        help_text="Primary business email"
    )
    website = models.URLField(
        blank=True,
        null=True,
        help_text="Company website URL"
    )
    
    # Logo
    logo = models.ImageField(
        upload_to='company_logos/%Y/%m/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'svg'])],
        help_text="Company logo (PNG, JPG, SVG - max 2MB)"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Company Settings"
        verbose_name_plural = "Company Settings"
    
    def __str__(self):
        return f"{self.company_name} - {self.user.email}"
    
    def clean(self):
        if self.gstin and len(self.gstin) != 15:
            raise ValidationError("GSTIN must be 15 digits")
        if self.pan and len(self.pan) != 10:
            raise ValidationError("PAN must be 10 characters")
        if self.pincode and not self.pincode.isdigit():
            raise ValidationError("Pincode must contain only digits")


class GSTSettings(models.Model):
    """GST configuration for invoices"""
    
    GST_RATE_CHOICES = [
        (0, '0%'),
        (5, '5%'),
        (12, '12%'),
        (18, '18%'),
        (28, '28%'),
    ]
    
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='gst_settings'
    )
    
    # GST Rate
    default_gst_rate = models.IntegerField(
        choices=GST_RATE_CHOICES,
        default=18,
        help_text="Default GST rate for invoices"
    )
    
    # HSN/SAC Codes
    default_hsn_code = models.CharField(
        max_length=8,
        blank=True,
        null=True,
        help_text="Default Harmonized System of Nomenclature code"
    )
    default_sac_code = models.CharField(
        max_length=6,
        blank=True,
        null=True,
        help_text="Default Service Accounting Code"
    )
    
    # GST Compliance
    is_registered = models.BooleanField(
        default=True,
        help_text="Is company registered under GST?"
    )
    
    # Composition Scheme (optional)
    composition_scheme = models.BooleanField(
        default=False,
        help_text="Is company under composition scheme?"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "GST Settings"
        verbose_name_plural = "GST Settings"
    
    def __str__(self):
        return f"GST Settings - {self.user.email} ({self.default_gst_rate}%)"


class SMTPSettings(models.Model):
    """Email configuration for sending invoices and notifications"""
    
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='smtp_settings'
    )
    
    # SMTP Configuration
    smtp_host = models.CharField(
        max_length=255,
        help_text="SMTP server address (e.g., smtp.gmail.com)"
    )
    smtp_port = models.IntegerField(
        default=587,
        help_text="SMTP port (typically 587 for TLS, 465 for SSL)"
    )
    smtp_username = models.CharField(
        max_length=255,
        help_text="SMTP username or email address"
    )
    smtp_password = models.CharField(
        max_length=255,
        help_text="SMTP password (encrypted)"
    )
    
    # Security
    use_tls = models.BooleanField(
        default=True,
        help_text="Use TLS encryption"
    )
    use_ssl = models.BooleanField(
        default=False,
        help_text="Use SSL encryption (usually for port 465)"
    )
    
    # Sender Details
    from_email = models.EmailField(
        help_text="From email address for outgoing emails"
    )
    from_name = models.CharField(
        max_length=255,
        help_text="From name for outgoing emails"
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Enable/disable SMTP configuration"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "SMTP Settings"
        verbose_name_plural = "SMTP Settings"
    
    def __str__(self):
        return f"SMTP Settings - {self.user.email} ({self.smtp_host})"


class InvoiceBranding(models.Model):
    """Invoice design and branding settings"""
    
    COLOR_CHOICES = [
        ('#0066cc', 'Blue'),
        ('#1a1a1a', 'Dark Gray'),
        ('#27ae60', 'Green'),
        ('#e74c3c', 'Red'),
        ('#f39c12', 'Orange'),
        ('#9b59b6', 'Purple'),
        ('#3498db', 'Light Blue'),
        ('#2ecc71', 'Light Green'),
    ]
    
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='invoice_branding'
    )
    
    # Branding
    primary_color = models.CharField(
        max_length=7,
        choices=COLOR_CHOICES,
        default='#0066cc',
        help_text="Primary color for invoice header and accents"
    )
    secondary_color = models.CharField(
        max_length=7,
        default='#f5f7fa',
        help_text="Secondary color for invoice background"
    )
    
    # Text Content
    invoice_title = models.CharField(
        max_length=50,
        default='INVOICE',
        help_text="Title shown in invoice"
    )
    footer_text = models.TextField(
        blank=True,
        null=True,
        help_text="Custom footer text for invoices"
    )
    terms_and_conditions = models.TextField(
        blank=True,
        null=True,
        help_text="Terms & conditions text for invoices"
    )
    
    # Signature
    signature_text = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Signature/authorization text (e.g., 'Authorized By')"
    )
    signature_image = models.ImageField(
        upload_to='signatures/%Y/%m/',
        blank=True,
        null=True,
        help_text="Digital signature image"
    )
    
    # Invoice Options
    show_hsn_sac = models.BooleanField(
        default=True,
        help_text="Show HSN/SAC codes in invoice items"
    )
    show_tax_breakdown = models.BooleanField(
        default=True,
        help_text="Show CGST/SGST/IGST breakdown"
    )
    show_notes = models.BooleanField(
        default=True,
        help_text="Show notes section in invoice"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Invoice Branding"
        verbose_name_plural = "Invoice Branding"
    
    def __str__(self):
        return f"Invoice Branding - {self.user.email}"


class UserProfileSettings(models.Model):
    """Additional user profile settings"""
    
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='profile_settings'
    )
    
    # Contact
    mobile_number = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        help_text="Mobile/phone number"
    )
    
    # Profile
    bio = models.TextField(
        blank=True,
        null=True,
        help_text="Short bio or designation"
    )
    profile_picture = models.ImageField(
        upload_to='profiles/%Y/%m/',
        blank=True,
        null=True,
        help_text="Profile picture"
    )
    
    # Preferences
    timezone = models.CharField(
        max_length=50,
        default='Asia/Kolkata',
        help_text="Timezone for user"
    )
    language = models.CharField(
        max_length=10,
        default='en',
        choices=[('en', 'English'), ('hi', 'हिन्दी'), ('kn', 'ಕನ್ನಡ')],
        help_text="Preferred language"
    )
    
    # Notifications
    email_notifications = models.BooleanField(
        default=True,
        help_text="Receive email notifications"
    )
    invoice_reminders = models.BooleanField(
        default=True,
        help_text="Receive invoice payment reminders"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "User Profile Settings"
        verbose_name_plural = "User Profile Settings"
    
    def __str__(self):
        return f"Profile Settings - {self.user.email}"


class SettingsAuditLog(models.Model):
    """Track changes to settings"""
    
    ACTION_CHOICES = [
        ('update', 'Updated'),
        ('create', 'Created'),
        ('delete', 'Deleted'),
    ]
    
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='settings_audit_logs'
    )
    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES
    )
    model_name = models.CharField(
        max_length=50,
        help_text="Model that was changed"
    )
    field_changed = models.CharField(
        max_length=50,
        help_text="Field that was changed"
    )
    old_value = models.TextField(
        blank=True,
        null=True
    )
    new_value = models.TextField(
        blank=True,
        null=True
    )
    ip_address = models.GenericIPAddressField(
        blank=True,
        null=True
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.action} - {self.model_name}"