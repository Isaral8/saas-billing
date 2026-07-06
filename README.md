# 🎫 SaaS Ticket Management & Billing System

**A comprehensive Django-based ticketing and invoice management solution for Indian SMBs.**

---

## 📋 Project Overview

This is a **multi-tenant SaaS application** for:
- ✅ Creating & managing support tickets
- ✅ Generating GST-compliant invoices
- ✅ Managing customers with GSTIN support
- ✅ Tracking payments & subscriptions
- ✅ Email notifications & alerts
- ✅ Background job automation

---

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- PostgreSQL 12+
- Redis 6+
- Git

### Installation

```bash
# 1. Clone repository
git clone <your-repo-url>
cd saas-billing

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Mac/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create .env file
copy .env.example .env
# Edit .env with your database credentials

# 5. Run migrations
python manage.py migrate

# 6. Create superuser
python manage.py createsuperuser

# 7. Run development server
python manage.py runserver
```

**Access the app:** `http://localhost:8000`

---

## 📦 Tech Stack

- **Backend:** Django 4.2 + Django REST Framework
- **Database:** PostgreSQL
- **Task Queue:** Celery + Redis
- **Email:** SendGrid
- **Payments:** Razorpay (integrated, not yet live)
- **Multi-Tenancy:** django-tenants
- **Authentication:** django-allauth (email + OAuth)
- **Frontend:** Django Templates + Bootstrap 5

---

## 📁 Project Structure