from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Q, Sum, Count
from django.core.paginator import Paginator
from accounts.models import Invoice, Subscription, CustomUser, Customer, SupportTicket
from decimal import Decimal
from django.http import JsonResponse
from .forms import TicketReplyForm


# ════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ════════════════════════════════════════════════════════════════════════════

@login_required(login_url='accounts:login')
def billing_dashboard_view(request):
    """Billing dashboard showing invoices and subscriptions."""
    user = request.user
    
    # Recent invoices
    invoices = Invoice.objects.filter(user=user).order_by('-issued_date')[:5]
    
    # Counts
    total_invoices = Invoice.objects.filter(user=user).count()
    paid_invoices = Invoice.objects.filter(user=user, status='paid').count()
    pending_invoices = Invoice.objects.filter(user=user, status__in=['issued', 'pending', 'overdue']).count()
    
    # Subscription
    subscriptions = Subscription.objects.filter(user=user)
    
    context = {
        'page_title': 'Billing Dashboard',
        'invoices': invoices,
        'subscriptions': subscriptions,
        'total_invoices': total_invoices,
        'paid_invoices': paid_invoices,
        'pending_invoices': pending_invoices,
    }
    return render(request, 'billing/dashboard.html', context)


# ════════════════════════════════════════════════════════════════════════════
# CUSTOMERS - LIST, DETAIL, CREATE, EDIT, DELETE, SEARCH
# ════════════════════════════════════════════════════════════════════════════

@login_required(login_url='accounts:login')
def customer_list(request):
    """List all customers with pagination and search."""
    user = request.user
    
    # Get search query
    search_query = request.GET.get('search', '').strip()
    
    # Base queryset
    customers = Customer.objects.filter(user=user)
    
    # Search if query provided
    if search_query:
        customers = customers.filter(
            Q(name__icontains=search_query) |
            Q(company__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone__icontains=search_query) |
            Q(gstin__icontains=search_query)
        )
    
    # Order by newest first
    customers = customers.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(customers, 10)  # 10 per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_title': 'Customers',
        'page_obj': page_obj,
        'customers': page_obj.object_list,
        'total_customers': Customer.objects.filter(user=user).count(),
        'active_customers': Customer.objects.filter(user=user, is_active=True).count(),
        'search_query': search_query,
    }
    return render(request, 'billing/customers.html', context)


@login_required(login_url='accounts:login')
def customer_search(request):
    """AJAX search for customers."""
    query = request.GET.get('q', '').strip()
    user = request.user
    
    if len(query) < 2:
        return render(request, 'billing/customer_search_results.html', {'customers': []})
    
    customers = Customer.objects.filter(user=user).filter(
        Q(name__icontains=query) |
        Q(company__icontains=query) |
        Q(email__icontains=query) |
        Q(phone__icontains=query) |
        Q(gstin__icontains=query)
    )[:10]
    
    context = {'customers': customers, 'query': query}
    return render(request, 'billing/customer_search_results.html', context)


@login_required(login_url='accounts:login')
@require_http_methods(["GET", "POST"])
def customer_create(request):
    """Create a new customer."""
    user = request.user
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        company = request.POST.get('company', '').strip()
        gstin = request.POST.get('gstin', '').strip()
        state = request.POST.get('state', '').strip()
        address = request.POST.get('address', '').strip()
        notes = request.POST.get('notes', '').strip()
        
        # Validation
        if not name or not email:
            messages.error(request, '❌ Name and Email are required.')
            return render(request, 'billing/customer_form.html')
        
        # Check if customer already exists
        if Customer.objects.filter(user=user, email=email).exists():
            messages.error(request, f'❌ Customer with email {email} already exists.')
            return render(request, 'billing/customer_form.html')
        
        try:
            customer = Customer.objects.create(
                user=user,
                name=name,
                email=email,
                phone=phone,
                company=company,
                gstin=gstin,
                state=state,
                address=address,
                notes=notes,
                is_active=True,
            )
            messages.success(request, f'✅ Customer {name} created successfully!')
            return redirect('billing:customer_detail', customer_id=customer.id)
        
        except Exception as e:
            messages.error(request, f'❌ Error creating customer: {str(e)}')
    
    context = {'page_title': 'Add New Customer'}
    return render(request, 'billing/customer_form.html', context)


