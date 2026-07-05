import logging
from decimal import Decimal
from datetime import timedelta

from django.utils import timezone
from django.db import transaction
from django.conf import settings

from accounts.models import Subscription, RenewalHistory, Notification, Invoice, InvoiceItem, Customer
from accounts.services import NotificationFactory
from accounts.emails import send_mail

logger = logging.getLogger(__name__)


# ── Expiry detection ────────────────────────────────────────────────────

def get_expiry_buckets(user):
    """Return subscriptions grouped by expiry urgency for a user's customers."""
    now   = timezone.now()
    today = now.date()

    all_subs = Subscription.objects.filter(
        user=user, customer__isnull=False
    ).select_related('customer').order_by('expires_at')

    buckets = {
        'expiring_today':    [],
        'expiring_week':     [],
        'expiring_month':    [],
        'expired':           [],
        'grace_period':      [],
        'active':            [],
    }

    for sub in all_subs:
        if not sub.expires_at:
            buckets['active'].append(sub)
            continue

        days = (sub.expires_at.date() - today).days

        if sub.is_in_grace_period:
            buckets['grace_period'].append(sub)
        elif days < 0:
            buckets['expired'].append(sub)
        elif days == 0:
            buckets['expiring_today'].append(sub)
        elif days <= 7:
            buckets['expiring_week'].append(sub)
        elif days <= 30:
            buckets['expiring_month'].append(sub)
        else:
            buckets['active'].append(sub)

    return buckets


def get_renewal_stats(user):
    """Summary stats for the renewal dashboard."""
    from django.db.models import Sum

    now         = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = today_start.replace(day=1)

    subs = Subscription.objects.filter(user=user, customer__isnull=False)
    hist = RenewalHistory.objects.filter(user=user)

    return {
        'total_active':       subs.filter(renewal_status='active').count(),
        'expiring_today':     subs.filter(expires_at__date=now.date()).count(),
        'expiring_week':      subs.filter(expires_at__date__range=[now.date(), (now + timedelta(days=7)).date()]).count(),
        'expired':            subs.filter(renewal_status='expired').count(),
        'renewed_today':      hist.filter(renewed_on__gte=today_start).count(),
        'renewed_this_month': hist.filter(renewed_on__gte=month_start).count(),
        'revenue_this_month': hist.filter(renewed_on__gte=month_start).aggregate(t=Sum('total_amount'))['t'] or Decimal('0'),
        'revenue_all_time':   hist.aggregate(t=Sum('total_amount'))['t'] or Decimal('0'),
    }


# ── Renewal workflow ────────────────────────────────────────────────────

PLAN_PRICES = {
    # plan_name: {billing_cycle: monthly_equivalent_price}
    'free':       {'monthly': 0,    'quarterly': 0,    'half_yearly': 0,    'yearly': 0},
    'starter':    {'monthly': 999,  'quarterly': 2697, 'half_yearly': 4994, 'yearly': 9588},
    'pro':        {'monthly': 2499, 'quarterly': 6747, 'half_yearly': 12494,'yearly': 23988},
    'enterprise': {'monthly': 4999, 'quarterly': 13497,'half_yearly': 24994,'yearly': 47988},
}

GST_RATE = Decimal('18')


def calculate_renewal_amount(plan, billing_cycle, discount=Decimal('0')):
    """Return subtotal, gst, total for a renewal."""
    prices  = PLAN_PRICES.get(plan, {})
    base    = Decimal(str(prices.get(billing_cycle, 0)))
    after_discount = max(Decimal('0'), base - discount)
    gst     = (after_discount * GST_RATE / 100).quantize(Decimal('0.01'))
    total   = (after_discount + gst).quantize(Decimal('0.01'))
    return base, gst, total


def get_new_expiry(current_expiry, billing_cycle):
    """Calculate new expiry date based on billing cycle."""
    from dateutil.relativedelta import relativedelta
    months_map = {'monthly': 1, 'quarterly': 3, 'half_yearly': 6, 'yearly': 12}
    months     = months_map.get(billing_cycle, 1)
    base       = current_expiry if current_expiry and current_expiry > timezone.now() else timezone.now()
    return base + relativedelta(months=months)


def _next_invoice_number(user, prefix):
    """Shared helper for generating a zero-padded, per-user, per-prefix invoice number."""
    last = Invoice.objects.filter(
        user=user, invoice_number__startswith=prefix
    ).order_by('-invoice_number').first()
    try:
        num = int(last.invoice_number.replace(prefix, '')) + 1 if last else 1
    except Exception:
        num = 1
    return f"{prefix}{num:03d}"


