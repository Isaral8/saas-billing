# billing/admin.py
# Professional Django Admin Configuration for Billing-Specific Models
# NOTE: Do NOT register CustomUser, Customer, Invoice, SupportTicket here
# They are already registered in accounts/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone

# Only import billing-specific models that don't exist in accounts app
# If these models don't exist in your billing app, you can safely delete the entire file
# or leave it empty (Django requires an admin.py file in each app)

try:
    from .models import Subscription, Plan, Payment
except ImportError:
    # These models may not exist in your billing app
    # That's fine - this file can remain empty
    Subscription = None
    Plan = None
    Payment = None


# =====================================================================
# PLAN ADMIN (if Plan model exists in billing app)
# =====================================================================

if Plan is not None:
    @admin.register(Plan)
    class PlanAdmin(admin.ModelAdmin):
        """
        Admin for billing plans.
        Manage subscription plans and pricing.
        """
        
        list_display = (
            'name',
            'get_price_display',
            'get_features_count',
            'get_billing_cycle',
            'is_active',
            'created_at'
        )
        
        list_filter = (
            'is_active',
            'billing_cycle',
            'created_at',
        )
        
        search_fields = (
            'name',
            'description',
        )
        
        readonly_fields = (
            'created_at',
            'updated_at',
        )
        
        fieldsets = (
            ('Plan Information', {
                'fields': ('name', 'description')
            }),
            ('Pricing', {
                'fields': ('price', 'currency', 'billing_cycle')
            }),
            ('Features', {
                'fields': ('features', 'max_customers', 'max_invoices'),
            }),
            ('Status', {
                'fields': ('is_active',)
            }),
            ('Timestamps', {
                'fields': ('created_at', 'updated_at'),
                'classes': ('collapse',)
            }),
        )
        
        ordering = ('price',)
        list_per_page = 25
        
        def get_price_display(self, obj):
            """Display formatted price"""
            try:
                return format_html(
                    '<span style="color: #0066cc; font-weight: 600;">₹{:,.2f}</span>',
                    float(obj.price)
                )
            except:
                return '—'
        get_price_display.short_description = 'Price'
        
        def get_features_count(self, obj):
            """Show number of features"""
            try:
                if isinstance(obj.features, list):
                    count = len(obj.features)
                else:
                    count = obj.features.count()
                return count
            except:
                return 0
        get_features_count.short_description = 'Features'
        
        def get_billing_cycle(self, obj):
            """Display billing cycle"""
            cycles = {
                'monthly': '📅 Monthly',
                'annual': '📊 Annual',
                'lifetime': '♾️ Lifetime'
            }
            return cycles.get(obj.billing_cycle, obj.billing_cycle)
        get_billing_cycle.short_description = 'Billing'


# =====================================================================
# SUBSCRIPTION ADMIN (if Subscription model exists in billing app)
# =====================================================================

if Subscription is not None:
    @admin.register(Subscription)
    class SubscriptionAdmin(admin.ModelAdmin):
        """
        Admin for customer subscriptions.
        Track active and inactive subscriptions.
        """
        
        list_display = (
            'get_subscription_id',
            'get_customer_display',
            'plan',
            'get_status_badge',
            'start_date',
            'end_date',
            'get_days_until_renewal',
            'created_at'
        )
        
        list_filter = (
            'status',
            'plan',
            'start_date',
            'end_date',
            'created_at',
        )
        
        search_fields = (
            'customer__name',
            'customer__email',
            'plan__name',
            'id'
        )
        
        readonly_fields = (
            'id',
            'created_at',
            'updated_at'
        )
        
        fieldsets = (
            ('Subscription Information', {
                'fields': ('id', 'customer', 'plan', 'status')
            }),
            ('Duration', {
                'fields': ('start_date', 'end_date')
            }),
            ('Timestamps', {
                'fields': ('created_at', 'updated_at'),
                'classes': ('collapse',)
            }),
        )
        
        actions = ['activate_subscriptions', 'deactivate_subscriptions', 'renew_subscriptions']
        ordering = ('-start_date',)
        list_per_page = 25
        
        def get_subscription_id(self, obj):
            """Display subscription ID"""
            return format_html('<strong>#{}</strong>', obj.id)
        get_subscription_id.short_description = 'Subscription'
        
        def get_customer_display(self, obj):
            """Display customer name"""
            try:
                return obj.customer.name
            except:
                return '—'
        get_customer_display.short_description = 'Customer'
        
        def get_status_badge(self, obj):
            """Display status badge"""
            color = '#16a34a' if obj.status == 'active' else '#dc2626'
            return format_html(
                '<span style="background: {}; color: white; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;">{}</span>',
                color, obj.status.upper()
            )
        get_status_badge.short_description = 'Status'
        
        def get_days_until_renewal(self, obj):
            """Show days until renewal"""
            try:
                if obj.end_date:
                    days = (obj.end_date - timezone.now().date()).days
                    if days <= 0:
                        return format_html('<span style="color: #dc2626;">⚠️ Expired</span>')
                    elif days <= 7:
                        return format_html('<span style="color: #f59e0b;">🔔 {} days</span>', days)
                    else:
                        return format_html('<span style="color: #16a34a;">✓ {} days</span>', days)
            except:
                pass
            return '—'
        get_days_until_renewal.short_description = 'Renewal'
        
        # Bulk Actions
        def activate_subscriptions(self, request, queryset):
            """Bulk action: Activate subscriptions"""
            count = queryset.update(status='active')
            self.message_user(request, f'✓ {count} subscription(s) activated')
        activate_subscriptions.short_description = "✓ Activate Subscriptions"
        
        def deactivate_subscriptions(self, request, queryset):
            """Bulk action: Deactivate subscriptions"""
            count = queryset.update(status='inactive')
            self.message_user(request, f'✕ {count} subscription(s) deactivated')
        deactivate_subscriptions.short_description = "✕ Deactivate Subscriptions"
        
        def renew_subscriptions(self, request, queryset):
            """Bulk action: Mark for renewal"""
            count = queryset.update(status='renewal_pending')
            self.message_user(request, f'🔄 {count} subscription(s) marked for renewal')
        renew_subscriptions.short_description = "🔄 Mark for Renewal"