@login_required(login_url='accounts:login')
def customer_detail(request, customer_id):
    """View customer details and related data."""
    user = request.user
    customer = get_object_or_404(Customer, id=customer_id, user=user)
    
    # Get related data
    invoices = Invoice.objects.filter(customer=customer).order_by('-issued_date')
    total_invoices = invoices.count()
    paid_invoices = invoices.filter(status='paid').count()
    pending_invoices = invoices.filter(status__in=['issued', 'pending', 'overdue']).count()
    
    # Calculate total spent
    total_spent = sum([inv.total for inv in invoices.filter(status='paid')]) if paid_invoices > 0 else 0
    
    # Get related tickets
    tickets = SupportTicket.objects.filter(customer_email=customer.email).order_by('-created_at')[:5]
    
    context = {
        'page_title': f'Customer - {customer.name}',
        'customer': customer,
        'invoices': invoices[:10],  # Last 10 invoices
        'total_invoices': total_invoices,
        'paid_invoices': paid_invoices,
        'pending_invoices': pending_invoices,
        'total_spent': total_spent,
        'tickets': tickets,
    }
    return render(request, 'billing/customer_detail.html', context)


@login_required(login_url='accounts:login')
@require_http_methods(["GET", "POST"])
def customer_edit(request, customer_id):
    """Edit customer information."""
    user = request.user
    customer = get_object_or_404(Customer, id=customer_id, user=user)
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        company = request.POST.get('company', '').strip()
        gstin = request.POST.get('gstin', '').strip()
        state = request.POST.get('state', '').strip()
        address = request.POST.get('address', '').strip()
        notes = request.POST.get('notes', '').strip()
        
        # Validation
        if not name or not email:
            messages.error(request, '❌ Name and Email are required.')
            return render(request, 'billing/customer_form.html', {'customer': customer})
        
        # Check if email already used by another customer
        if Customer.objects.filter(user=user, email=email).exclude(id=customer.id).exists():
            messages.error(request, f'❌ Email {email} is already used by another customer.')
            return render(request, 'billing/customer_form.html', {'customer': customer})
        
        try:
            customer.name = name
            customer.email = email
            customer.phone = phone
            customer.company = company
            customer.gstin = gstin
            customer.state = state
            customer.address = address
            customer.notes = notes
            customer.save()
            messages.success(request, f'✅ Customer {name} updated successfully!')
            return redirect('billing:customer_detail', customer_id=customer.id)
        
        except Exception as e:
            messages.error(request, f'❌ Error updating customer: {str(e)}')
    
    context = {
        'page_title': f'Edit Customer - {customer.name}',
        'customer': customer,
        'is_edit': True,
    }
    return render(request, 'billing/customer_form.html', context)


@login_required(login_url='accounts:login')
@require_http_methods(["POST"])
def customer_delete(request, customer_id):
    """Delete a customer."""
    user = request.user
    customer = get_object_or_404(Customer, id=customer_id, user=user)
    
    # Check if customer has invoices
    invoice_count = Invoice.objects.filter(customer=customer).count()
    
    if invoice_count > 0:
        messages.error(request, f'❌ Cannot delete customer with {invoice_count} invoice(s). Archive instead.')
        return redirect('billing:customer_detail', customer_id=customer.id)
    
    try:
        customer_name = customer.name
        customer.delete()
        messages.success(request, f'✅ Customer {customer_name} deleted successfully!')
        return redirect('billing:customer_list')
    
    except Exception as e:
        messages.error(request, f'❌ Error deleting customer: {str(e)}')
        return redirect('billing:customer_detail', customer_id=customer.id)


# ════════════════════════════════════════════════════════════════════════════
# INVOICES
# ════════════════════════════════════════════════════════════════════════════

