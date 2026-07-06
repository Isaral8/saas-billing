import pytest
from django.test import Client
from django.urls import reverse
from accounts.models import CustomUser, Customer, Invoice
from decimal import Decimal

@pytest.mark.django_db
class TestAuthViews:
    """Test authentication views"""
    
    def setup_method(self):
        """Setup before each test"""
        self.client = Client()
        self.user = CustomUser.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
    
    def test_signup_page_loads(self):
        """Test signup page loads"""
        response = self.client.get(reverse('signup'))
        assert response.status_code == 200
        print("✅ Signup page loads")
    
    def test_login_page_loads(self):
        """Test login page loads"""
        response = self.client.get(reverse('login'))
        assert response.status_code == 200
        print("✅ Login page loads")
    
    def test_home_page_loads(self):
        """Test home page loads"""
        response = self.client.get(reverse('home'))
        assert response.status_code in [200, 302]
        print("✅ Home page loads")


@pytest.mark.django_db
class TestDashboardView:
    """Test dashboard view"""
    
    def setup_method(self):
        """Setup before each test"""
        self.client = Client()
        self.user = CustomUser.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
    
    def test_dashboard_page_exists(self):
        """Test dashboard page exists"""
        response = self.client.get(reverse('dashboard'))
        # Should redirect to login or show 200
        assert response.status_code in [302, 200]
        print("✅ Dashboard page exists")


@pytest.mark.django_db
class TestInvoiceViews:
    """Test invoice views"""
    
    def setup_method(self):
        """Setup before each test"""
        self.client = Client()
        self.user = CustomUser.objects.create_user(
            email='user@example.com',
            password='pass123',
            first_name='Test',
            last_name='User'
        )
        self.invoice = Invoice.objects.create(
            user=self.user,
            invoice_number='INV-001',
            subtotal=Decimal('1000.00'),
            gst_amount=Decimal('180.00'),
            total=Decimal('1180.00'),
            status='issued'
        )
    
    def test_invoice_list_page(self):
        """Test invoice list page loads"""
        response = self.client.get(reverse('invoices_list'))
        # Should redirect to login or show 200
        assert response.status_code in [302, 200]
        print("✅ Invoice list page loads")
    
    def test_invoice_detail_page(self):
        """Test invoice detail page"""
        response = self.client.get(reverse('invoice_detail', kwargs={'pk': self.invoice.pk}))
        # Should redirect to login or show 200
        assert response.status_code in [302, 200]
        print("✅ Invoice detail page loads")


@pytest.mark.django_db
class TestTicketViews:
    """Test support ticket views"""
    
    def setup_method(self):
        """Setup before each test"""
        self.client = Client()
        self.user = CustomUser.objects.create_user(
            email='user@example.com',
            password='pass123'
        )
    
    def test_ticket_list_page(self):
        """Test ticket list page"""
        response = self.client.get(reverse('tickets_list'))
        assert response.status_code in [302, 200]
        print("✅ Ticket list page loads")


@pytest.mark.django_db
class TestCustomerViews:
    """Test customer views"""
    
    def setup_method(self):
        """Setup before each test"""
        self.client = Client()
        self.user = CustomUser.objects.create_user(
            email='user@example.com',
            password='pass123'
        )
    
    def test_customer_list_page(self):
        """Test customer list page"""
        response = self.client.get(reverse('customer_list'))
        assert response.status_code in [302, 200]
        print("✅ Customer list page loads")