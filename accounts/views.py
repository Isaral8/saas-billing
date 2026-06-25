import json
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.core.paginator import Paginator

from decimal import Decimal
from accounts.models import Invoice, Customer, SupportTicket, CustomUser
from accounts.forms import InvoiceForm, SupportTicketForm

from django.db.models.functions import TruncMonth
import uuid
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from django.http import HttpResponse
from django.urls import reverse

from django.db.models import Sum, Count, Avg, Q
from datetime import datetime, timedelta
from django.views.decorators.http import require_http_methods
from accounts.emails import (
    send_welcome_email, send_invoice_email, send_payment_confirmation_email,
    send_ticket_confirmation_email, send_ticket_update_email
)

# ============================================
# HOME & AUTHENTICATION VIEWS
# ============================================
def get_next_invoice_number(user):
    from datetime import datetime
    year = datetime.now().year
    prefix = f"INV-{year}-"
    last_invoice = Invoice.objects.filter(
        user=user, invoice_number__startswith=prefix
    ).order_by('-invoice_number').first()

    if last_invoice:
        try:
            last_num = int(last_invoice.invoice_number.replace(prefix, ''))
            next_num = last_num + 1
        except ValueError:
            next_num = 1
    else:
        next_num = 1

    return f"{prefix}{next_num:03d}"

def home_view(request):
    context = {'page_title': 'Home'}
    if request.user.is_authenticated:
        context['user_name'] = request.user.email
    return render(request, 'accounts/home.html', context)


def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()

        if not email or not password:
            messages.error(request, 'Email and password are required.')
            return render(request, 'accounts/login.html')

        user = authenticate(request, username=email, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, 'Welcome back!')
            return redirect('accounts:dashboard')

        messages.error(request, 'Invalid email or password.')

    return render(request, 'accounts/login.html')


def signup_view(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        password_confirm = request.POST.get('password_confirm', '').strip()
        company_name = request.POST.get('company_name', '').strip()

        if not all([email, password, password_confirm, company_name]):
            messages.error(request, 'All fields are required.')
            return render(request, 'accounts/signup.html')
        if password != password_confirm:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'accounts/signup.html')
        if len(password) < 8:
            messages.error(request, 'Password must be at least 8 characters.')
            return render(request, 'accounts/signup.html')
        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, 'This email is already registered.')
            return render(request, 'accounts/signup.html')

        try:
            user = CustomUser.objects.create_user(email=email, password=password, company_name=company_name)
            first_name = request.POST.get('first_name', '').strip()
            phone = request.POST.get('phone', '').strip()
            if first_name:
                user.first_name = first_name
            if phone:
                user.phone = phone
            user.save()
            send_welcome_email(user)
            messages.success(request, 'Account created! Please log in.')
            return redirect('accounts:login')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')

    return render(request, 'accounts/signup.html')


def logout_view(request):
    if request.method == 'POST':
        logout(request)
        messages.success(request, 'Logged out successfully.')
        return redirect('accounts:login')
    return render(request, 'accounts/logout.html')


# ============================================
# DASHBOARD VIEW
# ============================================

@login_required(login_url='accounts:login')
def dashboard_view(request):
    user = request.user
    today = timezone.now()

    start_of_this_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start_of_this_month.month == 1:
        start_of_last_month = start_of_this_month.replace(year=start_of_this_month.year - 1, month=12)
    else:
        start_of_last_month = start_of_this_month.replace(month=start_of_this_month.month - 1)
    end_of_last_month = start_of_this_month - timedelta(microseconds=1)
    twelve_months_ago = today - timedelta(days=365)

    invoices  = Invoice.objects.filter(user=user)
    customers = Customer.objects.filter(user=user)
    tickets   = SupportTicket.objects.filter(user=user)

    total_revenue  = invoices.aggregate(Sum('total'))['total__sum'] or Decimal('0.00')
    total_paid     = invoices.filter(status='paid').aggregate(Sum('total'))['total__sum'] or Decimal('0.00')
    gst_collected  = invoices.aggregate(Sum('gst_amount'))['gst_amount__sum'] or Decimal('0.00')

    total_invoices   = invoices.count()
    paid_invoices    = invoices.filter(status='paid').count()
    pending_invoices = invoices.filter(status__in=['issued', 'draft', 'pending']).count()
    overdue_invoices = invoices.filter(status='overdue').count()

    pending_amount = invoices.filter(status__in=['issued', 'draft', 'pending']).aggregate(s=Sum('total'))['s'] or Decimal('0.00')
    overdue_amount = invoices.filter(status='overdue').aggregate(s=Sum('total'))['s'] or Decimal('0.00')

    total_customers    = customers.count()
    active_customers   = customers.filter(is_active=True).count()
    inactive_customers = customers.filter(is_active=False).count()

    open_tickets        = tickets.filter(status='open').count()
    in_progress_tickets = tickets.filter(status='in_progress').count()
    resolved_tickets    = tickets.filter(status='resolved').count()
    closed_tickets      = tickets.filter(status='closed').count()
    total_tickets       = tickets.count()

    this_month_revenue = invoices.filter(issued_date__gte=start_of_this_month, issued_date__lte=today).aggregate(Sum('total'))['total__sum'] or Decimal('0.00')
    last_month_revenue = invoices.filter(issued_date__gte=start_of_last_month, issued_date__lte=end_of_last_month).aggregate(Sum('total'))['total__sum'] or Decimal('0.00')

    if last_month_revenue > 0:
        revenue_growth_pct = ((this_month_revenue - last_month_revenue) / last_month_revenue) * 100
        revenue_growth = f"{'+' if revenue_growth_pct >= 0 else ''}{revenue_growth_pct:.1f}%"
        revenue_growth_color = "green" if revenue_growth_pct >= 0 else "red"
    else:
        revenue_growth = "+100.0%" if this_month_revenue > 0 else "0.0%"
        revenue_growth_color = "green" if this_month_revenue > 0 else "gray"

    last_month_customers = customers.filter(created_at__gte=start_of_last_month, created_at__lte=end_of_last_month).count()
    this_month_customers = customers.filter(created_at__gte=start_of_this_month, created_at__lte=today).count()

    if last_month_customers > 0:
        customer_growth_pct = (this_month_customers / last_month_customers) * 100
        customer_growth = f"{customer_growth_pct:.1f}%"
    else:
        customer_growth = "100.0%" if this_month_customers > 0 else "0.0%"

    monthly_revenue_data = (
        invoices.filter(issued_date__gte=twelve_months_ago)
        .annotate(month=TruncMonth('issued_date'))
        .values('month').annotate(total=Sum('total')).order_by('month')
    )
    monthly_revenue_labels = [m['month'].strftime('%b %Y') if m['month'] else 'N/A' for m in monthly_revenue_data]
    monthly_revenue_values = [float(m['total'] or 0) for m in monthly_revenue_data]

    monthly_customers_data = (
        customers.filter(created_at__gte=twelve_months_ago)
        .annotate(month=TruncMonth('created_at'))
        .values('month').annotate(count=Count('id')).order_by('month')
    )
    monthly_customers_labels = [m['month'].strftime('%b %Y') if m['month'] else 'N/A' for m in monthly_customers_data]
    monthly_customers_values = [m['count'] for m in monthly_customers_data]

    invoice_status_counts = {
        'paid':    invoices.filter(status='paid').count(),
        'pending': invoices.filter(status__in=['issued', 'pending']).count(),
        'overdue': overdue_invoices,
        'draft':   invoices.filter(status='draft').count(),
    }
    ticket_status_counts = {
        'open': open_tickets, 'in_progress': in_progress_tickets,
        'resolved': resolved_tickets, 'closed': closed_tickets,
    }

    recent_customers = customers.order_by('-created_at')[:10]
    recent_invoices  = invoices.order_by('-issued_date')[:10]
    recent_tickets   = tickets.order_by('-created_at')[:10]

    from django.db.models import Sum as DjangoSum
    top_customers_data = customers.annotate(
        total_revenue=DjangoSum('invoice__total', filter=Q(invoice__user=user, invoice__status='paid'))
    ).filter(total_revenue__gt=0).order_by('-total_revenue')[:10]

    context = {
        'page_title': 'Dashboard',
        'total_revenue': f"{float(total_revenue):.2f}",
        'total_paid': f"{float(total_paid):.2f}",
        'gst_collected': f"{float(gst_collected):.2f}",
        'total_invoices': total_invoices,
        'paid_invoices': paid_invoices,
        'pending_invoices': pending_invoices,
        'overdue_invoices': overdue_invoices,
        'pending_amount': f"{float(pending_amount):.2f}",
        'overdue_amount': f"{float(overdue_amount):.2f}",
        'total_customers': total_customers,
        'active_customers': active_customers,
        'inactive_customers': inactive_customers,
        'total_tickets': total_tickets,
        'open_tickets': open_tickets,
        'in_progress_tickets': in_progress_tickets,
        'resolved_tickets': resolved_tickets,
        'closed_tickets': closed_tickets,
        'revenue_growth': revenue_growth,
        'revenue_growth_color': revenue_growth_color,
        'customer_growth': customer_growth,
        'this_month_revenue': f"{float(this_month_revenue):.2f}",
        'this_month_customers': this_month_customers,
        'monthly_revenue_labels': json.dumps(monthly_revenue_labels),
        'monthly_revenue_values': json.dumps(monthly_revenue_values),
        'monthly_customers_labels': json.dumps(monthly_customers_labels),
        'monthly_customers_values': json.dumps(monthly_customers_values),
        'invoice_status_counts': invoice_status_counts,
        'ticket_status_counts': ticket_status_counts,
        'recent_customers': recent_customers,
        'recent_invoices': recent_invoices,
        'recent_tickets': recent_tickets,
        'top_customers': top_customers_data,
    }
    return render(request, 'accounts/dashboard.html', context)


# ============================================
# INVOICE VIEWS
# ============================================