@login_required(login_url='accounts:login')
def invoices_list(request):
    """List all invoices."""
    user = request.user
    invoices = Invoice.objects.filter(user=user).order_by('-issued_date')
    
    # Pagination
    paginator = Paginator(invoices, 15)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_title': 'Invoices',
        'page_obj': page_obj,
        'invoices': page_obj.object_list,
        'total_invoices': Invoice.objects.filter(user=user).count(),
    }
    return render(request, 'billing/invoices.html', context)


@login_required(login_url='accounts:login')
@require_http_methods(["GET", "POST"])
def create_invoice(request):
    """Create a new invoice."""
    user = request.user
    customers = Customer.objects.filter(user=user)
    
    if request.method == 'POST':
        try:
            customer_id = request.POST.get('customer')
            invoice_number = request.POST.get('invoice_number', '').strip()
            issued_date = request.POST.get('issued_date')
            due_date = request.POST.get('due_date')
            amount = request.POST.get('amount', '0')
            gst_rate = request.POST.get('gst_rate', '18')
            description = request.POST.get('description', '').strip()
            
            # Validation
            if not all([customer_id, invoice_number, amount]):
                messages.error(request, '❌ Please fill in all required fields.')
                context = {'customers': customers, 'today': timezone.now().date()}
                return render(request, 'billing/create_invoice.html', context)
            
            # Get customer
            customer = get_object_or_404(Customer, id=customer_id, user=user)
            
            # Check if invoice number already exists
            if Invoice.objects.filter(user=user, invoice_number=invoice_number).exists():
                messages.error(request, f'❌ Invoice number {invoice_number} already exists.')
                context = {'customers': customers, 'today': timezone.now().date()}
                return render(request, 'billing/create_invoice.html', context)
            
            # Create invoice
            invoice = Invoice.objects.create(
                user=user,
                customer=customer,
                invoice_number=invoice_number,
                subtotal=Decimal(str(amount)),
                gst_rate=Decimal(str(gst_rate)),
                issued_date=issued_date if issued_date else timezone.now().date(),
                due_date=due_date if due_date else None,
                description=description,
                status='draft',
            )
            
            messages.success(request, f'✅ Invoice {invoice_number} created! Total: ₹{invoice.total}')
            return redirect('billing:invoices')
        
        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')
    
    context = {
        'page_title': 'Create Invoice',
        'customers': customers,
        'today': timezone.now().date(),
    }
    return render(request, 'billing/create_invoice.html', context)


@login_required(login_url='accounts:login')
def invoice_detail(request, invoice_id):
    """View invoice details."""
    user = request.user
    invoice = get_object_or_404(Invoice, id=invoice_id, user=user)
    
    context = {
        'page_title': f'Invoice - {invoice.invoice_number}',
        'invoice': invoice,
    }
    return render(request, 'billing/invoice_detail.html', context)


@login_required(login_url='accounts:login')
@require_http_methods(["GET", "POST"])
def update_invoice(request, invoice_id):
    """Edit invoice."""
    user = request.user
    invoice = get_object_or_404(Invoice, id=invoice_id, user=user)
    customers = Customer.objects.filter(user=user)
    
    if request.method == 'POST':
        try:
            invoice.customer_id = request.POST.get('customer')
            invoice.invoice_number = request.POST.get('invoice_number', '').strip()
            invoice.subtotal = Decimal(str(request.POST.get('amount', '0')))
            invoice.gst_rate = Decimal(str(request.POST.get('gst_rate', '18')))
            invoice.description = request.POST.get('description', '').strip()
            invoice.save()
            
            messages.success(request, f'✅ Invoice {invoice.invoice_number} updated!')
            return redirect('billing:invoice_detail', invoice_id=invoice.id)
        
        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')
    
    context = {
        'page_title': f'Edit Invoice - {invoice.invoice_number}',
        'invoice': invoice,
        'customers': customers,
        'is_edit': True,
    }
    return render(request, 'billing/create_invoice.html', context)


