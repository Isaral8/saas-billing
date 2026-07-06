import pytest
from django.utils import timezone
from accounts.models import CustomUser, Customer, Invoice, InvoiceItem, Product
from decimal import Decimal

@pytest.mark.django_db
class TestInvoiceWorkflow:
    """Test complete invoice creation workflow"""
    
    def test_create_invoice_with_items(self):
        """Test creating invoice with line items"""
        # Step 1: Create user (seller)
        user = CustomUser.objects.create_user(
            email='seller@example.com',
            password='pass123',
            gstin='12ABCDE1234F1Z5',
            company_name='My Company'
        )
        
        # Step 2: Create customer (buyer)
        customer = Customer.objects.create(
            user=user,
            name='ABC Corp',
            email='buyer@example.com',
            gstin='23XYZAB1234K1Z0',
            state='Tamil Nadu'
        )
        
        # Step 3: Create product
        product = Product.objects.create(
            user=user,
            name='Software License',
            price=Decimal('5000.00'),
            hsn_sac_code='6212',
            gst_rate=Decimal('18.00')
        )
        
        # Step 4: Create invoice
        invoice = Invoice.objects.create(
            user=user,
            customer=customer,
            invoice_number='INV-EMP-001',
            status='draft'
        )
        
        # Step 5: Add line items
        item = InvoiceItem.objects.create(
            invoice=invoice,
            product=product,
            quantity=2,
            rate=Decimal('5000.00'),
            hsn_sac_code='6212',
            gst_rate=Decimal('18.00'),
            subtotal=Decimal('10000.00'),
            gst_amount=Decimal('1800.00'),
            cgst_amount=Decimal('900.00'),
            sgst_amount=Decimal('900.00'),
            total=Decimal('11800.00')
        )
        
        # Step 6: Calculate invoice totals
        invoice.calculate_from_items()
        invoice.status = 'issued'
        invoice.save()
        
        # Verify
        assert invoice.status == 'issued'
        assert invoice.subtotal == Decimal('10000.00')
        assert invoice.total == Decimal('11800.00')
        assert invoice.customer.gstin == '23XYZAB1234K1Z0'
        
        print("✅ Complete invoice workflow test passed!")
    
    def test_ticket_creation_workflow(self):
        """Test complete ticket creation workflow"""
        # Step 1: Create user
        user = CustomUser.objects.create_user(
            email='support@example.com',
            password='pass123'
        )
        
        # Step 2: Create ticket
        from accounts.models import SupportTicket
        ticket = SupportTicket.objects.create(
            user=user,
            title='Payment Issue',
            description='Unable to process payment',
            status='open',
            priority='high'
        )
        
        # Step 3: Update ticket status
        ticket.status = 'in_progress'
        ticket.save()
        
        # Verify
        assert ticket.status == 'in_progress'
        assert ticket.priority == 'high'
        print("✅ Complete ticket workflow test passed!")