# accounts/emails.py
# Automated email sending functions

from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from decimal import Decimal

# ============================================
# WELCOME EMAILS
# ============================================

def send_welcome_email(user):
    """Send welcome email right after signup"""
    try:
        subject = "Welcome to iSaral! "

        html_message = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <div style="text-align: center; margin-bottom: 30px; border-bottom: 2px solid #0066cc; padding-bottom: 20px;">
                        <h1 style="color: #0066cc; margin: 0;">iSaral</h1>
                        <p style="color: #666; margin: 5px 0 0 0;">Smart GST Billing & Business Software</p>
                    </div>
                    <p>Hi <strong>{user.first_name or user.email}</strong>,</p>
                    <p>Welcome to iSaral! Your account is ready to go.</p>
                    <div style="background: #f5f5f5; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <p style="margin: 0 0 10px 0;"><strong>Here's what you can do right now:</strong></p>
                        <p style="margin: 5px 0;">Add your first customer</p>
                        <p style="margin: 5px 0;">Create your first GST-compliant invoice</p>
                        <p style="margin: 5px 0;">Track payments and generate reports</p>
                    </div>
                    <div style="background: #e8f4ff; padding: 15px; border-radius: 8px; margin: 20px 0; text-align: center;">
                        <a href="http://127.0.0.1:8000/accounts/login/" style="background: #0066cc; color: white; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: 600;">Log In to iSaral</a>
                    </div>
                    <div style="border-top: 1px solid #ddd; padding-top: 20px; margin-top: 30px; text-align: center; color: #666; font-size: 12px;">
                        <p style="margin: 5px 0;"><strong>iSaral Business Solutions</strong><br>Email: {settings.DEFAULT_FROM_EMAIL}<br>Website: www.isaral.ai</p>
                        <p style="margin-top: 10px; color: #999;">This is an automated email. Please do not reply to this message.</p>
                    </div>
                </div>
            </body>
        </html>
        """

        send_mail(
            subject=subject,
            message='',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending welcome email: {str(e)}")
        return False


# ============================================
# INVOICE EMAILS
# ============================================

def send_invoice_email(invoice):
    """Send invoice to customer via email"""
    try:
        if not invoice.customer or not invoice.customer.email:
            return False

        subject = f"Invoice #{invoice.invoice_number} - iSaral"

        context = {
            'invoice_number': invoice.invoice_number,
            'customer_name': invoice.customer.name,
            'customer_email': invoice.customer.email,
            'amount': invoice.total,
            'subtotal': invoice.subtotal,
            'gst_amount': invoice.gst_amount,
            'issued_date': invoice.issued_date.strftime('%d %b %Y'),
            'due_date': invoice.due_date.strftime('%d %b %Y') if invoice.due_date else 'N/A',
            'company_name': 'iSaral Business Solutions',
            'company_email': settings.DEFAULT_FROM_EMAIL,
        }

        html_message = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <div style="text-align: center; margin-bottom: 30px; border-bottom: 2px solid #0066cc; padding-bottom: 20px;">
                        <h1 style="color: #0066cc; margin: 0;">iSaral</h1>
                        <p style="color: #666; margin: 5px 0 0 0;">Invoice #{context['invoice_number']}</p>
                    </div>
                    <p>Dear <strong>{context['customer_name']}</strong>,</p>
                    <p>Your invoice has been generated. Please find the details below:</p>
                    <div style="background: #f5f5f5; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr style="border-bottom: 1px solid #ddd;">
                                <td style="padding: 10px; font-weight: 600;">Invoice #:</td>
                                <td style="padding: 10px; text-align: right;">{context['invoice_number']}</td>
                            </tr>
                            <tr style="border-bottom: 1px solid #ddd;">
                                <td style="padding: 10px; font-weight: 600;">Issued Date:</td>
                                <td style="padding: 10px; text-align: right;">{context['issued_date']}</td>
                            </tr>
                            <tr style="border-bottom: 1px solid #ddd;">
                                <td style="padding: 10px; font-weight: 600;">Due Date:</td>
                                <td style="padding: 10px; text-align: right;">{context['due_date']}</td>
                            </tr>
                            <tr style="border-bottom: 2px solid #0066cc;">
                                <td style="padding: 10px; font-weight: 600;">Subtotal:</td>
                                <td style="padding: 10px; text-align: right;">Rs.{context['subtotal']:.2f}</td>
                            </tr>
                            <tr style="border-bottom: 2px solid #0066cc;">
                                <td style="padding: 10px; font-weight: 600;">GST ({invoice.gst_rate:.0f}%):</td>
                                <td style="padding: 10px; text-align: right;">Rs.{context['gst_amount']:.2f}</td>
                            </tr>
                            <tr style="background: #0066cc; color: white;">
                                <td style="padding: 12px; font-weight: 700; font-size: 16px;">Total Amount:</td>
                                <td style="padding: 12px; text-align: right; font-weight: 700; font-size: 16px;">Rs.{context['amount']:.2f}</td>
                            </tr>
                        </table>
                    </div>
                    <div style="background: #e8f4ff; padding: 15px; border-radius: 8px; margin: 20px 0; text-align: center;">
                        <p style="margin: 0;">Please review the invoice and make payment at your earliest convenience.</p>
                    </div>
                    <div style="border-top: 1px solid #ddd; padding-top: 20px; margin-top: 30px; text-align: center; color: #666; font-size: 12px;">
                        <p style="margin: 5px 0;"><strong>{context['company_name']}</strong><br>Email: {context['company_email']}<br>Website: www.isaral.ai</p>
                        <p style="margin-top: 10px; color: #999;">This is an automated email. Please do not reply to this message.</p>
                    </div>
                </div>
            </body>
        </html>
        """

        send_mail(
            subject=subject,
            message='',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invoice.customer.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending invoice email: {str(e)}")
        return False


def send_payment_confirmation_email(invoice):
    """Send payment confirmation email"""
    try:
        if not invoice.customer or not invoice.customer.email:
            return False

        subject = f"Payment Confirmed - Invoice #{invoice.invoice_number}"

        html_message = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <div style="text-align: center; margin-bottom: 30px; background: #d4edda; padding: 20px; border-radius: 8px; border-left: 4px solid #28a745;">
                        <h2 style="color: #28a745; margin: 0;">Payment Received</h2>
                        <p style="color: #155724; margin: 10px 0 0 0;">Thank you for your payment</p>
                    </div>
                    <p>Dear <strong>{invoice.customer.name}</strong>,</p>
                    <p>We have received your payment for Invoice <strong>#{invoice.invoice_number}</strong>.</p>
                    <div style="background: #f5f5f5; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <p style="margin: 0 0 10px 0;"><strong>Invoice Details:</strong></p>
                        <p style="margin: 5px 0;">Invoice #: {invoice.invoice_number}</p>
                        <p style="margin: 5px 0;">Amount: Rs.{invoice.total:.2f}</p>
                        <p style="margin: 5px 0;">Status: <span style="color: #28a745; font-weight: 600;">Paid</span></p>
                    </div>
                    <div style="border-top: 1px solid #ddd; padding-top: 20px; margin-top: 30px; text-align: center; color: #666; font-size: 12px;">
                        <p style="margin: 5px 0;">iSaral Business Solutions<br>Thank you for your business!</p>
                    </div>
                </div>
            </body>
        </html>
        """

        send_mail(
            subject=subject,
            message='',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invoice.customer.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending payment email: {str(e)}")
        return False


# ============================================
# SUPPORT TICKET EMAILS
# ============================================

def send_ticket_confirmation_email(ticket):
    """Send support ticket confirmation email"""
    try:
        if not ticket.customer_email:
            return False
        subject = f"Support Ticket #{ticket.ticket_number} - iSaral Support"

        html_message = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #0066cc;">Support Ticket Created</h2>
                    <p>Dear <strong>{ticket.customer_name}</strong>,</p>
                    <p>Your support ticket has been successfully created. Our team will review it shortly.</p>
                    <div style="background: #f5f5f5; padding: 20px; border-radius: 8px; margin: 20px 0;">
                          <p><strong>Ticket #:</strong> {ticket.ticket_number}</p>
                        <p><strong>Subject:</strong> {ticket.subject}</p>
                        <p><strong>Priority:</strong> {ticket.priority.upper()}</p>
                        <p><strong>Status:</strong> {ticket.status.upper()}</p>
                    </div>
                    <p>You will receive email updates as your ticket progresses.</p>
                    <div style="border-top: 1px solid #ddd; padding-top: 20px; margin-top: 30px; text-align: center; color: #666; font-size: 12px;">
                        <p>iSaral Support Team</p>
                    </div>
                </div>
            </body>
        </html>
        """

        send_mail(
            subject=subject,
            message='',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[ticket.customer_email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending ticket email: {str(e)}")
        return False
def send_ticket_update_email(ticket, update_message):
    """Send support ticket update email"""
    try:
        if not ticket.customer_email:
            return False

        subject = f"Update on Ticket #{ticket.ticket_number} - iSaral Support"
        html_message = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #0066cc;">Ticket Update</h2>
                    <p>Dear <strong>{ticket.customer_name}</strong>,</p>
                    <p>There's an update on your support ticket:</p>
                    <div style="background: #f5f5f5; padding: 20px; border-radius: 8px; margin: 20px 0;">
                          <p><strong>Ticket #:</strong> {ticket.ticket_number}</p>
                        <p><strong>Subject:</strong> {ticket.subject}</p>
                        <p><strong>Current Status:</strong> {ticket.status.upper()}</p>
                        <hr style="border: none; border-top: 1px solid #ddd; margin: 15px 0;">
                        <p><strong>Update:</strong></p>
                        <p>{update_message}</p>
                    </div>
                    <div style="border-top: 1px solid #ddd; padding-top: 20px; margin-top: 30px; text-align: center; color: #666; font-size: 12px;">
                        <p>iSaral Support Team</p>
                    </div>
                </div>
            </body>
        </html>
        """

        send_mail(
            subject=subject,
            message='',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[ticket.customer_email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending update email: {str(e)}")
        return False