@login_required(login_url='accounts:login')
@require_http_methods(["POST"])
def delete_invoice(request, invoice_id):
    """Delete invoice."""
    user = request.user
    invoice = get_object_or_404(Invoice, id=invoice_id, user=user)
    
    invoice_number = invoice.invoice_number
    invoice.delete()
    messages.success(request, f'✅ Invoice {invoice_number} deleted!')
    return redirect('billing:invoices')


@login_required(login_url='accounts:login')
def generate_invoice_pdf(request, invoice_id):
    """Generate invoice PDF."""
    from django.http import HttpResponse
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from io import BytesIO
    
    user = request.user
    invoice = get_object_or_404(Invoice, id=invoice_id, user=user)
    
    # Create PDF
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    
    # Add content (simplified)
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, 750, f"Invoice {invoice.invoice_number}")
    
    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, 700, f"Customer: {invoice.customer.name}")
    pdf.drawString(50, 680, f"Amount: ₹{invoice.total}")
    pdf.drawString(50, 660, f"Date: {invoice.issued_date}")
    
    pdf.save()
    buffer.seek(0)
    
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Invoice_{invoice.invoice_number}.pdf"'
    return response


# ════════════════════════════════════════════════════════════════════════════
# TICKETS
# ════════════════════════════════════════════════════════════════════════════

@login_required(login_url='accounts:login')
def tickets_list(request):
    """List all support tickets."""
    user = request.user
    tickets = SupportTicket.objects.filter(user=user).order_by('-created_at')
    
    paginator = Paginator(tickets, 15)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_title': 'Support Tickets',
        'page_obj': page_obj,
        'tickets': page_obj.object_list,
    }
    return render(request, 'billing/tickets.html', context)


@login_required(login_url='accounts:login')
@require_http_methods(["GET", "POST"])
def create_ticket(request):
    """Create a support ticket."""
    user = request.user
    
    if request.method == 'POST':
        try:
            # Generate ticket number
            last_ticket = SupportTicket.objects.filter(user=user).order_by('-created_at').first()
            ticket_number = f"TKT-{timezone.now().year}-{(last_ticket.id.int % 10000) + 1 if last_ticket else 1:05d}"
            
            ticket = SupportTicket.objects.create(
                user=user,
                ticket_number=ticket_number,
                customer_name=request.POST.get('customer_name', '').strip(),
                customer_mobile=request.POST.get('customer_mobile', '').strip(),
                customer_email=request.POST.get('customer_email', '').strip(),
                subject=request.POST.get('subject', '').strip(),
                description=request.POST.get('description', '').strip(),
                priority=request.POST.get('priority', 'medium'),
            )
            
            messages.success(request, f'✅ Ticket {ticket_number} created!')
            return redirect('billing:ticket_detail', ticket_id=ticket.id)
        
        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')
    
    context = {'page_title': 'Create Ticket'}
    return render(request, 'billing/create_ticket.html', context)


@login_required
def ticket_detail(request, ticket_id):
    """Display ticket details with conversation history"""
    
    # Get the ticket
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    
    # Check if user has permission to view this ticket
    if ticket.customer != request.user and not request.user.is_staff:
        messages.error(request, "You don't have permission to view this ticket.")
        return redirect('tickets:list')
    
    # Get all replies for this ticket (ordered by creation time)
    replies = ticket.replies.all().order_by('created_at')
    
    # Initialize form
    form = TicketReplyForm()
    
    # Handle POST request (new reply)
    if request.method == 'POST':
        form = TicketReplyForm(request.POST)
        
        if form.is_valid():
            # Create the reply but don't save yet
            reply = form.save(commit=False)
            reply.ticket = ticket
            reply.user = request.user
            # Check if current user is staff
            reply.is_staff_reply = request.user.is_staff
            reply.save()
            
            # Show success message
            messages.success(request, "Your reply has been added successfully!")
            
            # Redirect to same page to show new reply
            return redirect('tickets:detail', ticket_id=ticket.id)
        else:
            # Form has errors, display them
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    
    context = {
        'ticket': ticket,
        'replies': replies,
        'form': form,
    }
    
    return render(request, 'tickets/ticket_detail.html', context)