# =====================================================================
# PAYMENT ADMIN (if Payment model exists in billing app)
# =====================================================================

if Payment is not None:
    @admin.register(Payment)
    class PaymentAdmin(admin.ModelAdmin):
        """
        Admin for payment tracking.
        Monitor all transactions and payment status.
        """
        
        list_display = (
            'get_payment_id',
            'get_customer_display',
            'get_amount_display',
            'payment_method',
            'get_status_badge',
            'payment_date',
            'created_at'
        )
        
        list_filter = (
            'status',
            'payment_method',
            'payment_date',
            'created_at',
        )
        
        search_fields = (
            'id',
            'customer__name',
            'customer__email',
            'transaction_id',
        )
        
        readonly_fields = (
            'id',
            'transaction_id',
            'created_at',
            'updated_at',
        )
        
        fieldsets = (
            ('Payment Information', {
                'fields': ('id', 'customer', 'amount', 'currency')
            }),
            ('Payment Details', {
                'fields': ('payment_method', 'payment_date', 'status', 'transaction_id')
            }),
            ('Notes', {
                'fields': ('notes',),
                'classes': ('collapse',)
            }),
            ('Timestamps', {
                'fields': ('created_at', 'updated_at'),
                'classes': ('collapse',)
            }),
        )
        
        actions = ['mark_completed', 'mark_failed', 'mark_refunded']
        ordering = ('-payment_date',)
        list_per_page = 25
        date_hierarchy = 'payment_date'
        
        def get_payment_id(self, obj):
            """Display payment ID"""
            return format_html('<strong style="color: #0066cc;">#{}</strong>', obj.id)
        get_payment_id.short_description = 'Payment ID'
        
        def get_customer_display(self, obj):
            """Display customer name"""
            try:
                return obj.customer.name
            except:
                return '—'
        get_customer_display.short_description = 'Customer'
        
        def get_amount_display(self, obj):
            """Display formatted amount"""
            try:
                return format_html(
                    '<span style="color: #0066cc; font-weight: 600;">₹{:,.2f}</span>',
                    float(obj.amount)
                )
            except:
                return '—'
        get_amount_display.short_description = 'Amount'
        
        def get_status_badge(self, obj):
            """Display status badge"""
            status_colors = {
                'pending': '#f59e0b',
                'completed': '#16a34a',
                'failed': '#dc2626',
                'refunded': '#9ca3af'
            }
            color = status_colors.get(obj.status, '#9ca3af')
            return format_html(
                '<span style="background: {}; color: white; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;">{}</span>',
                color, obj.status.upper()
            )
        get_status_badge.short_description = 'Status'
        
        # Bulk Actions
        def mark_completed(self, request, queryset):
            """Mark payments as completed"""
            count = queryset.update(status='completed')
            self.message_user(request, f'✓ {count} payment(s) marked as completed')
        mark_completed.short_description = "✓ Mark Completed"
        
        def mark_failed(self, request, queryset):
            """Mark payments as failed"""
            count = queryset.update(status='failed')
            self.message_user(request, f'✕ {count} payment(s) marked as failed')
        mark_failed.short_description = "✕ Mark Failed"
        
        def mark_refunded(self, request, queryset):
            """Mark payments as refunded"""
            count = queryset.update(status='refunded')
            self.message_user(request, f'💰 {count} payment(s) refunded')
        mark_refunded.short_description = "💰 Mark Refunded"


# =====================================================================
# ADMIN SITE CUSTOMIZATION
# =====================================================================

admin.site.site_header = "💰 iSaral Billing Admin"
admin.site.site_title = "iSaral Billing"
admin.site.index_title = "Billing Management"

# ============================================
# TICKET REPLY ADMIN (PHASE 1-3)
# ============================================


