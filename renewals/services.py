"""
renewals/services.py
--------------------
All business logic for subscription renewals.
"""

from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from accounts.models import Subscription, RenewalHistory, Notification, Invoice, InvoiceItem, Customer


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
    from django.db.models import Sum, Count
    from datetime import timedelta

    now         = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start  = today_start - timedelta(days=7)
    month_start = today_start.replace(day=1)

    subs = Subscription.objects.filter(user=user, customer__isnull=False)
    hist = RenewalHistory.objects.filter(user=user)

    return {
        'total_active':      subs.filter(renewal_status='active').count(),
        'expiring_today':    subs.filter(expires_at__date=now.date()).count(),
        'expiring_week':     subs.filter(expires_at__date__range=[now.date(), (now + timedelta(days=7)).date()]).count(),
        'expired':           subs.filter(renewal_status='expired').count(),
        'renewed_today':     hist.filter(renewed_on__gte=today_start).count(),
        'renewed_this_month':hist.filter(renewed_on__gte=month_start).count(),
        'revenue_this_month':hist.filter(renewed_on__gte=month_start).aggregate(t=Sum('total_amount'))['t'] or Decimal('0'),
        'revenue_all_time':  hist.aggregate(t=Sum('total_amount'))['t'] or Decimal('0'),
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

    # ── Build invoice number ──────────────────────────────────
    from datetime import datetime
    year   = datetime.now().year
    prefix = f"RNW-{year}-"
    last   = Invoice.objects.filter(
        user=renewed_by, invoice_number__startswith=prefix
    ).order_by('-invoice_number').first()
    try:
        num = int(last.invoice_number.replace(prefix, '')) + 1 if last else 1
    except Exception:
        num = 1
    invoice_number = f"{prefix}{num:03d}"

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
        invoice      = invoice,
        product_name = f"{plan.title()} Plan ({billing_cycle.replace('_',' ').title()})",
        description  = f"Subscription renewal for {billing_cycle.replace('_',' ')}",
        quantity     = Decimal('1'),
        unit_price   = base - discount,
        gst_rate     = GST_RATE,
        gst_amount   = gst,
        subtotal     = base - discount,
        line_total   = total,
        discount_amount = discount,
    )

    # ── Update Subscription ───────────────────────────────────
    old_expiry                = subscription.expires_at
    subscription.plan         = plan
    subscription.billing_cycle= billing_cycle
    subscription.expires_at   = new_expiry
    subscription.renewal_date = new_expiry
    subscription.renewed_on   = timezone.now()
    subscription.renewed_by   = renewed_by
    subscription.renewal_status = 'active'
    subscription.is_active    = True
    subscription.payment_status = 'paid'
    subscription.amount       = base
    subscription.discount     = discount
    subscription.invoice      = invoice
    subscription.notes        = notes
    subscription.save()

    # ── RenewalHistory ────────────────────────────────────────
    RenewalHistory.objects.create(
        subscription   = subscription,
        user           = renewed_by,
        customer       = subscription.customer,
        plan           = plan,
        billing_cycle  = billing_cycle,
        amount         = base,
        discount       = discount,
        gst_amount     = gst,
        total_amount   = total,
        renewal_type   = 'manual',
        previous_expiry= old_expiry,
        new_expiry     = new_expiry,
        invoice        = invoice,
        payment_status = 'paid',
        notes          = notes,
    )

    # ── Notification ──────────────────────────────────────────
    Notification.objects.create(
        user    = renewed_by,
        type    = 'system',
        title   = f'Subscription Renewed',
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
    from django.db.models import Q
    from datetime import timedelta

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
            # Avoid duplicate notifications for same sub+days
            exists = Notification.objects.filter(user=user, title=title, message=msg).exists()
            if not exists:
                Notification.objects.create(user=user, type='plan_expiry', title=title, message=msg)
                created += 1

    return created