"""renewals/views.py"""

from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q

from accounts.models import Subscription, RenewalHistory, Customer
from renewals.services import (
    get_expiry_buckets, get_renewal_stats, calculate_renewal_amount,
    renew_subscription, sync_renewal_statuses, create_expiry_notifications,
    PLAN_PRICES,
)


@login_required
def renewal_dashboard(request):
    """Main renewal dashboard with stats and expiry buckets."""
    sync_renewal_statuses(request.user)
    stats   = get_renewal_stats(request.user)
    buckets = get_expiry_buckets(request.user)

    # Recent renewals
    recent = RenewalHistory.objects.filter(
        user=request.user
    ).select_related('customer').order_by('-renewed_on')[:10]

    context = {
        'page_title': 'Renewal Dashboard',
        'stats':      stats,
        'buckets':    buckets,
        'recent':     recent,
    }
    return render(request, 'renewals/dashboard.html', context)


@login_required
def renewal_list(request):
    """Paginated, filtered list of all subscriptions."""
    sync_renewal_statuses(request.user)

    qs = Subscription.objects.filter(
        user=request.user, customer__isnull=False
    ).select_related('customer').order_by('expires_at')

    # Filters
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(customer__name__icontains=q) |
            Q(customer__email__icontains=q) |
            Q(plan__icontains=q)
        )

    status = request.GET.get('status', '')
    if status:
        qs = qs.filter(renewal_status=status)

    plan = request.GET.get('plan', '')
    if plan:
        qs = qs.filter(plan=plan)

    paginator = Paginator(qs, 20)
    page_obj  = paginator.get_page(request.GET.get('page'))

    context = {
        'page_title': 'Subscriptions & Renewals',
        'page_obj':   page_obj,
        'q':          q,
        'status':     status,
        'plan':       plan,
        'plan_choices': ['free', 'starter', 'pro', 'enterprise'],
        'status_choices': ['active', 'expired', 'grace', 'upcoming', 'cancelled'],
    }
    return render(request, 'renewals/list.html', context)


@login_required
def renew_view(request, sub_id):
    """Show renewal form and process renewal."""
    sub = get_object_or_404(Subscription, pk=sub_id, user=request.user)

    if request.method == 'POST':
        plan          = request.POST.get('plan', sub.plan)
        billing_cycle = request.POST.get('billing_cycle', sub.billing_cycle)
        discount      = Decimal(request.POST.get('discount', '0') or '0')
        notes         = request.POST.get('notes', '')

        try:
            subscription, invoice = renew_subscription(
                subscription  = sub,
                renewed_by    = request.user,
                billing_cycle = billing_cycle,
                plan          = plan,
                discount      = discount,
                notes         = notes,
            )
            messages.success(request, f'Subscription renewed successfully until {subscription.expires_at.strftime("%d %b %Y")}. Invoice #{invoice.invoice_number} generated.')
            return redirect('renewals:list')
        except Exception as e:
            messages.error(request, f'Renewal failed: {str(e)}')

    # GET — show form with preview
    plan          = request.GET.get('plan', sub.plan)
    billing_cycle = request.GET.get('billing_cycle', sub.billing_cycle or 'monthly')
    discount      = Decimal(request.GET.get('discount', '0') or '0')
    base, gst, total = calculate_renewal_amount(plan, billing_cycle, discount)

    context = {
        'page_title':   f'Renew — {sub.customer.name if sub.customer else sub.user.email}',
        'sub':          sub,
        'plan':         plan,
        'billing_cycle':billing_cycle,
        'discount':     discount,
        'base':         base,
        'gst':          gst,
        'total':        total,
        'plan_choices': list(PLAN_PRICES.keys()),
        'cycle_choices':[('monthly','Monthly'),('quarterly','Quarterly'),('half_yearly','Half-Yearly'),('yearly','Yearly')],
        'prices_json':  {p: list(v.values()) for p, v in PLAN_PRICES.items()},
    }
    return render(request, 'renewals/renew_form.html', context)


@login_required
def renewal_history(request, sub_id):
    """Renewal history for a single subscription."""
    sub     = get_object_or_404(Subscription, pk=sub_id, user=request.user)
    history = RenewalHistory.objects.filter(subscription=sub).order_by('-renewed_on')
    context = {
        'page_title': f'Renewal History — {sub.customer.name if sub.customer else sub.user.email}',
        'sub':        sub,
        'history':    history,
    }
    return render(request, 'renewals/history.html', context)


@login_required
def renewal_reports(request):
    """Renewal reports."""
    from django.db.models import Sum, Count
    from datetime import timedelta

    now         = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    hist = RenewalHistory.objects.filter(user=request.user)

    monthly = (
        hist.filter(renewed_on__gte=now - timedelta(days=365))
        .extra(select={'month': "date_trunc('month', renewed_on)"})
        .values('month')
        .annotate(count=Count('id'), revenue=Sum('total_amount'))
        .order_by('month')
    )

    plan_wise = (
        hist.values('plan')
        .annotate(count=Count('id'), revenue=Sum('total_amount'))
        .order_by('-revenue')
    )

    customer_wise = (
        hist.filter(customer__isnull=False)
        .values('customer__name')
        .annotate(count=Count('id'), revenue=Sum('total_amount'))
        .order_by('-revenue')[:10]
    )

    context = {
        'page_title':    'Renewal Reports',
        'monthly':       list(monthly),
        'plan_wise':     list(plan_wise),
        'customer_wise': list(customer_wise),
        'total_revenue': hist.aggregate(t=Sum('total_amount'))['t'] or Decimal('0'),
        'total_renewals':hist.count(),
    }
    return render(request, 'renewals/reports.html', context)


@login_required
def preview_amount_api(request):
    """JSON API to preview renewal amount."""
    plan          = request.GET.get('plan', 'starter')
    billing_cycle = request.GET.get('billing_cycle', 'monthly')
    discount      = Decimal(request.GET.get('discount', '0') or '0')
    base, gst, total = calculate_renewal_amount(plan, billing_cycle, discount)
    return JsonResponse({'base': str(base), 'gst': str(gst), 'total': str(total)})


@login_required
def send_expiry_notifications_view(request):
    """Manually trigger expiry notifications."""
    if request.method == 'POST':
        count = create_expiry_notifications(request.user)
        messages.success(request, f'{count} expiry notification(s) created.')
    return redirect('renewals:dashboard')