@login_required(login_url='accounts:login')
def create_invoice(request):
    if request.method == 'POST':
        post_data = request.POST.copy()
        try:
            subtotal   = Decimal(post_data.get('subtotal') or '0')
            gst_rate   = Decimal(post_data.get('gst_rate') or '18')
            gst_amount = round(subtotal * gst_rate / 100, 2)
            total      = round(subtotal + gst_amount, 2)

            business_state = (request.user.business_state or '').strip().lower()
            customer_id    = post_data.get('customer')
            customer_state = ''
            if customer_id:
                try:
                    c = Customer.objects.get(id=customer_id, user=request.user)
                    customer_state = (c.state or '').strip().lower()
                except Exception:
                    pass

            if business_state and customer_state and business_state == customer_state:
                cgst = round(gst_amount / 2, 2)
                sgst = round(gst_amount / 2, 2)
                igst = Decimal('0')
            else:
                cgst = Decimal('0')
                sgst = Decimal('0')
                igst = gst_amount

            post_data['gst_amount']  = str(gst_amount)
            post_data['cgst_amount'] = str(cgst)
            post_data['sgst_amount'] = str(sgst)
            post_data['igst_amount'] = str(igst)
            post_data['total']       = str(total)
        except Exception as e:
            messages.error(request, f'Calculation error: {str(e)}')

        form = InvoiceForm(post_data, user=request.user)
        if form.is_valid():
            try:
                invoice = form.save(commit=False)
                invoice.user = request.user
                invoice.save()
                send_invoice_email(invoice)
                messages.success(request, f'Invoice #{invoice.invoice_number} created successfully!')
                return redirect('accounts:invoices')
            except Exception as e:
                messages.error(request, f'Error: {str(e)}')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = InvoiceForm(user=request.user, initial={'invoice_number': get_next_invoice_number(request.user)})

    context = {
        'form': form,
        'customers': Customer.objects.filter(user=request.user),
        'page_title': 'Create Invoice',
    }
    return render(request, 'accounts/create_invoice.html', context)


@login_required(login_url='accounts:login')
def invoices_list(request):
    all_invoices = Invoice.objects.filter(user=request.user)

    status = request.GET.get('status')
    filtered = all_invoices
    if status in ['draft', 'issued', 'paid', 'overdue', 'pending']:
        filtered = all_invoices.filter(status=status)

    def safe_sum(qs, field):
        result = qs.aggregate(s=Sum(field))['s']
        return Decimal(str(result)) if result else Decimal('0.00')

    total_amount  = safe_sum(all_invoices, 'subtotal') or safe_sum(all_invoices, 'total')
    paid_amount   = safe_sum(all_invoices.filter(status='paid'), 'subtotal') or safe_sum(all_invoices.filter(status='paid'), 'total')
    pending_amount = safe_sum(all_invoices.filter(status__in=['issued', 'pending', 'draft']), 'subtotal') or safe_sum(all_invoices.filter(status__in=['issued', 'pending', 'draft']), 'total')

    context = {
        'invoices': filtered,
        'selected_status': status or 'all',
        'page_title': 'Invoices',
        'total_invoices_count': all_invoices.count(),
        'total_amount': f"{float(total_amount):.2f}",
        'paid_amount': f"{float(paid_amount):.2f}",
        'pending_amount': f"{float(pending_amount):.2f}",
    }
    return render(request, 'accounts/invoices.html', context)


@login_required(login_url='accounts:login')
def update_invoice(request, invoice_id):
    try:
        invoice = Invoice.objects.get(id=invoice_id, user=request.user)
    except Invoice.DoesNotExist:
        messages.error(request, 'Invoice not found.')
        return redirect('accounts:invoices')

    if request.method == 'POST':
        if invoice.status == 'paid':
            messages.error(request, 'Cannot update a paid invoice.')
            return redirect('accounts:invoices')

        previous_status = invoice.status
        post_data = request.POST.copy()
        try:
            subtotal   = Decimal(post_data.get('subtotal') or '0')
            gst_rate   = Decimal(post_data.get('gst_rate') or '18')
            gst_amount = round(subtotal * gst_rate / 100, 2)
            total      = round(subtotal + gst_amount, 2)

            business_state = (request.user.business_state or '').strip().lower()
            customer_state = (invoice.customer.state or '').strip().lower() if invoice.customer else ''

            if business_state and customer_state and business_state == customer_state:
                cgst = round(gst_amount / 2, 2)
                sgst = round(gst_amount / 2, 2)
                igst = Decimal('0')
            else:
                cgst = Decimal('0')
                sgst = Decimal('0')
                igst = gst_amount

            post_data['gst_amount']  = str(gst_amount)
            post_data['cgst_amount'] = str(cgst)
            post_data['sgst_amount'] = str(sgst)
            post_data['igst_amount'] = str(igst)
            post_data['total']       = str(total)
        except Exception:
            pass

        form = InvoiceForm(post_data, instance=invoice, user=request.user)
        if form.is_valid():
            try:
                invoice = form.save(commit=False)
                invoice.user = request.user
                invoice.updated_at = timezone.now()
                invoice.save()
                if invoice.status == 'paid' and previous_status != 'paid':
                    send_payment_confirmation_email(invoice)
                messages.success(request, f'Invoice #{invoice.invoice_number} updated successfully!')
                return redirect('accounts:invoices')
            except Exception as e:
                messages.error(request, f'Error: {str(e)}')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = InvoiceForm(instance=invoice, user=request.user)

    context = {
        'form': form,
        'customers': Customer.objects.filter(user=request.user),
        'invoice': invoice,
        'page_title': f'Edit Invoice #{invoice.invoice_number}',
    }
    return render(request, 'accounts/update_invoice.html', context)


@login_required(login_url='accounts:login')
def delete_invoice(request, invoice_id):
    if request.method == 'POST':
        try:
            invoice = Invoice.objects.get(id=invoice_id, user=request.user)
            if invoice.status != 'draft':
                messages.error(request, f'Cannot delete {invoice.status} invoices. Only draft invoices can be deleted.')
                return redirect('accounts:invoices')
            invoice_number = invoice.invoice_number
            invoice.delete()
            messages.success(request, f'Invoice #{invoice_number} deleted successfully!')
        except Invoice.DoesNotExist:
            messages.error(request, 'Invoice not found.')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    return redirect('accounts:invoices')


