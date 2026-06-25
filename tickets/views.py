from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
import uuid
from datetime import datetime

# ✅ Import from accounts.models
from accounts.models import SupportTicket


@login_required
def tickets_view(request):
    """Display all support tickets for the logged-in user."""
    tickets = SupportTicket.objects.filter(user=request.user).order_by('-created_at')
    context = {'tickets': tickets, 'page_title': 'Support Tickets'}
    return render(request, 'accounts/tickets.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def create_ticket_view(request):
    """Create a new support ticket."""
    if request.method == 'POST':
        subject = request.POST.get('subject', '').strip()
        description = request.POST.get('description', '').strip()
        priority = request.POST.get('priority', 'medium').strip()
        customer_name = request.POST.get('customer_name', '').strip()
        customer_email = request.POST.get('customer_email', '').strip()
        customer_mobile = request.POST.get('customer_mobile', '').strip()

        # Validation
        if not all([subject, description, customer_name, customer_email, customer_mobile]):
            messages.error(request, 'All fields are required.')
            return render(request, 'accounts/create_ticket.html')

        # Generate unique ticket number
        ticket_number = f"TKT-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"

        # Create ticket
        SupportTicket.objects.create(
            user=request.user,
            subject=subject,
            description=description,
            priority=priority,
            customer_name=customer_name,
            customer_email=customer_email,
            customer_mobile=customer_mobile,
            ticket_number=ticket_number,
            status='open'
        )

        messages.success(request, f'✅ Support ticket {ticket_number} created successfully!')
        return redirect('accounts:tickets')  # ✅ Correct URL name

    return render(request, 'accounts/create_ticket.html', {'page_title': 'Create Ticket'})


@login_required
def ticket_detail_view(request, ticket_id):
    """View ticket details."""
    ticket = get_object_or_404(SupportTicket, id=ticket_id, user=request.user)
    context = {'ticket': ticket, 'page_title': f'Ticket {ticket.ticket_number}'}
    return render(request, 'accounts/ticket_detail.html', context)


@login_required
@require_http_methods(["POST"])
def update_ticket_status_view(request, ticket_id):
    """Update ticket status."""
    ticket = get_object_or_404(SupportTicket, id=ticket_id, user=request.user)
    new_status = request.POST.get('status', '').strip()

    valid_statuses = ['open', 'in_progress', 'resolved', 'closed']
    
    if new_status in valid_statuses:
        ticket.status = new_status
        ticket.save()
        messages.success(request, f'✅ Ticket status updated to {new_status}.')
    else:
        messages.error(request, 'Invalid status.')

    return redirect('tickets:detail', ticket_id=ticket_id)  # ✅ Correct URL name