@transaction.atomic
def renew_subscription(subscription, renewed_by, billing_cycle=None, plan=None, discount=Decimal('0'), notes=''):
    """
    Perform a full renewal:
    1. Calculate amounts
    2. Create Invoice + InvoiceItem
    3. Update Subscription
    4. Write RenewalHistory
    5. Create Notification
    """
    billing_cycle = billing_cycle or subscription.billing_cycle
    plan          = plan          or subscription.plan

    base, gst, total = calculate_renewal_amount(plan, billing_cycle, discount)
    new_expiry       = get_new_expiry(subscription.expires_at, billing_cycle)

    from datetime import datetime
    year            = datetime.now().year
    invoice_number  = _next_invoice_number(renewed_by, f"RNW-{year}-")

    # ── Create Invoice ────────────────────────────────────────
    invoice = Invoice.objects.create(
        user           = renewed_by,
        customer       = subscription.customer,
        invoice_number = invoice_number,
        issued_date    = timezone.now().date(),
        subtotal       = base - discount,
        gst_rate       = GST_RATE,
        gst_amount     = gst,
        total          = total,
        status         = 'paid',
        notes          = f"Renewal — {plan.title()} plan ({billing_cycle})",
    )

    # ── Create InvoiceItem ────────────────────────────────────
    InvoiceItem.objects.create(
        invoice         = invoice,
        product_name    = f"{plan.title()} Plan ({billing_cycle.replace('_',' ').title()})",
        description     = f"Subscription renewal for {billing_cycle.replace('_',' ')}",
        quantity        = Decimal('1'),
        unit_price      = base - discount,
        gst_rate        = GST_RATE,
        gst_amount      = gst,
        subtotal        = base - discount,
        line_total      = total,
        discount_amount = discount,
    )

    # ── Update Subscription ───────────────────────────────────
    old_expiry                  = subscription.expires_at
    subscription.plan           = plan
    subscription.billing_cycle  = billing_cycle
    subscription.expires_at     = new_expiry
    subscription.renewal_date   = new_expiry
    subscription.renewed_on     = timezone.now()
    subscription.renewed_by     = renewed_by
    subscription.renewal_status = 'active'
    subscription.is_active      = True
    subscription.payment_status = 'paid'
    subscription.amount         = base
    subscription.discount       = discount
    subscription.invoice        = invoice
    subscription.notes          = notes
    subscription.save()

    # ── RenewalHistory ────────────────────────────────────────
    RenewalHistory.objects.create(
        subscription    = subscription,
        user            = renewed_by,
        customer        = subscription.customer,
        plan            = plan,
        billing_cycle   = billing_cycle,
        amount          = base,
        discount        = discount,
        gst_amount      = gst,
        total_amount    = total,
        renewal_type    = 'manual',
        previous_expiry = old_expiry,
        new_expiry      = new_expiry,
        invoice         = invoice,
        payment_status  = 'paid',
        notes           = notes,
    )

    # ── Notification ──────────────────────────────────────────
    Notification.objects.create(
        user    = renewed_by,
        type    = 'system',
        title   = 'Subscription Renewed',
        message = f'{subscription.customer.name if subscription.customer else "User"} — {plan.title()} plan renewed until {new_expiry.strftime("%d %b %Y")}.',
    )

    return subscription, invoice


def sync_renewal_statuses(user):
    """Update renewal_status for all subscriptions based on current date."""
    now  = timezone.now()
    subs = Subscription.objects.filter(user=user, customer__isnull=False)
    for sub in subs:
        if not sub.expires_at:
            continue
        days = (sub.expires_at - now).days
        if days > 0:
            sub.renewal_status = 'active'
        elif sub.is_in_grace_period:
            sub.renewal_status = 'grace'
        else:
            sub.renewal_status = 'expired'
            sub.is_active = False
    Subscription.objects.bulk_update(subs, ['renewal_status', 'is_active'])


def create_expiry_notifications(user):
    """Create notifications for subscriptions expiring in 30/15/7/1 days."""
    now  = timezone.now()
    subs = Subscription.objects.filter(
        user=user, customer__isnull=False, renewal_status='active'
    ).select_related('customer')

    milestones = [30, 15, 7, 1]
    created    = 0

    for sub in subs:
        if not sub.expires_at:
            continue
        days = (sub.expires_at.date() - now.date()).days
        if days in milestones:
            title = f'Plan Expiring in {days} Day{"s" if days > 1 else ""}'
            msg   = f'{sub.customer.name if sub.customer else sub.user.email} — {sub.plan.title()} expires on {sub.expires_at.strftime("%d %b %Y")}.'
            exists = Notification.objects.filter(user=user, title=title, message=msg).exists()
            if not exists:
                Notification.objects.create(user=user, type='plan_expiry', title=title, message=msg)
                created += 1

    return created


# ── RenewalService: invoice generation + reminders for automated renewals ──