@login_required(login_url='accounts:login')
def email_invoice(request, invoice_id):
    try:
        invoice = Invoice.objects.get(id=invoice_id, user=request.user)
    except Invoice.DoesNotExist:
        messages.error(request, 'Invoice not found.')
        return redirect('accounts:invoices')

    if not invoice.customer or not invoice.customer.email:
        messages.error(request, 'Customer has no email address. Please update customer details.')
        return redirect('accounts:invoices')

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
        import io

        buffer = io.BytesIO()
        LEFT_MARGIN = RIGHT_MARGIN = 15 * mm
        TOP_MARGIN = BOT_MARGIN = 12 * mm
        USABLE = A4[0] - LEFT_MARGIN - RIGHT_MARGIN

        doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=LEFT_MARGIN, rightMargin=RIGHT_MARGIN, topMargin=TOP_MARGIN, bottomMargin=BOT_MARGIN)

        BRAND = colors.HexColor('#0D1B4B')
        GOLD  = colors.HexColor('#F4A61D')
        GREEN = colors.HexColor('#0F9D58')
        RED   = colors.HexColor('#E53935')
        GRAY  = colors.HexColor('#6B7280')
        LGRAY = colors.HexColor('#F3F4F6')
        BLACK = colors.HexColor('#111827')
        WHITE = colors.white

        status_color = {'paid': GREEN, 'pending': GOLD, 'issued': GOLD, 'overdue': RED, 'draft': GRAY}.get(invoice.status, GRAY)
        BASE = getSampleStyleSheet()['Normal']

        def S(name, size=9, color=BLACK, font='Helvetica', align=TA_LEFT, leading=None):
            return ParagraphStyle(name, parent=BASE, fontSize=size, textColor=color, fontName=font, alignment=align, leading=leading or size+4)

        user     = request.user
        customer = invoice.customer
        company_name    = user.company_name or 'iSaral Business Solutions'
        company_address = user.business_address or 'Bangalore, Karnataka'
        company_gstin   = user.gstin or ''
        company_phone   = user.phone or ''
        company_email   = user.email or ''

        cname  = customer.name or 'N/A'
        cco    = customer.company or ''
        cemail = customer.email or ''
        cphone = customer.phone or ''
        caddr  = customer.address or ''
        cstate = customer.state or ''
        cgstin = customer.gstin or ''

        issued_str = invoice.issued_date.strftime('%d %b %Y')
        due_str    = invoice.due_date.strftime('%d %b %Y') if invoice.due_date else 'N/A'
        hsn        = invoice.hsn_sac_code or '-'

        subtotal   = Decimal(str(invoice.subtotal or 0))
        gst_rate   = Decimal(str(invoice.gst_rate or 0))
        gst_amount = Decimal(str(invoice.gst_amount or 0))
        cgst       = Decimal(str(invoice.cgst_amount or 0))
        sgst       = Decimal(str(invoice.sgst_amount or 0))
        igst       = Decimal(str(invoice.igst_amount or 0))
        total      = Decimal(str(invoice.total or 0))
        half_gst   = gst_rate / Decimal('2')

        story = []
        L = USABLE * 0.55
        R = USABLE * 0.45

        left_lines = [Paragraph('iSaral', S('h1', 18, WHITE, 'Helvetica-Bold', leading=22)), Spacer(1, 3), Paragraph(company_name, S('h2', 10, WHITE, 'Helvetica-Bold', leading=14)), Paragraph(company_address, S('h3', 8, WHITE, leading=12))]
        if company_gstin: left_lines.append(Paragraph(f'GSTIN: {company_gstin}', S('h4', 8, WHITE, leading=12)))
        if company_phone: left_lines.append(Paragraph(f'Ph: {company_phone}', S('h5', 8, WHITE, leading=12)))
        left_lines.append(Paragraph(f'Email: {company_email}', S('h6', 8, WHITE, leading=12)))

        right_lines = [Paragraph('TAX INVOICE', S('ti', 13, GOLD, 'Helvetica-Bold', TA_RIGHT)), Spacer(1, 4), Paragraph(f'# {invoice.invoice_number}', S('in', 11, WHITE, 'Helvetica-Bold', TA_RIGHT)), Spacer(1, 6), Paragraph(f'Date: {issued_str}', S('d1', 9, WHITE, align=TA_RIGHT)), Paragraph(f'Due:  {due_str}', S('d2', 9, WHITE, align=TA_RIGHT)), Spacer(1, 6), Paragraph(invoice.status.upper(), S('st', 8, WHITE, 'Helvetica-Bold', TA_RIGHT))]

        header = Table([[left_lines, right_lines]], colWidths=[L, R], style=TableStyle([('BACKGROUND', (0,0), (-1,-1), BRAND), ('VALIGN', (0,0), (-1,-1), 'TOP'), ('LEFTPADDING', (0,0), (-1,-1), 10), ('RIGHTPADDING', (0,0), (-1,-1), 10), ('TOPPADDING', (0,0), (-1,-1), 12), ('BOTTOMPADDING', (0,0), (-1,-1), 14)]))
        story.append(header)
        story.append(Spacer(1, 6*mm))

        BL = BR = USABLE * 0.50 - 3*mm
        GAP = 6*mm

        bill_rows = [[Paragraph('BILL TO', S('bt', 8, BRAND, 'Helvetica-Bold'))], [Paragraph(cname, S('bn', 10, BLACK, 'Helvetica-Bold'))]]
        for txt in [cco, cemail, cphone, caddr, (f'State: {cstate}' if cstate else ''), (f'GSTIN: {cgstin}' if cgstin else '')]:
            if txt: bill_rows.append([Paragraph(txt, S(f'b{len(bill_rows)}', 9, BLACK))])

        bill_tbl = Table(bill_rows, colWidths=[BL - 16], style=TableStyle([('BACKGROUND', (0,0), (-1,-1), LGRAY), ('TOPPADDING', (0,0), (-1,-1), 4), ('BOTTOMPADDING', (0,0), (-1,-1), 3), ('LEFTPADDING', (0,0), (-1,-1), 8), ('RIGHTPADDING', (0,0), (-1,-1), 8)]))

        meta_rows = [[Paragraph('DETAILS', S('det', 8, BRAND, 'Helvetica-Bold')), ''], [Paragraph('Invoice No', S('ml', 8, GRAY)), Paragraph(invoice.invoice_number, S('mv', 9, BLACK, 'Helvetica-Bold'))], [Paragraph('Issue Date', S('ml2', 8, GRAY)), Paragraph(issued_str, S('mv2', 9, BLACK))], [Paragraph('Due Date', S('ml3', 8, GRAY)), Paragraph(due_str, S('mv3', 9, BLACK))], [Paragraph('HSN / SAC', S('ml4', 8, GRAY)), Paragraph(hsn, S('mv4', 9, BLACK))], [Paragraph('Status', S('ml5', 8, GRAY)), Paragraph(invoice.status.capitalize(), S('mv5', 9, status_color, 'Helvetica-Bold'))]]
        MC1 = (BR - 16) * 0.42
        MC2 = (BR - 16) * 0.58
        meta_tbl = Table(meta_rows, colWidths=[MC1, MC2], style=TableStyle([('BACKGROUND', (0,0), (-1,-1), LGRAY), ('SPAN', (0,0), (1,0)), ('TOPPADDING', (0,0), (-1,-1), 4), ('BOTTOMPADDING', (0,0), (-1,-1), 3), ('LEFTPADDING', (0,0), (-1,-1), 8), ('RIGHTPADDING', (0,0), (-1,-1), 8)]))

        info = Table([[bill_tbl, Spacer(GAP, 1), meta_tbl]], colWidths=[BL, GAP, BR], style=TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
        story.append(info)
        story.append(Spacer(1, 6*mm))

        def TH(t): return Paragraph(t, S('th', 9, WHITE, 'Helvetica-Bold', TA_CENTER))
        def TC(t): return Paragraph(t, S('tc', 9, BLACK, align=TA_CENTER))
        def TL(t): return Paragraph(t, S('tl', 9, BLACK))
        def TR(t): return Paragraph(t, S('tr', 9, BLACK, align=TA_RIGHT))

        desc = invoice.description or 'Service / Product'
        C = [8*mm, USABLE-8*mm-20*mm-28*mm-18*mm-28*mm, 20*mm, 28*mm, 18*mm, 28*mm]

        items = Table([[TH('#'), TH('Description'), TH('HSN/SAC'), TH('Rate (Rs.)'), TH('GST %'), TH('Amount (Rs.)')], [TC('1'), TL(desc), TC(hsn), TR(f'{subtotal:,.2f}'), TC(f'{gst_rate:.1f}%'), TR(f'{subtotal:,.2f}')]], colWidths=C, style=TableStyle([('BACKGROUND', (0,0), (-1,0), BRAND), ('BACKGROUND', (0,1), (-1,-1), LGRAY), ('GRID', (0,0), (-1,-1), 0.4, colors.HexColor('#E5E7EB')), ('LINEBELOW', (0,0), (-1,0), 1, BRAND), ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6), ('LEFTPADDING', (0,0), (-1,-1), 5), ('RIGHTPADDING', (0,0), (-1,-1), 5), ('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
        story.append(items)
        story.append(Spacer(1, 5*mm))

        SW = 90*mm; SC1 = 36*mm; SC2 = 22*mm; SC3 = SW - SC1 - SC2

        def SL(t): return Paragraph(t, S('sl', 8, GRAY))
        def SR(t): return Paragraph(t, S('sr', 9, BLACK, align=TA_RIGHT))
        def SB(t): return Paragraph(t, S('sb', 10, WHITE, 'Helvetica-Bold'))
        def SBR(t): return Paragraph(t, S('sbr', 10, WHITE, 'Helvetica-Bold', TA_RIGHT))

        gst_rows = [[SL('IGST'), SL(f'@ {gst_rate:.1f}%'), SR(f'Rs. {igst:,.2f}')]] if igst > 0 else [[SL('CGST'), SL(f'@ {half_gst:.1f}%'), SR(f'Rs. {cgst:,.2f}')], [SL('SGST'), SL(f'@ {half_gst:.1f}%'), SR(f'Rs. {sgst:,.2f}')]]
        summary_rows = [[SL('Subtotal'), SL(''), SR(f'Rs. {subtotal:,.2f}')]] + gst_rows + [[SL('GST Total'), SL(''), SR(f'Rs. {gst_amount:,.2f}')]] + [[SB('TOTAL'), SB(''), SBR(f'Rs. {total:,.2f}')]]
        last = len(summary_rows) - 1

        sum_tbl = Table(summary_rows, colWidths=[SC1, SC2, SC3], style=TableStyle([('BACKGROUND', (0, last), (-1, last), BRAND), ('BACKGROUND', (0, 0), (-1, last-1), LGRAY), ('LINEABOVE', (0, last), (-1, last), 1, BRAND), ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,0), (-1,-1), 5), ('LEFTPADDING', (0,0), (-1,-1), 8), ('RIGHTPADDING', (0,0), (-1,-1), 8), ('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
        wrapper = Table([[Spacer(USABLE - SW, 1), sum_tbl]], colWidths=[USABLE - SW, SW], style=TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
        story.append(wrapper)
        story.append(Spacer(1, 8*mm))

        if invoice.notes:
            story.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#E5E7EB')))
            story.append(Spacer(1, 3*mm))
            story.append(Paragraph('Notes:', S('nl', 8, BRAND, 'Helvetica-Bold')))
            story.append(Paragraph(invoice.notes, S('nv', 8, GRAY, leading=12)))
            story.append(Spacer(1, 4*mm))

        story.append(HRFlowable(width='100%', thickness=0.8, color=BRAND))
        story.append(Spacer(1, 3*mm))
        footer = Table([[Paragraph('Thank you for your business!', S('fl', 9, BRAND, 'Helvetica-Bold')), Paragraph(f'Generated {timezone.now().strftime("%d %b %Y")}  |  Powered by iSaral', S('fr', 8, GRAY, align=TA_RIGHT))]], colWidths=[USABLE * 0.5, USABLE * 0.5], style=TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (-1,-1), 0)]))
        story.append(footer)
        doc.build(story)
        pdf_data = buffer.getvalue()
        buffer.close()

        from django.core.mail import EmailMessage as DjangoEmailMessage
        company_name_str = user.company_name or 'iSaral Business Solutions'
        subject = f"Invoice #{invoice.invoice_number} from {company_name_str}"
        body = f"""Dear {customer.name},\n\nThank you for your business.\n\nPlease find attached Invoice #{invoice.invoice_number}.\n\nInvoice Details:\n----------------------------\nInvoice Number : {invoice.invoice_number}\nInvoice Date   : {issued_str}\nDue Date       : {due_str}\nSubtotal       : Rs. {invoice.subtotal:,.2f}\nGST ({invoice.gst_rate:.0f}%)     : Rs. {invoice.gst_amount:,.2f}\nTotal Amount   : Rs. {invoice.total:,.2f}\n----------------------------\n\nIf you have any questions, please contact us.\n\nRegards,\n{company_name_str}\nhttps://isaral.ai\n"""

        email_msg = DjangoEmailMessage(subject=subject, body=body, from_email=user.email, to=[customer.email])
        email_msg.attach(f'INV-{invoice.invoice_number}.pdf', pdf_data, 'application/pdf')
        email_msg.send(fail_silently=False)
        messages.success(request, f'Invoice emailed successfully to {customer.email}')

    except Exception as e:
        messages.error(request, f'Email could not be sent. Please try again later. ({str(e)})')

    return redirect('accounts:invoices')


@login_required(login_url='accounts:login')
def generate_invoice_pdf(request, invoice_id):
    try:
        invoice = Invoice.objects.get(id=invoice_id, user=request.user)
    except Invoice.DoesNotExist:
        messages.error(request, 'Invoice not found.')
        return redirect('accounts:invoices')

    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT

    LEFT_MARGIN = RIGHT_MARGIN = 15 * mm
    TOP_MARGIN = BOT_MARGIN = 12 * mm
    USABLE = A4[0] - LEFT_MARGIN - RIGHT_MARGIN

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="INV-{invoice.invoice_number}.pdf"'

    doc = SimpleDocTemplate(response, pagesize=A4, leftMargin=LEFT_MARGIN, rightMargin=RIGHT_MARGIN, topMargin=TOP_MARGIN, bottomMargin=BOT_MARGIN)

    BRAND = colors.HexColor('#0D1B4B')
    GOLD  = colors.HexColor('#F4A61D')
    GREEN = colors.HexColor('#0F9D58')
    RED   = colors.HexColor('#E53935')
    GRAY  = colors.HexColor('#6B7280')
    LGRAY = colors.HexColor('#F3F4F6')
    BLACK = colors.HexColor('#111827')
    WHITE = colors.white

    status_color = {'paid': GREEN, 'pending': GOLD, 'issued': GOLD, 'overdue': RED, 'draft': GRAY}.get(invoice.status, GRAY)
    BASE = getSampleStyleSheet()['Normal']

    def S(name, size=9, color=BLACK, font='Helvetica', align=TA_LEFT, leading=None):
        return ParagraphStyle(name, parent=BASE, fontSize=size, textColor=color, fontName=font, alignment=align, leading=leading or size+4)

    user     = request.user
    customer = invoice.customer
    company_name    = user.company_name or 'iSaral Business Solutions'
    company_address = user.business_address or 'Bangalore, Karnataka'
    company_gstin   = user.gstin or ''
    company_phone   = user.phone or ''
    company_email   = user.email or ''

    cname  = (customer.name if customer else 'N/A')
    cco    = (customer.company if customer else '')
    cemail = (customer.email if customer else '')
    cphone = (customer.phone if customer else '')
    caddr  = (customer.address if customer else '')
    cstate = (customer.state if customer else '')
    cgstin = (customer.gstin if customer else '')

    issued_str = invoice.issued_date.strftime('%d %b %Y')
    due_str    = invoice.due_date.strftime('%d %b %Y') if invoice.due_date else 'N/A'
    hsn        = invoice.hsn_sac_code or '-'

    subtotal   = Decimal(str(invoice.subtotal or 0))
    gst_rate   = Decimal(str(invoice.gst_rate or 0))
    gst_amount = Decimal(str(invoice.gst_amount or 0))
    cgst       = Decimal(str(invoice.cgst_amount or 0))
    sgst       = Decimal(str(invoice.sgst_amount or 0))
    igst       = Decimal(str(invoice.igst_amount or 0))
    total      = Decimal(str(invoice.total or 0))
    half_gst   = gst_rate / Decimal('2')

    story = []
    L = USABLE * 0.55; R = USABLE * 0.45

    left_lines = [Paragraph('iSaral', S('h1', 18, WHITE, 'Helvetica-Bold', leading=22)), Spacer(1, 3), Paragraph(company_name, S('h2', 10, WHITE, 'Helvetica-Bold', leading=14)), Paragraph(company_address, S('h3', 8, WHITE, leading=12))]
    if company_gstin: left_lines.append(Paragraph(f'GSTIN: {company_gstin}', S('h4', 8, WHITE, leading=12)))
    if company_phone: left_lines.append(Paragraph(f'Ph: {company_phone}', S('h5', 8, WHITE, leading=12)))
    left_lines.append(Paragraph(f'Email: {company_email}', S('h6', 8, WHITE, leading=12)))

    right_lines = [Paragraph('TAX INVOICE', S('ti', 13, GOLD, 'Helvetica-Bold', TA_RIGHT)), Spacer(1, 4), Paragraph(f'# {invoice.invoice_number}', S('in', 11, WHITE, 'Helvetica-Bold', TA_RIGHT)), Spacer(1, 6), Paragraph(f'Date: {issued_str}', S('d1', 9, WHITE, align=TA_RIGHT)), Paragraph(f'Due:  {due_str}', S('d2', 9, WHITE, align=TA_RIGHT)), Spacer(1, 6), Paragraph(invoice.status.upper(), S('st', 8, WHITE, 'Helvetica-Bold', TA_RIGHT))]

    header = Table([[left_lines, right_lines]], colWidths=[L, R], style=TableStyle([('BACKGROUND', (0,0), (-1,-1), BRAND), ('VALIGN', (0,0), (-1,-1), 'TOP'), ('LEFTPADDING', (0,0), (-1,-1), 10), ('RIGHTPADDING', (0,0), (-1,-1), 10), ('TOPPADDING', (0,0), (-1,-1), 12), ('BOTTOMPADDING', (0,0), (-1,-1), 14)]))
    story.append(header); story.append(Spacer(1, 6*mm))

    BL = BR = USABLE * 0.50 - 3*mm; GAP = 6*mm

    bill_rows = [[Paragraph('BILL TO', S('bt', 8, BRAND, 'Helvetica-Bold'))], [Paragraph(cname, S('bn', 10, BLACK, 'Helvetica-Bold'))]]
    for txt in [cco, cemail, cphone, caddr, (f'State: {cstate}' if cstate else ''), (f'GSTIN: {cgstin}' if cgstin else '')]:
        if txt: bill_rows.append([Paragraph(txt, S(f'b{len(bill_rows)}', 9, BLACK))])

    bill_tbl = Table(bill_rows, colWidths=[BL - 16], style=TableStyle([('BACKGROUND', (0,0), (-1,-1), LGRAY), ('TOPPADDING', (0,0), (-1,-1), 4), ('BOTTOMPADDING', (0,0), (-1,-1), 3), ('LEFTPADDING', (0,0), (-1,-1), 8), ('RIGHTPADDING', (0,0), (-1,-1), 8)]))

    meta_rows = [[Paragraph('DETAILS', S('det', 8, BRAND, 'Helvetica-Bold')), ''], [Paragraph('Invoice No', S('ml', 8, GRAY)), Paragraph(invoice.invoice_number, S('mv', 9, BLACK, 'Helvetica-Bold'))], [Paragraph('Issue Date', S('ml2', 8, GRAY)), Paragraph(issued_str, S('mv2', 9, BLACK))], [Paragraph('Due Date', S('ml3', 8, GRAY)), Paragraph(due_str, S('mv3', 9, BLACK))], [Paragraph('HSN / SAC', S('ml4', 8, GRAY)), Paragraph(hsn, S('mv4', 9, BLACK))], [Paragraph('Status', S('ml5', 8, GRAY)), Paragraph(invoice.status.capitalize(), S('mv5', 9, status_color, 'Helvetica-Bold'))]]
    MC1 = (BR - 16) * 0.42; MC2 = (BR - 16) * 0.58
    meta_tbl = Table(meta_rows, colWidths=[MC1, MC2], style=TableStyle([('BACKGROUND', (0,0), (-1,-1), LGRAY), ('SPAN', (0,0), (1,0)), ('TOPPADDING', (0,0), (-1,-1), 4), ('BOTTOMPADDING', (0,0), (-1,-1), 3), ('LEFTPADDING', (0,0), (-1,-1), 8), ('RIGHTPADDING', (0,0), (-1,-1), 8)]))

    info = Table([[bill_tbl, Spacer(GAP, 1), meta_tbl]], colWidths=[BL, GAP, BR], style=TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
    story.append(info); story.append(Spacer(1, 6*mm))

    def TH(t): return Paragraph(t, S('th', 9, WHITE, 'Helvetica-Bold', TA_CENTER))
    def TC(t): return Paragraph(t, S('tc', 9, BLACK, align=TA_CENTER))
    def TL(t): return Paragraph(t, S('tl', 9, BLACK))
    def TR(t): return Paragraph(t, S('tr', 9, BLACK, align=TA_RIGHT))

    desc = invoice.description or 'Service / Product'
    C = [8*mm, USABLE-8*mm-20*mm-28*mm-18*mm-28*mm, 20*mm, 28*mm, 18*mm, 28*mm]
    items = Table([[TH('#'), TH('Description'), TH('HSN/SAC'), TH('Rate (Rs.)'), TH('GST %'), TH('Amount (Rs.)')], [TC('1'), TL(desc), TC(hsn), TR(f'{subtotal:,.2f}'), TC(f'{gst_rate:.1f}%'), TR(f'{subtotal:,.2f}')]], colWidths=C, style=TableStyle([('BACKGROUND', (0,0), (-1,0), BRAND), ('BACKGROUND', (0,1), (-1,-1), LGRAY), ('GRID', (0,0), (-1,-1), 0.4, colors.HexColor('#E5E7EB')), ('LINEBELOW', (0,0), (-1,0), 1, BRAND), ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6), ('LEFTPADDING', (0,0), (-1,-1), 5), ('RIGHTPADDING', (0,0), (-1,-1), 5), ('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
    story.append(items); story.append(Spacer(1, 5*mm))

    SW = 90*mm; SC1 = 36*mm; SC2 = 22*mm; SC3 = SW - SC1 - SC2

    def SL(t): return Paragraph(t, S('sl', 8, GRAY))
    def SR(t): return Paragraph(t, S('sr', 9, BLACK, align=TA_RIGHT))
    def SB(t): return Paragraph(t, S('sb', 10, WHITE, 'Helvetica-Bold'))
    def SBR(t): return Paragraph(t, S('sbr', 10, WHITE, 'Helvetica-Bold', TA_RIGHT))

    gst_rows = [[SL('IGST'), SL(f'@ {gst_rate:.1f}%'), SR(f'Rs. {igst:,.2f}')]] if igst > 0 else [[SL('CGST'), SL(f'@ {half_gst:.1f}%'), SR(f'Rs. {cgst:,.2f}')], [SL('SGST'), SL(f'@ {half_gst:.1f}%'), SR(f'Rs. {sgst:,.2f}')]]
    summary_rows = [[SL('Subtotal'), SL(''), SR(f'Rs. {subtotal:,.2f}')]] + gst_rows + [[SL('GST Total'), SL(''), SR(f'Rs. {gst_amount:,.2f}')]] + [[SB('TOTAL'), SB(''), SBR(f'Rs. {total:,.2f}')]]
    last = len(summary_rows) - 1

    sum_tbl = Table(summary_rows, colWidths=[SC1, SC2, SC3], style=TableStyle([('BACKGROUND', (0, last), (-1, last), BRAND), ('BACKGROUND', (0, 0), (-1, last-1), LGRAY), ('LINEABOVE', (0, last), (-1, last), 1, BRAND), ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,0), (-1,-1), 5), ('LEFTPADDING', (0,0), (-1,-1), 8), ('RIGHTPADDING', (0,0), (-1,-1), 8), ('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
    wrapper = Table([[Spacer(USABLE - SW, 1), sum_tbl]], colWidths=[USABLE - SW, SW], style=TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
    story.append(wrapper); story.append(Spacer(1, 8*mm))

    if invoice.notes:
        story.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#E5E7EB')))
        story.append(Spacer(1, 3*mm))
        story.append(Paragraph('Notes:', S('nl', 8, BRAND, 'Helvetica-Bold')))
        story.append(Paragraph(invoice.notes, S('nv', 8, GRAY, leading=12)))
        story.append(Spacer(1, 4*mm))

    story.append(HRFlowable(width='100%', thickness=0.8, color=BRAND))
    story.append(Spacer(1, 3*mm))
    footer = Table([[Paragraph('Thank you for your business!', S('fl', 9, BRAND, 'Helvetica-Bold')), Paragraph(f'Generated {timezone.now().strftime("%d %b %Y")}  |  Powered by iSaral', S('fr', 8, GRAY, align=TA_RIGHT))]], colWidths=[USABLE * 0.5, USABLE * 0.5], style=TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (-1,-1), 0)]))
    story.append(footer)
    doc.build(story)
    return response


# ============================================
# CUSTOMER VIEWS
# ============================================

@login_required(login_url='accounts:login')
def add_customer(request):
    if request.method == 'POST':
        name    = request.POST.get('name', '').strip()
        email   = request.POST.get('email', '').strip()
        phone   = request.POST.get('phone', '').strip()
        company = request.POST.get('company', '').strip()
        gstin   = request.POST.get('gstin', '').strip()
        state   = request.POST.get('state', '').strip()
        address = request.POST.get('address', '').strip()

        if not name or not email:
            messages.error(request, 'Name and Email are required.')
            return render(request, 'accounts/customer_form.html')

        if Customer.objects.filter(user=request.user, email=email).exists():
            messages.error(request, f'Customer with email {email} already exists.')
            return render(request, 'accounts/customer_form.html')

        try:
            customer = Customer.objects.create(
                user=request.user, name=name, email=email,
                phone=phone, company=company, gstin=gstin,
                state=state, address=address,
            )
            messages.success(request, f'Customer {name} created successfully!')
            return redirect('accounts:get_customer_details', customer_id=customer.id)
        except Exception as e:
            messages.error(request, f'Error creating customer: {str(e)}')

    context = {'page_title': 'Add New Customer'}
    return render(request, 'accounts/customer_form.html', context)


@login_required(login_url='accounts:login')
def customer_list(request):
    user = request.user
    search_query = request.GET.get('search', '').strip()

    customers = Customer.objects.filter(user=user)

    if search_query:
        customers = customers.filter(
            Q(name__icontains=search_query) |
            Q(company__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone__icontains=search_query) |
            Q(gstin__icontains=search_query)
        )

    customers = customers.order_by('-created_at')

    paginator   = Paginator(customers, 10)
    page_number = request.GET.get('page', 1)
    page_obj    = paginator.get_page(page_number)

    # -- FIX: count against ALL customers (unfiltered) for the stat cards --
    all_customers = Customer.objects.filter(user=user)

    context = {
        'page_title':         'Customers',
        'page_obj':           page_obj,
        'customers':          page_obj.object_list,
        'total_customers':    all_customers.count(),
        'active_customers':   all_customers.filter(is_active=True).count(),
        'inactive_customers': all_customers.filter(is_active=False).count(),  # FIX
        'search_query':       search_query,
    }
    return render(request, 'accounts/customers.html', context)


@login_required(login_url='accounts:login')
def customer_search(request):
    query = request.GET.get('q', '').strip()
    user  = request.user

    if len(query) < 2:
        return render(request, 'accounts/customer_search_results.html', {'customers': []})

    customers = Customer.objects.filter(user=user).filter(
        Q(name__icontains=query) | Q(company__icontains=query) |
        Q(email__icontains=query) | Q(phone__icontains=query) |
        Q(gstin__icontains=query)
    )[:10]

    return render(request, 'accounts/customer_search_results.html', {'customers': customers, 'query': query})


@login_required(login_url='accounts:login')
def get_customer_details(request, customer_id):
    user = request.user
    try:
        customer = Customer.objects.get(id=customer_id, user=user)
    except Customer.DoesNotExist:
        messages.error(request, 'Customer not found.')
        return redirect('accounts:create_customer')

    invoices         = Invoice.objects.filter(customer=customer).order_by('-issued_date')
    total_invoices   = invoices.count()
    paid_invoices    = invoices.filter(status='paid').count()
    pending_invoices = invoices.filter(status__in=['issued', 'pending', 'overdue']).count()
    total_spent      = sum([inv.total for inv in invoices.filter(status='paid')]) if paid_invoices > 0 else 0
    tickets          = SupportTicket.objects.filter(customer_email=customer.email).order_by('-created_at')[:5]

    context = {
        'page_title':        f'Customer - {customer.name}',
        'customer':          customer,
        'invoices':          invoices[:10],
        'total_invoices':    total_invoices,
        'paid_invoices':     paid_invoices,
        'pending_invoices':  pending_invoices,
        'total_spent':       total_spent,
        'tickets':           tickets,
    }
    return render(request, 'accounts/customer_detail.html', context)


@login_required(login_url='accounts:login')
@require_http_methods(["GET", "POST"])
def customer_edit(request, customer_id):
    user = request.user
    try:
        customer = Customer.objects.get(id=customer_id, user=user)
    except Customer.DoesNotExist:
        messages.error(request, 'Customer not found.')
        return redirect('accounts:create_customer')

    if request.method == 'POST':
        name    = request.POST.get('name', '').strip()
        email   = request.POST.get('email', '').strip()
        phone   = request.POST.get('phone', '').strip()
        company = request.POST.get('company', '').strip()
        gstin   = request.POST.get('gstin', '').strip()
        state   = request.POST.get('state', '').strip()
        address = request.POST.get('address', '').strip()

        if not name or not email:
            messages.error(request, 'Name and Email are required.')
            return render(request, 'accounts/customer_form.html', {'customer': customer})

        if Customer.objects.filter(user=user, email=email).exclude(id=customer.id).exists():
            messages.error(request, f'Email {email} is already used by another customer.')
            return render(request, 'accounts/customer_form.html', {'customer': customer})

        try:
            customer.name = name; customer.email = email; customer.phone = phone
            customer.company = company; customer.gstin = gstin
            customer.state = state; customer.address = address
            customer.save()
            messages.success(request, f'Customer {name} updated successfully!')
            return redirect('accounts:get_customer_details', customer_id=customer.id)
        except Exception as e:
            messages.error(request, f'Error updating customer: {str(e)}')

    context = {
        'page_title': f'Edit Customer - {customer.name}',
        'customer':   customer,
        'is_edit':    True,
    }
    return render(request, 'accounts/customer_form.html', context)


@login_required(login_url='accounts:login')
@require_http_methods(["POST"])
def toggle_customer_status(request, customer_id):
    """Toggle customer active / inactive."""
    try:
        customer = Customer.objects.get(id=customer_id, user=request.user)
        customer.is_active = not customer.is_active
        customer.save()
        label = "activated" if customer.is_active else "deactivated"
        messages.success(request, f'Customer {customer.name} {label} successfully!')
    except Customer.DoesNotExist:
        messages.error(request, 'Customer not found.')
    return redirect('accounts:customer_list')


@login_required(login_url='accounts:login')
@require_http_methods(["POST"])
def delete_customer(request, customer_id):
    user = request.user
    try:
        customer = Customer.objects.get(id=customer_id, user=user)
    except Customer.DoesNotExist:
        messages.error(request, 'Customer not found.')
        return redirect('accounts:create_customer')

    invoice_count = Invoice.objects.filter(customer=customer).count()
    if invoice_count > 0:
        messages.error(request, f'Cannot delete customer with {invoice_count} invoice(s). Archive instead.')
        return redirect('accounts:get_customer_details', customer_id=customer.id)

    try:
        customer_name = customer.name
        customer.delete()
        messages.success(request, f'Customer {customer_name} deleted successfully!')
        return redirect('accounts:create_customer')
    except Exception as e:
        messages.error(request, f'Error deleting customer: {str(e)}')
        return redirect('accounts:get_customer_details', customer_id=customer.id)


# ============================================
# TICKET VIEWS
# ============================================

@login_required(login_url='accounts:login')
def tickets_list(request):
    tickets = SupportTicket.objects.filter(user=request.user).order_by('-created_at')
    context = {
        'tickets':           tickets,
        'page_title':        'Support Tickets',
        'total_tickets':     tickets.count(),
        'open_count':        tickets.filter(status='open').count(),
        'in_progress_count': tickets.filter(status='in_progress').count(),
        'resolved_count':    tickets.filter(status='resolved').count(),
        'closed_count':      tickets.filter(status='closed').count(),
    }
    return render(request, 'accounts/tickets.html', context)


@login_required(login_url='accounts:login')
def create_ticket(request):
    if request.method == 'POST':
        form = SupportTicketForm(request.POST)
        if form.is_valid():
            try:
                ticket_number = f"TKT-{timezone.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
                subject     = form.cleaned_data['subject']
                product     = form.cleaned_data['product']
                description = form.cleaned_data['description']
                description = f"Product: {dict(form.fields['product'].choices).get(product, product)}\n\n{description}"

                tally_sno = form.cleaned_data.get('tally_sno')
                if tally_sno: description += f"\n\nTally Serial Number: {tally_sno}"

                other_product_name = form.cleaned_data.get('other_product_name')
                if other_product_name: description += f"\n\nOther Product: {other_product_name}"

                ticket = SupportTicket.objects.create(
                    user=request.user, ticket_number=ticket_number,
                    customer_name=form.cleaned_data['customer_name'],
                    customer_mobile=form.cleaned_data['customer_mobile'],
                    customer_email=form.cleaned_data['customer_email'],
                    subject=subject, description=description,
                    priority=form.cleaned_data['priority'], status='open',
                )
                send_ticket_confirmation_email(ticket)
                messages.success(request, f"Ticket #{ticket.ticket_number} created successfully.")
                return redirect('accounts:tickets')
            except Exception as e:
                messages.error(request, f"Database Error: {str(e)}")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = SupportTicketForm()

    return render(request, 'accounts/create_ticket.html', {'form': form, 'page_title': 'Create Ticket'})


@login_required(login_url='accounts:login')
def ticket_detail_view(request, ticket_id):
    try:
        ticket = SupportTicket.objects.get(id=ticket_id, user=request.user)
    except SupportTicket.DoesNotExist:
        messages.error(request, 'Ticket not found.')
        return redirect('accounts:tickets')

    replies = ticket.replies.all().order_by('created_at')

    if request.method == 'POST':
        action = request.POST.get('action', '').strip()

        if action == 'add_reply':
            message_text    = request.POST.get('message', '').strip()
            resolution_note = request.POST.get('resolution_note', '').strip()
            new_status      = request.POST.get('status', ticket.status).strip()

            if not message_text:
                messages.error(request, 'Reply message cannot be empty.')
                return redirect('accounts:ticket_detail', ticket_id=ticket_id)

            from accounts.models import TicketReply
            TicketReply.objects.create(
                ticket=ticket, user=request.user, message=message_text,
                resolution_note=resolution_note, is_staff_reply=request.user.is_staff,
            )
            if new_status in ['open', 'in_progress', 'resolved', 'closed']:
                ticket.status = new_status
            ticket.save()
            messages.success(request, 'Reply added successfully.')
            return redirect('accounts:ticket_detail', ticket_id=ticket_id)

        elif action == 'update_status':
            new_status = request.POST.get('status', '').strip()
            if new_status in ['open', 'in_progress', 'resolved', 'closed']:
                ticket.status = new_status
                ticket.save()
                messages.success(request, f'Status updated to {ticket.get_status_display()}.')
            else:
                messages.error(request, 'Invalid status.')
            return redirect('accounts:ticket_detail', ticket_id=ticket_id)

        elif action == 'edit':
            subject     = request.POST.get('subject', '').strip()
            priority    = request.POST.get('priority', ticket.priority).strip()
            status      = request.POST.get('status', ticket.status).strip()
            description = request.POST.get('description', '').strip()
            if not subject:
                messages.error(request, 'Subject is required.')
                return redirect('accounts:ticket_detail', ticket_id=ticket_id)
            ticket.subject = subject; ticket.priority = priority
            ticket.status = status; ticket.description = description
            ticket.save()
            messages.success(request, 'Ticket updated successfully.')
            return redirect('accounts:ticket_detail', ticket_id=ticket_id)

        elif action == 'close_ticket':
            ticket.status = 'closed'
            ticket.save()
            messages.success(request, 'Ticket closed.')
            return redirect('accounts:ticket_detail', ticket_id=ticket_id)

    context = {'ticket': ticket, 'replies': replies, 'page_title': f'Ticket: {ticket.subject}'}
    return render(request, 'accounts/ticket_detail.html', context)


@login_required(login_url='accounts:login')
def update_ticket_status_view(request, ticket_id):
    try:
        ticket = SupportTicket.objects.get(id=ticket_id, user=request.user)
    except SupportTicket.DoesNotExist:
        messages.error(request, 'Ticket not found.')
        return redirect('accounts:tickets')

    if request.method != 'POST':
        return redirect('accounts:ticket_detail', ticket_id=ticket_id)

    new_status = request.POST.get('status', '').strip()
    if new_status in ['open', 'in_progress', 'resolved', 'closed']:
        ticket.status = new_status
        ticket.save()
        messages.success(request, f'Status updated to {ticket.get_status_display()}.')
    else:
        messages.error(request, 'Invalid status.')

    return redirect('accounts:ticket_detail', ticket_id=ticket_id)


# ============================================
# REPORTS VIEW
# ============================================

# ============================================================
# COMPLETE FIXED billing_reports VIEW — paste into accounts/views.py
# replacing the existing billing_reports, export_invoices_csv,
# export_invoices_pdf functions
# ============================================================

from django.db.models import (
    Sum, Count, Avg, Q, F,
    Case, When, Value, DecimalField
)
from django.db.models.functions import TruncMonth, Coalesce
from django.utils import timezone
from datetime import datetime, timedelta, date
from decimal import Decimal
import json


# ── shared helper so Dashboard and Reports always use identical numbers ──

def get_invoice_stats(user, invoices_qs=None):
    """
    Reusable helper. Pass a filtered queryset or None for all invoices.
    Returns a dict of consistent metrics used by both Dashboard and Reports.
    """
    if invoices_qs is None:
        from accounts.models import Invoice
        invoices_qs = Invoice.objects.filter(user=user)

    agg = invoices_qs.aggregate(
        total_revenue   = Coalesce(Sum('total'),       Decimal('0.00')),
        paid_revenue    = Coalesce(Sum('total', filter=Q(status='paid')),    Decimal('0.00')),
        pending_revenue = Coalesce(Sum('total', filter=Q(status__in=['issued','pending','draft'])), Decimal('0.00')),
        overdue_revenue = Coalesce(Sum('total', filter=Q(status='overdue')), Decimal('0.00')),
        total_gst       = Coalesce(Sum('gst_amount'),  Decimal('0.00')),
        total_cgst      = Coalesce(Sum('cgst_amount'), Decimal('0.00')),
        total_sgst      = Coalesce(Sum('sgst_amount'), Decimal('0.00')),
        total_igst      = Coalesce(Sum('igst_amount'), Decimal('0.00')),
        total_subtotal  = Coalesce(Sum('subtotal'),    Decimal('0.00')),
        avg_invoice     = Avg('total'),
        total_count     = Count('id'),
        paid_count      = Count('id', filter=Q(status='paid')),
        pending_count   = Count('id', filter=Q(status__in=['issued','pending','draft'])),
        overdue_count   = Count('id', filter=Q(status='overdue')),
        draft_count     = Count('id', filter=Q(status='draft')),
        cancelled_count = Count('id', filter=Q(status='cancelled')),
    )

    total = agg['total_count'] or 1  # avoid div-by-zero
    agg['paid_pct']      = round((agg['paid_count']      / total) * 100, 1)
    agg['pending_pct']   = round((agg['pending_count']   / total) * 100, 1)
    agg['overdue_pct']   = round((agg['overdue_count']   / total) * 100, 1)
    agg['draft_pct']     = round((agg['draft_count']     / total) * 100, 1)
    agg['cancelled_pct'] = round((agg['cancelled_count'] / total) * 100, 1)
    agg['outstanding']   = agg['pending_revenue'] + agg['overdue_revenue']
    agg['avg_invoice']   = agg['avg_invoice'] or Decimal('0.00')
    return agg


@login_required(login_url='accounts:login')
def billing_reports(request):
    from accounts.models import Invoice, Customer, SupportTicket

    user  = request.user
    today = timezone.now().date()

    # ── 1. DATE RANGE PRESETS ────────────────────────────────────────────
    preset = request.GET.get('preset', '')
    from_date_str = request.GET.get('from_date', '')
    to_date_str   = request.GET.get('to_date', '')

    # Financial year helpers (India: Apr 1 – Mar 31)
    fy_start_year = today.year if today.month >= 4 else today.year - 1
    this_fy_start = date(fy_start_year, 4, 1)
    this_fy_end   = date(fy_start_year + 1, 3, 31)
    prev_fy_start = date(fy_start_year - 1, 4, 1)
    prev_fy_end   = date(fy_start_year,     3, 31)

    preset_map = {
        'today':       (today,                         today),
        'yesterday':   (today - timedelta(days=1),     today - timedelta(days=1)),
        'this_week':   (today - timedelta(days=today.weekday()), today),
        'this_month':  (today.replace(day=1),          today),
        'last_month':  (
            (today.replace(day=1) - timedelta(days=1)).replace(day=1),
            today.replace(day=1) - timedelta(days=1),
        ),
        'last_3m':     (today - timedelta(days=90),    today),
        'last_6m':     (today - timedelta(days=180),   today),
        'this_fy':     (this_fy_start,                 this_fy_end),
        'prev_fy':     (prev_fy_start,                 prev_fy_end),
        'all':         (None, None),   # no date filter → matches invoices page
    }

    if preset in preset_map:
        from_date, to_date = preset_map[preset]
    elif from_date_str and to_date_str:
        try:
            from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
            to_date   = datetime.strptime(to_date_str,   '%Y-%m-%d').date()
        except ValueError:
            from_date = to_date = None
    else:
        # ── FIX #1: Default = ALL TIME (matches Invoices page) ──────────
        from_date = None
        to_date   = None

    # ── 2. BUILD QUERYSETS ───────────────────────────────────────────────
    status_filter   = request.GET.get('status', '')
    customer_filter = request.GET.get('customer', '')
    gst_type_filter = request.GET.get('gst_type', '')   # 'cgst','igst'

    # All invoices for this user — matches what the Invoices page shows
    all_invoices = Invoice.objects.filter(user=user).select_related('customer')

    # Filtered queryset starts from all_invoices
    filtered = all_invoices

    if from_date and to_date:
        filtered = filtered.filter(issued_date__gte=from_date, issued_date__lte=to_date)

    if status_filter:
        filtered = filtered.filter(status=status_filter)

    if customer_filter:
        filtered = filtered.filter(customer_id=customer_filter)

    if gst_type_filter == 'cgst':
        filtered = filtered.filter(cgst_amount__gt=0)
    elif gst_type_filter == 'igst':
        filtered = filtered.filter(igst_amount__gt=0)

    filtered = filtered.order_by('-issued_date')

    # ── 3. STATS ─────────────────────────────────────────────────────────
    stats = get_invoice_stats(user, filtered)

    # ── 4. MONTHLY ANALYTICS (last 12 months) ────────────────────────────
    twelve_months_ago = today - timedelta(days=365)
    monthly_data = (
        all_invoices
        .filter(issued_date__gte=twelve_months_ago)
        .annotate(month=TruncMonth('issued_date'))
        .values('month')
        .annotate(
            revenue        = Coalesce(Sum('total'),                                  Decimal('0')),
            paid_revenue   = Coalesce(Sum('total', filter=Q(status='paid')),         Decimal('0')),
            pending_rev    = Coalesce(Sum('total', filter=Q(status__in=['issued','pending','draft'])), Decimal('0')),
            overdue_rev    = Coalesce(Sum('total', filter=Q(status='overdue')),      Decimal('0')),
            invoice_count  = Count('id'),
            paid_count     = Count('id', filter=Q(status='paid')),
            pending_count  = Count('id', filter=Q(status__in=['issued','pending','draft'])),
            overdue_count  = Count('id', filter=Q(status='overdue')),
            new_customers  = Count('customer', distinct=True),
        )
        .order_by('month')
    )

    monthly_labels        = []
    monthly_revenue       = []
    monthly_paid          = []
    monthly_pending       = []
    monthly_overdue       = []
    monthly_invoice_count = []

    for m in monthly_data:
        if m['month']:
            monthly_labels.append(m['month'].strftime('%b %Y'))
            monthly_revenue.append(float(m['revenue'] or 0))
            monthly_paid.append(float(m['paid_revenue'] or 0))
            monthly_pending.append(float(m['pending_rev'] or 0))
            monthly_overdue.append(float(m['overdue_rev'] or 0))
            monthly_invoice_count.append(m['invoice_count'])

    # ── 5. CUSTOMER REPORTS ───────────────────────────────────────────────
    top_customers = (
        Customer.objects.filter(user=user)
        .annotate(
            total_revenue  = Coalesce(Sum('invoice__total'),                                            Decimal('0')),
            paid_revenue   = Coalesce(Sum('invoice__total', filter=Q(invoice__status='paid')),          Decimal('0')),
            pending_rev    = Coalesce(Sum('invoice__total', filter=Q(invoice__status__in=['issued','pending','draft'])), Decimal('0')),
            overdue_rev    = Coalesce(Sum('invoice__total', filter=Q(invoice__status='overdue')),       Decimal('0')),
            invoice_count  = Count('invoice'),
        )
        .filter(invoice_count__gt=0)
        .order_by('-total_revenue')[:10]
    )

    customers_with_pending = (
        Customer.objects.filter(user=user)
        .annotate(
            pending_amount = Coalesce(
                Sum('invoice__total', filter=Q(invoice__status__in=['issued','pending','draft'])),
                Decimal('0')
            ),
            pending_count = Count('invoice', filter=Q(invoice__status__in=['issued','pending','draft'])),
        )
        .filter(pending_count__gt=0)
        .order_by('-pending_amount')[:10]
    )

    customers_with_overdue = (
        Customer.objects.filter(user=user)
        .annotate(
            overdue_amount = Coalesce(
                Sum('invoice__total', filter=Q(invoice__status='overdue')),
                Decimal('0')
            ),
            overdue_count = Count('invoice', filter=Q(invoice__status='overdue')),
        )
        .filter(overdue_count__gt=0)
        .order_by('-overdue_amount')[:10]
    )

    # ── 6. GST ANALYTICS ─────────────────────────────────────────────────
    gst_stats = filtered.aggregate(
        total_cgst     = Coalesce(Sum('cgst_amount'), Decimal('0')),
        total_sgst     = Coalesce(Sum('sgst_amount'), Decimal('0')),
        total_igst     = Coalesce(Sum('igst_amount'), Decimal('0')),
        total_gst      = Coalesce(Sum('gst_amount'),  Decimal('0')),
        taxable_amount = Coalesce(Sum('subtotal'),     Decimal('0')),
        grand_total    = Coalesce(Sum('total'),        Decimal('0')),
    )

    gst_monthly = (
        all_invoices
        .filter(issued_date__gte=twelve_months_ago)
        .annotate(month=TruncMonth('issued_date'))
        .values('month')
        .annotate(
            cgst = Coalesce(Sum('cgst_amount'), Decimal('0')),
            sgst = Coalesce(Sum('sgst_amount'), Decimal('0')),
            igst = Coalesce(Sum('igst_amount'), Decimal('0')),
            gst  = Coalesce(Sum('gst_amount'),  Decimal('0')),
        )
        .order_by('month')
    )

    gst_labels = [m['month'].strftime('%b %Y') for m in gst_monthly if m['month']]
    gst_cgst   = [float(m['cgst'] or 0) for m in gst_monthly if m['month']]
    gst_sgst   = [float(m['sgst'] or 0) for m in gst_monthly if m['month']]
    gst_igst   = [float(m['igst'] or 0) for m in gst_monthly if m['month']]
    gst_total  = [float(m['gst']  or 0) for m in gst_monthly if m['month']]

    # Customer list for filter dropdown
    all_customers = Customer.objects.filter(user=user).order_by('name')

    # ── 7. EXPORTS ───────────────────────────────────────────────────────
    export_format = request.GET.get('export', '')
    if export_format == 'csv':
        return _export_csv(filtered)
    elif export_format == 'pdf':
        return _export_pdf(filtered, user, from_date, to_date)
    elif export_format == 'gst_csv':
        return _export_gst_csv(filtered)

    # ── 8. CONTEXT ───────────────────────────────────────────────────────
    context = {
        'page_title': 'Reports',

        # date range
        'from_date':    from_date.strftime('%Y-%m-%d') if from_date else '',
        'to_date':      to_date.strftime('%Y-%m-%d')   if to_date   else '',
        'preset':       preset,
        'today':        today.strftime('%Y-%m-%d'),

        # filters
        'status_filter':   status_filter,
        'customer_filter': customer_filter,
        'all_customers':   all_customers,

        # invoice data
        'invoices': filtered,

        # ── FIX #1: total_invoices now matches filtered (or all) ──
        'total_invoices':   stats['total_count'],
        'total_revenue':    stats['total_revenue'],
        'paid_revenue':     stats['paid_revenue'],
        'pending_revenue':  stats['pending_revenue'],
        'overdue_revenue':  stats['overdue_revenue'],
        'outstanding':      stats['outstanding'],
        'average_invoice':  stats['avg_invoice'],
        'pending_amount':   stats['pending_revenue'],

        # status breakdown
        'paid_count':      stats['paid_count'],
        'pending_count':   stats['pending_count'],
        'overdue_count':   stats['overdue_count'],
        'draft_count':     stats['draft_count'],
        'cancelled_count': stats['cancelled_count'],
        'paid_pct':        stats['paid_pct'],
        'pending_pct':     stats['pending_pct'],
        'overdue_pct':     stats['overdue_pct'],
        'draft_pct':       stats['draft_pct'],
        'cancelled_pct':   stats['cancelled_pct'],

        # monthly chart data (JSON for Chart.js)
        'monthly_labels':        json.dumps(monthly_labels),
        'monthly_revenue':       json.dumps(monthly_revenue),
        'monthly_paid':          json.dumps(monthly_paid),
        'monthly_pending':       json.dumps(monthly_pending),
        'monthly_overdue':       json.dumps(monthly_overdue),
        'monthly_invoice_count': json.dumps(monthly_invoice_count),

        # customer reports
        'top_customers':           top_customers,
        'customers_with_pending':  customers_with_pending,
        'customers_with_overdue':  customers_with_overdue,

        # GST
        'gst_stats':   gst_stats,
        'gst_labels':  json.dumps(gst_labels),
        'gst_cgst':    json.dumps(gst_cgst),
        'gst_sgst':    json.dumps(gst_sgst),
        'gst_igst':    json.dumps(gst_igst),
        'gst_total':   json.dumps(gst_total),
    }
    return render(request, 'accounts/reports.html', context)


# ── EXPORT HELPERS ────────────────────────────────────────────────────────

def _export_csv(invoices):
    import csv
    from django.http import HttpResponse
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="invoices_report.csv"'
    writer = csv.writer(response)
    writer.writerow([
        'Invoice #', 'Customer', 'Date', 'Due Date',
        'Subtotal', 'GST Rate', 'CGST', 'SGST', 'IGST',
        'GST Amount', 'Total', 'Status'
    ])
    for inv in invoices:
        writer.writerow([
            inv.invoice_number,
            inv.customer.name if inv.customer else 'N/A',
            inv.issued_date.strftime('%d-%m-%Y'),
            inv.due_date.strftime('%d-%m-%Y') if inv.due_date else '',
            inv.subtotal,
            f"{inv.gst_rate}%",
            inv.cgst_amount,
            inv.sgst_amount,
            inv.igst_amount,
            inv.gst_amount,
            inv.total,
            inv.get_status_display(),
        ])
    return response


def _export_gst_csv(invoices):
    import csv
    from django.http import HttpResponse
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="gst_report.csv"'
    writer = csv.writer(response)
    writer.writerow([
        'Invoice #', 'Customer', 'GSTIN', 'Date',
        'Taxable Amount', 'GST Rate', 'CGST', 'SGST', 'IGST',
        'Total GST', 'Grand Total'
    ])
    for inv in invoices:
        writer.writerow([
            inv.invoice_number,
            inv.customer.name    if inv.customer else 'N/A',
            inv.customer.gstin   if inv.customer else '',
            inv.issued_date.strftime('%d-%m-%Y'),
            inv.subtotal,
            f"{inv.gst_rate}%",
            inv.cgst_amount,
            inv.sgst_amount,
            inv.igst_amount,
            inv.gst_amount,
            inv.total,
        ])
    return response


def _export_pdf(invoices, user, from_date, to_date):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm, inch
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle,
        Paragraph, Spacer, HRFlowable
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
    from django.http import HttpResponse
    from io import BytesIO

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=12*mm, bottomMargin=15*mm,
    )

    BRAND = colors.HexColor('#0D1B4B')
    GRAY  = colors.HexColor('#6B7280')
    LGRAY = colors.HexColor('#F3F4F6')
    BLACK = colors.HexColor('#111827')
    WHITE = colors.white
    GREEN = colors.HexColor('#059669')
    RED   = colors.HexColor('#DC2626')
    AMBER = colors.HexColor('#D97706')

    styles = getSampleStyleSheet()
    USABLE = A4[0] - 30*mm

    def P(text, size=9, color=BLACK, bold=False, align=TA_LEFT):
        font = 'Helvetica-Bold' if bold else 'Helvetica'
        return Paragraph(str(text), ParagraphStyle(
            'x', parent=styles['Normal'],
            fontSize=size, textColor=color,
            fontName=font, alignment=align, leading=size+4,
        ))

    story = []

    # Header
    date_range = ''
    if from_date and to_date:
        date_range = f"{from_date.strftime('%d %b %Y')} – {to_date.strftime('%d %b %Y')}"
    else:
        date_range = 'All Time'

    company = user.company_name or 'iSaral Business Solutions'
    hdr = Table(
        [[
            [P('iSaral', 16, WHITE, True), Spacer(1,2), P(company, 9, WHITE), P(f'Generated: {timezone.now().strftime("%d %b %Y")}', 8, WHITE)],
            [P('BILLING REPORT', 13, colors.HexColor('#F4A61D'), True, TA_RIGHT), Spacer(1,4), P(f'Period: {date_range}', 9, WHITE, align=TA_RIGHT), P(f'Generated by: {user.email}', 8, WHITE, align=TA_RIGHT)],
        ]],
        colWidths=[USABLE*0.55, USABLE*0.45],
        style=TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), BRAND),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING', (0,0), (-1,-1), 12),
            ('RIGHTPADDING', (0,0), (-1,-1), 12),
            ('TOPPADDING', (0,0), (-1,-1), 14),
            ('BOTTOMPADDING', (0,0), (-1,-1), 14),
        ])
    )
    story.append(hdr)
    story.append(Spacer(1, 6*mm))

    # Invoice table
    col_w = [USABLE*0.16, USABLE*0.22, USABLE*0.12, USABLE*0.14, USABLE*0.12, USABLE*0.12, USABLE*0.12]
    rows = [[
        P('Invoice #', 8, WHITE, True, TA_CENTER),
        P('Customer',  8, WHITE, True, TA_CENTER),
        P('Date',      8, WHITE, True, TA_CENTER),
        P('Subtotal',  8, WHITE, True, TA_RIGHT),
        P('GST',       8, WHITE, True, TA_RIGHT),
        P('Total',     8, WHITE, True, TA_RIGHT),
        P('Status',    8, WHITE, True, TA_CENTER),
    ]]

    status_colors = {
        'paid': GREEN, 'pending': AMBER, 'issued': AMBER,
        'overdue': RED, 'draft': GRAY, 'cancelled': GRAY,
    }

    for inv in invoices:
        sc = status_colors.get(inv.status, GRAY)
        rows.append([
            P(inv.invoice_number, 8, colors.HexColor('#1d4ed8')),
            P(inv.customer.name if inv.customer else 'N/A', 8, BLACK),
            P(inv.issued_date.strftime('%d %b %Y'), 8, GRAY),
            P(f'Rs.{inv.subtotal:,.2f}', 8, BLACK, align=TA_RIGHT),
            P(f'Rs.{inv.gst_amount:,.2f}', 8, BLACK, align=TA_RIGHT),
            P(f'Rs.{inv.total:,.2f}', 8, BLACK, True, TA_RIGHT),
            P(inv.get_status_display(), 8, sc, True, TA_CENTER),
        ])

    tbl_style = TableStyle([
        ('BACKGROUND',    (0,0), (-1,0),  BRAND),
        ('BACKGROUND',    (0,1), (-1,-1), LGRAY),
        ('ROWBACKGROUNDS',(0,1), (-1,-1), [WHITE, LGRAY]),
        ('GRID',          (0,0), (-1,-1), 0.3, colors.HexColor('#E5E7EB')),
        ('TOPPADDING',    (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING',   (0,0), (-1,-1), 6),
        ('RIGHTPADDING',  (0,0), (-1,-1), 6),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
    ])

    story.append(Table(rows, colWidths=col_w, style=tbl_style, repeatRows=1))
    story.append(Spacer(1, 5*mm))

    # Totals row
    inv_list = list(invoices)
    grand_total    = sum(i.total      for i in inv_list)
    grand_subtotal = sum(i.subtotal   for i in inv_list)
    grand_gst      = sum(i.gst_amount for i in inv_list)

    summary = Table(
        [[
            P(f'Total Invoices: {len(inv_list)}', 9, BRAND, True),
            P(f'Subtotal: Rs.{grand_subtotal:,.2f}', 9, BRAND, True, TA_RIGHT),
            P(f'Total GST: Rs.{grand_gst:,.2f}', 9, BRAND, True, TA_RIGHT),
            P(f'Grand Total: Rs.{grand_total:,.2f}', 11, WHITE, True, TA_RIGHT),
        ]],
        colWidths=[USABLE*0.25, USABLE*0.25, USABLE*0.25, USABLE*0.25],
        style=TableStyle([
            ('BACKGROUND',    (3,0), (3,0), BRAND),
            ('BACKGROUND',    (0,0), (2,0), LGRAY),
            ('TOPPADDING',    (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('LEFTPADDING',   (0,0), (-1,-1), 8),
            ('RIGHTPADDING',  (0,0), (-1,-1), 8),
            ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
        ])
    )
    story.append(summary)
    story.append(Spacer(1, 4*mm))
    story.append(HRFlowable(width='100%', thickness=0.8, color=BRAND))

    doc.build(story)
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="billing_report.pdf"'
    return response


# Alias so the old export functions still resolve
def export_invoices_csv(invoices):
    return _export_csv(invoices)

def export_invoices_pdf(invoices):
    return _export_pdf(invoices, None, None, None)

# ============================================
# PLANS VIEW
# ============================================

@login_required(login_url='accounts:login')
def plans_list(request):
    return render(request, 'accounts/plans.html', {'page_title': 'Plans'})


@login_required(login_url='accounts:login')
@require_http_methods(["POST"])
def plan_signup(request):
    try:
        plan         = request.POST.get('plan', '').strip()
        company_name = request.POST.get('company_name', '').strip()
        full_name    = request.POST.get('full_name', '').strip()
        email        = request.POST.get('email', '').strip()
        phone        = request.POST.get('phone', '').strip()

        if not all([plan, company_name, full_name, email, phone]):
            return JsonResponse({'success': False, 'message': 'All fields are required'})

        user = request.user
        user.company_name = company_name
        user.phone = phone
        user.save()

        return JsonResponse({'success': True, 'message': f'Welcome to {plan} plan!', 'redirect_url': request.build_absolute_uri(reverse('accounts:dashboard'))})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})


# ============================================
# SETTINGS VIEW
# ============================================

@login_required(login_url='accounts:login')
def settings_view(request):
    user = request.user
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'update_profile':
            user.first_name   = request.POST.get('first_name', '').strip()
            user.last_name    = request.POST.get('last_name', '').strip()
            user.phone        = request.POST.get('phone', '').strip()
            user.company_name = request.POST.get('company_name', '').strip()
            if 'profile_photo' in request.FILES:
                user.profile_photo = request.FILES['profile_photo']
            user.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('accounts:settings')

        elif action == 'change_password':
            from django.contrib.auth import update_session_auth_hash
            current = request.POST.get('current_password', '')
            new_pw  = request.POST.get('new_password', '')
            confirm = request.POST.get('confirm_password', '')
            if not user.check_password(current):
                messages.error(request, 'Current password is incorrect.')
            elif new_pw != confirm:
                messages.error(request, 'Passwords do not match.')
            elif len(new_pw) < 8:
                messages.error(request, 'Password must be at least 8 characters.')
            else:
                user.set_password(new_pw)
                user.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Password changed successfully!')
            return redirect('accounts:settings')

        elif action == 'update_company':
            from accounts.models import CompanySettings
            company_name = request.POST.get('company_name', '').strip()
            gstin        = request.POST.get('gstin', '').strip() or None
            pan          = request.POST.get('pan', '').strip() or None
            address      = request.POST.get('address', '').strip()
            city         = request.POST.get('city', '').strip()
            state        = request.POST.get('state', '').strip()
            pincode      = request.POST.get('pincode', '').strip()
            phone        = request.POST.get('phone', '').strip()
            email        = request.POST.get('email', '').strip()
            website      = request.POST.get('website', '').strip() or None

            try:
                company, created = CompanySettings.objects.get_or_create(user=user)
                company.company_name = company_name
                company.gstin   = gstin
                company.pan     = pan
                company.address = address
                company.city    = city
                company.state   = state
                company.pincode = pincode
                company.phone   = phone
                company.email   = email
                company.website = website
                if 'logo' in request.FILES:
                    company.logo = request.FILES['logo']
                company.save()
                messages.success(request, '✅ Company settings saved successfully!')
            except Exception as e:
                messages.error(request, f'❌ Error saving company settings: {str(e)}')
            return redirect('accounts:settings')

        elif action == 'delete_account':
            if request.POST.get('confirm_delete') == 'DELETE':
                user.delete()
                return redirect('accounts:login')
            else:
                messages.error(request, 'Type DELETE to confirm.')
            return redirect('accounts:settings')

   # Load existing company settings or create empty instance
    try:
        company = user.company_settings
    except Exception:
        company = None

    context = {
        'page_title': 'Settings',
        'user': user,
        'company': company,
    }
    return render(request, 'accounts/settings.html', context)
