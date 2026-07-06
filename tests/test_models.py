import pytest
from django.utils import timezone
from decimal import Decimal
from accounts.models import CustomUser, Customer, Invoice, InvoiceItem, Product, SupportTicket

# ============================================
# TEST: CustomUser Model
# ============================================

@pytest.mark.django_db
class TestCustomUserModel:
    """Test CustomUser creation and methods"""
    
    def test_create_custom_user(self):
        """Test creating a CustomUser"""
        user = CustomUser.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User',
            company_name='Test Company'
        )
        assert user.email == 'test@example.com'
        assert user.first_name == 'Test'
        assert user.is_active == True
        print(f"✅ Created user: {user.email}")
    
    def test_user_with_gstin(self):
        """Test user with GST details"""
        user = CustomUser.objects.create_user(
            email='gst@example.com',
            password='pass123',
            gstin='12ABCDE1234F1Z5',
            pan_number='AAAPA1234A',
            business_state='Karnataka'
        )
        assert user.gstin == '12ABCDE1234F1Z5'
        assert user.business_state == 'Karnataka'
        print(f"✅ Created GST user: {user.gstin}")
    
    def test_user_with_roles(self):
        """Test user roles"""
        owner = CustomUser.objects.create_user(
            email='owner@example.com',
            password='pass123',
            role='owner'
        )
        assert owner.role == 'owner'
        print(f"✅ Created owner: {owner.role}")


# ============================================
# TEST: Customer Model
# ============================================

@pytest.mark.django_db
class TestCustomerModel:
    """Test Customer creation"""
    
    def test_create_customer(self):
        """Test creating a customer"""
        user = CustomUser.objects.create_user(
            email='user@example.com',
            password='pass123'
        )
        customer = Customer.objects.create(
            user=user,
            name='ABC Corporation',
            email='abc@example.com',
            company='ABC Corp',
            gstin='12ABCDE1234F1Z5',
            state='Karnataka'
        )
        assert customer.name == 'ABC Corporation'
        assert customer.gstin == '12ABCDE1234F1Z5'
        assert customer.user == user
        print(f"✅ Created customer: {customer.name}")


# ============================================
# TEST: Invoice Model
# ============================================

@pytest.mark.django_db
class TestInvoiceModel:
    """Test Invoice creation and GST calculations"""
    
    def test_create_invoice(self):
        """Test creating an invoice"""
        user = CustomUser.objects.create_user(
            email='user@example.com',
            password='pass123',
            gstin='12ABCDE1234F1Z5'
        )
        invoice = Invoice.objects.create(
            user=user,
            invoice_number='INV-001',
            subtotal=Decimal('1000.00'),
            gst_rate=Decimal('18.00'),
            gst_amount=Decimal('180.00'),
            total=Decimal('1180.00'),
            status='issued'
        )
        assert invoice.invoice_number == 'INV-001'
        assert invoice.total == Decimal('1180.00')
        assert invoice.status == 'issued'
        print(f"✅ Created invoice: {invoice.invoice_number}")
    
    def test_invoice_gst_calculation(self):
        """Test GST calculation is correct"""
        user = CustomUser.objects.create_user(
            email='user@example.com',
            password='pass123'
        )
        
        # Subtotal: ₹1000, GST 18% = ₹180
        invoice = Invoice.objects.create(
            user=user,
            invoice_number='INV-GST-001',
            subtotal=Decimal('1000.00'),
            gst_rate=Decimal('18.00'),
            gst_amount=Decimal('180.00'),
            cgst_amount=Decimal('90.00'),  # 9%
            sgst_amount=Decimal('90.00'),  # 9%
            total=Decimal('1180.00')
        )
        
        # Verify calculation
        assert invoice.subtotal + invoice.gst_amount == invoice.total
        assert invoice.cgst_amount + invoice.sgst_amount == invoice.gst_amount
        print(f"✅ GST calculation correct: {invoice.total}")


# ============================================
# TEST: Product Model
# ============================================

@pytest.mark.django_db
class TestProductModel:
    """Test Product creation"""
    
    def test_create_product(self):
        """Test creating a product"""
        user = CustomUser.objects.create_user(
            email='user@example.com',
            password='pass123'
        )
        product = Product.objects.create(
            user=user,
            name='Laptop',
            price=Decimal('50000.00'),
            unit='pcs',
            hsn_sac_code='8471',
            gst_rate=Decimal('5.00')
        )
        assert product.name == 'Laptop'
        assert product.price == Decimal('50000.00')
        assert product.hsn_sac_code == '8471'
        print(f"✅ Created product: {product.name}")


# ============================================
# TEST: SupportTicket Model
# ============================================

@pytest.mark.django_db
class TestSupportTicketModel:
    """Test Support Ticket creation"""
    
    def test_create_ticket(self):
        """Test creating a support ticket"""
        user = CustomUser.objects.create_user(
            email='user@example.com',
            password='pass123'
        )
        ticket = SupportTicket.objects.create(
            user=user,
            title='Invoice Not Received',
            description='I did not receive the invoice email',
            status='open',
            priority='medium'
        )
        assert ticket.title == 'Invoice Not Received'
        assert ticket.status == 'open'
        assert ticket.priority == 'medium'
        print(f"✅ Created ticket: {ticket.title}")