class RenewalService:
    """
    Service for creating renewal invoices and sending reminder emails
    for automated/scheduled renewals (distinct from the manual
    `renew_subscription` workflow above).

    NOTE: field names below (Invoice/InvoiceItem) are aligned with the
    schema confirmed elsewhere in this codebase (renew_subscription,
    accounts/tasks.py). The `Renewal` model referenced in
    `send_renewal_reminders` has NOT been confirmed — verify its fields
    (`status`, `renewal_date`, `reminder_7_days_sent`, `subscription`,
    `invoice`, `invoice_created`, `processed_at`) against
    renewals/models.py before relying on this method.
    """

    @staticmethod
    @transaction.atomic
    def create_renewal_invoice(renewal):
        """Create an Invoice + InvoiceItem from a Renewal record."""
        subscription = renewal.subscription

        try:
            base  = Decimal(str(subscription.amount))
            gst   = (base * GST_RATE / 100).quantize(Decimal('0.01'))
            total = (base + gst).quantize(Decimal('0.01'))

            invoice_number = _next_invoice_number(subscription.user, "REN-")

            invoice = Invoice.objects.create(
                user           = subscription.user,
                customer       = subscription.customer,
                invoice_number = invoice_number,
                issued_date    = timezone.now().date(),
                due_date       = timezone.now().date() + timedelta(days=7),
                subtotal       = base,
                gst_rate       = GST_RATE,
                gst_amount     = gst,
                total          = total,
                status         = 'sent',
                notes          = f"Renewal for period {renewal.renewal_date}",
            )

            InvoiceItem.objects.create(
                invoice     = invoice,
                product_name= f"{subscription.plan.title()} Renewal",
                description = f"Renewal for period {renewal.renewal_date}",
                quantity    = Decimal('1'),
                unit_price  = base,
                gst_rate    = GST_RATE,
                gst_amount  = gst,
                subtotal    = base,
                line_total  = total,
            )

            renewal.invoice         = invoice
            renewal.invoice_created = True
            renewal.status          = 'invoice_created'
            renewal.processed_at    = timezone.now()
            renewal.save(update_fields=['invoice', 'invoice_created', 'status', 'processed_at'])

            NotificationFactory.renewal_invoice_created(
                subscription.user,
                renewal,
                async_task=True,
            )

            RenewalService.send_renewal_invoice_email(invoice, subscription)

            return invoice

        except Exception as e:
            logger.error(f"Error creating renewal invoice for renewal {renewal.id}: {e}")
            renewal.status = 'failed'
            renewal.save(update_fields=['status'])
            return None

    @staticmethod
    def send_renewal_invoice_email(invoice, subscription):
        """Send renewal invoice email."""
        subject = f"Renewal Invoice - {invoice.invoice_number}"

        html_message = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6;">
                <div style="max-width: 600px; margin: 0 auto; border: 1px solid #ddd; padding: 20px;">
                    <h2 style="color: #5cb85c;">Subscription Renewal</h2>
                    <p>Dear {subscription.customer.name},</p>
                    <p>Your subscription renewal invoice is ready.</p>
                    <div style="background-color: #f5f5f5; padding: 15px; margin: 20px 0;">
                        <p><strong>Plan:</strong> {subscription.plan}</p>
                        <p><strong>Amount:</strong> ₹{invoice.total:,.2f}</p>
                        <p><strong>Due Date:</strong> {invoice.due_date}</p>
                    </div>
                    <p>
                        <a href="http://localhost:8000/accounts/invoices/{invoice.id}/"
                           style="background-color: #5cb85c; color: white; padding: 10px 20px;
                                  text-decoration: none; border-radius: 4px;">
                            View Invoice
                        </a>
                    </p>
                    <p>Thank you for your continued business!</p>
                </div>
            </body>
        </html>
        """

        try:
            send_mail(
                subject=subject,
                message=f"Your renewal invoice {invoice.invoice_number} is ready",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[subscription.customer.email],
                html_message=html_message,
                fail_silently=False,
            )
        except Exception as e:
            logger.error(f"Error sending renewal email for invoice {invoice.invoice_number}: {e}")

    @staticmethod
    def send_renewal_reminders():
        """
        Send renewal reminders.
        UNCONFIRMED: relies on renewals.models.Renewal with fields
        status, renewal_date, reminder_7_days_sent, subscription.
        Verify this model exists with these fields before relying on this.
        """
        from renewals.models import Renewal

        today = timezone.now().date()

        renewals_7_days = Renewal.objects.filter(
            status='pending',
            renewal_date__lte=today + timedelta(days=7),
            renewal_date__gte=today,
            reminder_7_days_sent=False,
        ).select_related('subscription', 'subscription__customer')

        sent_count = 0
        for renewal in renewals_7_days:
            subscription = renewal.subscription
            subject = f"Subscription Renewal Reminder - {subscription.plan}"

            html_message = f"""
            <html>
                <body style="font-family: Arial, sans-serif;">
                    <p>Your subscription renewal is coming up in 7 days!</p>
                    <p>Plan: {subscription.plan}</p>
                    <p>Renewal Date: {renewal.renewal_date}</p>
                </body>
            </html>
            """

            try:
                send_mail(
                    subject=subject,
                    message="Your subscription renewal reminder",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[subscription.customer.email],
                    html_message=html_message,
                    fail_silently=False,
                )
                renewal.reminder_7_days_sent = True
                renewal.save(update_fields=['reminder_7_days_sent'])
                sent_count += 1
            except Exception as e:
                logger.error(f"Error sending renewal reminder for renewal {renewal.id}: {e}")

        return {'sent': sent_count}