@login_required(login_url='accounts:login')
@require_http_methods(["POST"])
def update_ticket_status_view(request, ticket_id):
    """Update ticket status."""
    user = request.user
    ticket = get_object_or_404(SupportTicket, id=ticket_id, user=user)
    
    status = request.POST.get('status')
    if status in ['open', 'in_progress', 'resolved', 'closed']:
        ticket.status = status
        ticket.save()
        messages.success(request, f'✅ Ticket status updated to {status}!')
    else:
        messages.error(request, '❌ Invalid status!')
    
    return redirect('billing:ticket_detail', ticket_id=ticket.id)


# ════════════════════════════════════════════════════════════════════════════
# PLANS & SUBSCRIPTIONS
# ════════════════════════════════════════════════════════════════════════════

@login_required(login_url='accounts:login')
def plans_list(request):
    """Display subscription plans."""
    plans = [
        {'id': 'free', 'name': 'Free', 'price': 0, 'features': ['Basic invoicing', '2 users', '50 invoices/month']},
        {'id': 'starter', 'name': 'Starter', 'price': 999, 'features': ['Advanced invoicing', '5 users', 'CRM', 'Unlimited invoices']},
        {'id': 'pro', 'name': 'Pro', 'price': 2499, 'features': ['Full access', '20 users', 'API', 'Custom branding', 'Priority support']},
        {'id': 'enterprise', 'name': 'Enterprise', 'price': 4999, 'features': ['Everything in Pro', '50+ users', 'Dedicated support', 'Custom integrations']},
    ]
    
    user_subscription = Subscription.objects.filter(user=request.user).first()
    context = {
        'page_title': 'Plans',
        'plans': plans,
        'user_subscription': user_subscription,
    }
    return render(request, 'billing/plans.html', context)


@login_required(login_url='accounts:login')
@require_http_methods(["POST"])
def plan_signup(request):
    """Upgrade/change plan."""
    plan_name = request.POST.get('plan', '').lower()
    
    if plan_name in ['free', 'starter', 'pro', 'enterprise']:
        try:
            Subscription.objects.update_or_create(
                user=request.user,
                defaults={'plan': plan_name, 'is_active': True}
            )
            messages.success(request, f'✅ Upgraded to {plan_name.title()} plan!')
        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')
    else:
        messages.error(request, '❌ Invalid plan!')
    
    return redirect('billing:plans')


@login_required(login_url='accounts:login')
def subscriptions_view(request):
    """List subscriptions."""
    subscriptions = Subscription.objects.filter(user=request.user)
    context = {
        'page_title': 'Subscriptions',
        'subscriptions': subscriptions,
    }
    return render(request, 'billing/subscriptions.html', context)


@login_required(login_url='accounts:login')
@require_http_methods(["POST"])
def cancel_subscription_view(request):
    """Cancel subscription."""
    try:
        subscription = Subscription.objects.filter(user=request.user).first()
        if subscription:
            subscription.is_active = False
            subscription.save()
            messages.success(request, '✅ Subscription cancelled!')
        else:
            messages.error(request, '❌ No active subscription found!')
    except Exception as e:
        messages.error(request, f'❌ Error: {str(e)}')
    
    return redirect('billing:subscriptions')


# ════════════════════════════════════════════════════════════════════════════
# REPORTS
# ════════════════════════════════════════════════════════════════════════════

@login_required(login_url='accounts:login')
def billing_reports(request):
    """Display billing reports."""
    user = request.user
    invoices = Invoice.objects.filter(user=user)
    
    paid_invoices = invoices.filter(status='paid')
    total_revenue = sum([inv.total for inv in paid_invoices]) if paid_invoices.exists() else 0
    pending_invoices = invoices.filter(status__in=['issued', 'pending', 'overdue']).count()
    
    context = {
        'page_title': 'Reports',
        'total_revenue': total_revenue,
        'pending_invoices': pending_invoices,
        'total_invoices': invoices.count(),
        'paid_invoices': paid_invoices.count(),
        'invoices': invoices.order_by('-issued_date'),
    }
    return render(request, 'billing/reports.html', context)