from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Sum, Q
from accounts.models import (
    CustomUser, Customer, Invoice, SupportTicket, Subscription, Notification
)
from accounts.emails import (
    send_invoice_email,
    send_payment_confirmation_email,
    send_ticket_confirmation_email,
    send_ticket_update_email,
)


# ============================================
# CUSTOM USER ADMIN
# ============================================

@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):

    list_display = ('get_name', 'email', 'company_name', 'current_plan', 'get_role_badge', 'is_active', 'last_login')
    list_filter  = ('is_active', 'is_staff', 'is_superuser', 'current_plan')
    search_fields = ('email', 'first_name', 'last_name', 'company_name')
    readonly_fields = ('last_login', 'created_at', 'updated_at', 'get_summary')

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'phone')}),
        ('Company & plan', {'fields': ('company_name', 'current_plan', 'role')}),
        ('GST details', {
            'fields': ('business_state', 'gstin', 'pan_number', 'business_type',
                       'default_gst_rate', 'business_address', 'invoice_prefix'),
            'classes': ('collapse',),
        }),
        ('Notifications', {
            'fields': ('notif_invoice_paid', 'notif_overdue', 'notif_new_ticket',
                       'notif_new_customer', 'notif_weekly_summary', 'notif_gst_reminders'),
            'classes': ('collapse',),
        }),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups')}),
        ('Metadata', {'fields': ('last_login', 'created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    ordering = ('-last_login',)
    list_per_page = 25

    def get_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.email
    get_name.short_description = 'Name'

    def get_role_badge(self, obj):
        if obj.is_superuser:
            color, label = '#dc2626', 'SUPERUSER'
        elif obj.is_staff:
            color, label = '#1d4ed8', 'STAFF'
        else:
            color, label = '#6b7280', obj.role.upper()
        return format_html(
            '<span style="background:{};color:#fff;padding:3px 8px;border-radius:3px;font-size:11px;font-weight:600">{}</span>',
            color, label
        )
    get_role_badge.short_description = 'Role'

    def get_summary(self, obj):
        invoices  = Invoice.objects.filter(user=obj).count()
        customers = Customer.objects.filter(user=obj).count()
        return format_html(
            '<strong>Invoices:</strong> {} &nbsp;|&nbsp; <strong>Customers:</strong> {}',
            invoices, customers
        )
    get_summary.short_description = 'Summary'


# ============================================
# CUSTOMER ADMIN
# ============================================

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):

    list_display  = ('name', 'email', 'phone', 'company', 'get_gstin_badge',
                     'get_invoice_count', 'get_total_revenue', 'created_at')
    list_filter   = ('created_at', 'state')
    search_fields = ('name', 'email', 'phone', 'gstin', 'company')
    readonly_fields = ('id', 'created_at', 'updated_at', 'get_stats')

    fieldsets = (
        ('Basic information', {
            'fields': ('user', 'name', 'email', 'phone', 'company', 'id'),
        }),
        ('Tax & compliance', {
            'fields': ('gstin', 'state'),
        }),
        ('Address', {
            'fields': ('address',),
        }),
        ('Statistics', {
            'fields': ('get_stats',),
            'classes': ('collapse',),
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    actions    = ['export_customers_csv']
    ordering   = ('-created_at',)
    list_per_page = 25
    date_hierarchy = 'created_at'

    def get_gstin_badge(self, obj):
        if not obj.gstin:
            return '—'
        if len(obj.gstin) == 15:
            return format_html(
                '<span style="background:#dcfce7;color:#166534;padding:3px 8px;border-radius:3px;font-size:11px;font-weight:600">✓ {}</span>',
                obj.gstin
            )
        return format_html(
            '<span style="background:#fef3c7;color:#92400e;padding:3px 8px;border-radius:3px;font-size:11px;font-weight:600">⚠ {}</span>',
            obj.gstin
        )
    get_gstin_badge.short_description = 'GSTIN'

    def get_invoice_count(self, obj):
        return obj.invoice_set.count()
    get_invoice_count.short_description = 'Invoices'

    def get_total_revenue(self, obj):
        total = obj.invoice_set.filter(status='paid').aggregate(Sum('total'))['total__sum'] or 0
        return format_html('<span style="color:#1d4ed8;font-weight:600">₹{:,.2f}</span>', float(total))
    get_total_revenue.short_description = 'Revenue'

    def get_stats(self, obj):
        invoices = obj.invoice_set.all()
        paid     = invoices.filter(status='paid').aggregate(Sum('total'))['total__sum'] or 0
        pending  = invoices.filter(status__in=['issued', 'pending']).aggregate(Sum('total'))['total__sum'] or 0
        return format_html(
            '<p><strong>Total invoices:</strong> {}</p>'
            '<p><strong>Paid:</strong> ₹{:,.2f}</p>'
            '<p><strong>Pending:</strong> ₹{:,.2f}</p>',
            invoices.count(), float(paid), float(pending)
        )
    get_stats.short_description = 'Customer statistics'

    def export_customers_csv(self, request, queryset):
        import csv
        from django.http import HttpResponse
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="customers.csv"'
        writer = csv.writer(response)
        writer.writerow(['Name', 'Email', 'Phone', 'Company', 'GSTIN', 'State', 'Invoices'])
        for c in queryset:
            writer.writerow([c.name, c.email, c.phone, c.company, c.gstin, c.state, c.invoice_set.count()])
        return response
    export_customers_csv.short_description = 'Export selected customers to CSV'


# ============================================
# INVOICE ADMIN
# ============================================

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):

    list_display  = ('get_invoice_link', 'get_customer_link', 'get_amount',
                     'get_status_badge', 'issued_date', 'get_payment_status')
    list_filter   = ('status', 'issued_date', 'due_date')
    search_fields = ('invoice_number', 'customer__name', 'customer__email')
    readonly_fields = ('id', 'created_at', 'updated_at', 'get_summary')

    fieldsets = (
        ('Invoice details', {
            'fields': ('user', 'invoice_number', 'customer', 'issued_date', 'due_date', 'hsn_sac_code'),
        }),
        ('Amounts', {
            'fields': ('subtotal', 'gst_rate', 'gst_amount', 'cgst_amount', 'sgst_amount', 'igst_amount', 'total'),
        }),
        ('Status & notes', {
            'fields': ('status', 'notes'),
        }),
        ('Summary', {'fields': ('get_summary',), 'classes': ('collapse',)}),
        ('Metadata', {'fields': ('id', 'created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    actions    = ['mark_paid', 'mark_overdue', 'send_invoice_email_action',
                  'send_payment_email_action', 'export_invoices_csv']
    ordering   = ('-issued_date',)
    list_per_page = 25
    date_hierarchy = 'issued_date'

    def get_invoice_link(self, obj):
        return format_html('<strong style="color:#1d4ed8">{}</strong>', obj.invoice_number)
    get_invoice_link.short_description = 'Invoice #'

    def get_customer_link(self, obj):
        if not obj.customer:
            return '—'
        url = reverse('admin:accounts_customer_change', args=[obj.customer.id])
        return format_html('<a href="{}">{}</a>', url, obj.customer.name)
    get_customer_link.short_description = 'Customer'

    def get_amount(self, obj):
        return format_html('<span style="color:#1d4ed8;font-weight:600">₹{:,.2f}</span>', float(obj.total or 0))
    get_amount.short_description = 'Total'

    def get_status_badge(self, obj):
        colors = {
            'draft': '#6b7280', 'issued': '#f59e0b', 'pending': '#f59e0b',
            'paid': '#16a34a', 'overdue': '#dc2626', 'cancelled': '#374151',
        }
        return format_html(
            '<span style="background:{};color:#fff;padding:4px 8px;border-radius:3px;font-size:11px;font-weight:600">{}</span>',
            colors.get(obj.status, '#6b7280'), obj.status.upper()
        )
    get_status_badge.short_description = 'Status'

    def get_payment_status(self, obj):
        from datetime import date
        if obj.status == 'paid':
            return format_html('<span style="color:#16a34a">✓ Paid</span>')
        if obj.due_date:
            days = (obj.due_date - date.today()).days
            if days < 0:
                return format_html('<span style="color:#dc2626">Overdue {} days</span>', abs(days))
            return format_html('<span style="color:#f59e0b">Due in {} days</span>', days)
        return '—'
    get_payment_status.short_description = 'Payment'

    def get_summary(self, obj):
        return format_html(
            '<p><strong>Subtotal:</strong> ₹{:,.2f}</p>'
            '<p><strong>GST ({:.0f}%):</strong> ₹{:,.2f}</p>'
            '<p><strong>Total:</strong> ₹{:,.2f}</p>',
            float(obj.subtotal or 0), float(obj.gst_rate or 18),
            float(obj.gst_amount or 0), float(obj.total or 0)
        )
    get_summary.short_description = 'Amount breakdown'

    def mark_paid(self, request, queryset):
        count = queryset.update(status='paid')
        self.message_user(request, f'{count} invoice(s) marked as paid.')
    mark_paid.short_description = 'Mark as paid'

    def mark_overdue(self, request, queryset):
        count = queryset.update(status='overdue')
        self.message_user(request, f'{count} invoice(s) marked as overdue.')
    mark_overdue.short_description = 'Mark as overdue'

    def send_invoice_email_action(self, request, queryset):
        count = sum(1 for inv in queryset if send_invoice_email(inv))
        self.message_user(request, f'Invoice email sent to {count} customer(s).')
    send_invoice_email_action.short_description = 'Send invoice email'

    def send_payment_email_action(self, request, queryset):
        count = sum(1 for inv in queryset.filter(status='paid') if send_payment_confirmation_email(inv))
        self.message_user(request, f'Payment confirmation sent to {count} customer(s).')
    send_payment_email_action.short_description = 'Send payment confirmation'

    def export_invoices_csv(self, request, queryset):
        import csv
        from django.http import HttpResponse
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="invoices.csv"'
        writer = csv.writer(response)
        writer.writerow(['Invoice #', 'Customer', 'Subtotal', 'GST', 'Total', 'Status', 'Date'])
        for inv in queryset:
            writer.writerow([
                inv.invoice_number,
                inv.customer.name if inv.customer else 'N/A',
                inv.subtotal, inv.gst_amount, inv.total,
                inv.get_status_display(),
                inv.issued_date.strftime('%d-%m-%Y'),
            ])
        return response
    export_invoices_csv.short_description = 'Export invoices to CSV'


# ============================================
# SUPPORT TICKET ADMIN
# ============================================

@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):

    list_display  = ('ticket_number', 'subject', 'customer_name', 'get_priority_badge',
                     'get_status_badge', 'get_age', 'created_at')
    list_filter   = ('priority', 'status', 'created_at')
    search_fields = ('ticket_number', 'subject', 'customer_name', 'customer_email')
    readonly_fields = ('id', 'ticket_number', 'created_at', 'updated_at')

    fieldsets = (
        ('Ticket info', {
            'fields': ('user', 'ticket_number', 'subject', 'id'),
        }),
        ('Customer', {
            'fields': ('customer_name', 'customer_email', 'customer_mobile'),
        }),
        ('Details', {
            'fields': ('description', 'priority', 'status'),
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    actions    = ['close_tickets', 'reopen_tickets', 'mark_high_priority',
                  'send_confirmation_email', 'send_update_email']
    ordering   = ('-created_at',)
    list_per_page = 25
    date_hierarchy = 'created_at'

    def get_priority_badge(self, obj):
        colors = {'low': '#16a34a', 'medium': '#f59e0b', 'high': '#dc2626'}
        return format_html(
            '<span style="background:{};color:#fff;padding:3px 8px;border-radius:3px;font-size:11px;font-weight:600">{}</span>',
            colors.get(obj.priority, '#6b7280'), obj.priority.upper()
        )
    get_priority_badge.short_description = 'Priority'

    def get_status_badge(self, obj):
        colors = {'open': '#3b82f6', 'in_progress': '#f59e0b', 'resolved': '#16a34a', 'closed': '#6b7280'}
        return format_html(
            '<span style="background:{};color:#fff;padding:3px 8px;border-radius:3px;font-size:11px;font-weight:600">{}</span>',
            colors.get(obj.status, '#6b7280'), obj.status.upper()
        )
    get_status_badge.short_description = 'Status'

    def get_age(self, obj):
        from datetime import date
        days = (date.today() - obj.created_at.date()).days
        return 'Today' if days == 0 else f'{days}d ago'
    get_age.short_description = 'Age'

    def close_tickets(self, request, queryset):
        count = queryset.update(status='closed')
        self.message_user(request, f'{count} ticket(s) closed.')
    close_tickets.short_description = 'Close selected tickets'

    def reopen_tickets(self, request, queryset):
        count = queryset.update(status='open')
        self.message_user(request, f'{count} ticket(s) reopened.')
    reopen_tickets.short_description = 'Reopen selected tickets'

    def mark_high_priority(self, request, queryset):
        count = queryset.update(priority='high')
        self.message_user(request, f'{count} ticket(s) marked high priority.')
    mark_high_priority.short_description = 'Mark as high priority'

    def send_confirmation_email(self, request, queryset):
        count = sum(1 for t in queryset if send_ticket_confirmation_email(t))
        self.message_user(request, f'Confirmation email sent to {count} customer(s).')
    send_confirmation_email.short_description = 'Send confirmation email'

    def send_update_email(self, request, queryset):
        msg = 'Your ticket is being reviewed by our team. Thank you for your patience.'
        count = sum(1 for t in queryset if send_ticket_update_email(t, msg))
        self.message_user(request, f'Update email sent to {count} customer(s).')
    send_update_email.short_description = 'Send update email'


# ============================================
# SUBSCRIPTION ADMIN
# ============================================

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display  = ('user', 'plan', 'is_active', 'created_at')
    list_filter   = ('plan', 'is_active')
    search_fields = ('user__email', 'user__company_name')
    readonly_fields = ('id', 'created_at', 'updated_at')


# ============================================
# NOTIFICATION ADMIN - PHASE 2
# ============================================

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """
    Notification admin with search, filters, bulk actions, and smart display.
    """
    
    list_display = (
        'get_title_link',
        'get_user_link',
        'get_type_badge',
        'get_priority_badge',
        'get_read_status',
        'created_at'
    )
    
    list_filter = (
        'notification_type',
        'priority',
        'is_read',
        'created_at',
        ('created_at', admin.DateFieldListFilter),
    )
    
    search_fields = (
        'title',
        'message',
        'user__email',
        'user__first_name',
        'user__last_name',
        'related_object_id',
    )
    
    readonly_fields = (
        'id',
        'created_at',
        'updated_at',
        'get_related_object_link',
    )
    
    fieldsets = (
        ('Notification Details', {
            'fields': ('user', 'notification_type', 'title', 'message', 'id'),
        }),
        ('Metadata', {
            'fields': ('priority', 'is_read', 'icon', 'color'),
        }),
        ('Related Object', {
            'fields': ('related_model', 'related_object_id', 'get_related_object_link', 'action_url'),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    actions = [
        'mark_as_read_action',
        'mark_as_unread_action',
        'delete_selected',
    ]
    
    ordering = ('-created_at',)
    list_per_page = 50
    date_hierarchy = 'created_at'
    
    def get_title_link(self, obj):
        """Display title with link to change view."""
        url = reverse('admin:accounts_notification_change', args=[obj.id])
        return format_html(
            '<a href="{}">{}</a>',
            url,
            obj.title[:50] + '...' if len(obj.title) > 50 else obj.title
        )
    get_title_link.short_description = 'Title'
    
    def get_user_link(self, obj):
        """Link to user admin."""
        url = reverse('admin:accounts_customuser_change', args=[obj.user.id])
        return format_html(
            '<a href="{}">{}</a>',
            url,
            obj.user.email
        )
    get_user_link.short_description = 'User'
    
    def get_type_badge(self, obj):
        """Color-coded notification type badge."""
        color_map = {
            'invoice_created': '#3b82f6',
            'invoice_updated': '#3b82f6',
            'invoice_deleted': '#dc2626',
            'invoice_paid': '#16a34a',
            'invoice_pending': '#f59e0b',
            'payment_received': '#16a34a',
            'payment_failed': '#dc2626',
            'customer_added': '#8b5cf6',
            'customer_updated': '#8b5cf6',
            'customer_deleted': '#dc2626',
            'product_added': '#14b8a6',
            'product_updated': '#14b8a6',
            'product_deleted': '#dc2626',
            'low_stock': '#f59e0b',
            'out_of_stock': '#dc2626',
            'backup_created': '#16a34a',
            'backup_failed': '#dc2626',
            'renewal_due': '#f59e0b',
            'renewal_expired': '#dc2626',
            'subscription_renewed': '#16a34a',
            'system_info': '#6b7280',
            'system_success': '#16a34a',
            'system_warning': '#f59e0b',
            'system_error': '#dc2626',
        }
        
        color = color_map.get(obj.notification_type, '#6b7280')
        label = obj.get_notification_type_display()
        
        return format_html(
            '<span style="background:{};color:#fff;padding:3px 8px;border-radius:3px;font-size:11px;font-weight:600">{}</span>',
            color,
            label
        )
    get_type_badge.short_description = 'Type'
    
    def get_priority_badge(self, obj):
        """Priority level badge."""
        colors = {
            'low': '#6b7280',
            'medium': '#f59e0b',
            'high': '#dc2626',
            'critical': '#9c0c1a',
        }
        
        color = colors.get(obj.priority, '#6b7280')
        
        return format_html(
            '<span style="background:{};color:#fff;padding:3px 8px;border-radius:3px;font-size:11px;font-weight:600">{}</span>',
            color,
            obj.get_priority_display()
        )
    get_priority_badge.short_description = 'Priority'
    
    def get_read_status(self, obj):
        """Read/unread status indicator."""
        if obj.is_read:
            return format_html(
                '<span style="background:#d1d5db;color:#1f2937;padding:3px 8px;border-radius:3px;font-size:11px;font-weight:600">✓ Read</span>'
            )
        else:
            return format_html(
                '<span style="background:#3b82f6;color:#fff;padding:3px 8px;border-radius:3px;font-size:11px;font-weight:600">● Unread</span>'
            )
    get_read_status.short_description = 'Status'
    
    def get_related_object_link(self, obj):
        """Link to related object if available."""
        if not obj.related_model or not obj.related_object_id:
            return '—'
        
        # Map model names to admin URL patterns
        model_url_map = {
            'Invoice': ('admin:accounts_invoice_change', 'invoice'),
            'Customer': ('admin:accounts_customer_change', 'customer'),
            'Product': ('admin:accounts_product_change', 'product'),
        }
        
        if obj.related_model in model_url_map:
            admin_name, _ = model_url_map[obj.related_model]
            try:
                url = reverse(admin_name, args=[obj.related_object_id])
                return format_html(
                    '<a href="{}">{} #{}</a>',
                    url,
                    obj.related_model,
                    obj.related_object_id[:8]  # Show first 8 chars of UUID
                )
            except:
                pass
        
        return format_html('{} #{}', obj.related_model, obj.related_object_id[:8])
    get_related_object_link.short_description = 'Related Object'
    
    def mark_as_read_action(self, request, queryset):
        """Bulk mark notifications as read."""
        count = sum(1 for obj in queryset if obj.mark_as_read())
        self.message_user(request, f'{count} notification(s) marked as read.')
    mark_as_read_action.short_description = 'Mark selected as read'
    
    def mark_as_unread_action(self, request, queryset):
        """Bulk mark notifications as unread."""
        count = sum(1 for obj in queryset if obj.mark_as_unread())
        self.message_user(request, f'{count} notification(s) marked as unread.')
    mark_as_unread_action.short_description = 'Mark selected as unread'


# ============================================
# ADMIN SITE HEADER
# ============================================

admin.site.site_header = 'iSaral Admin Panel'
admin.site.site_title  = 'iSaral Admin'
admin.site.index_title = 'Dashboard'
