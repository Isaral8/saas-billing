from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy

app_name = 'accounts'

urlpatterns = [
    # ════════════════════════════════════════════════════════════════════
    # HOME & DASHBOARD
    # ════════════════════════════════════════════════════════════════════
    path('', views.home_view, name='home'),
    path('dashboard/', views.dashboard_view, name='dashboard'),

    # ════════════════════════════════════════════════════════════════════
    # AUTHENTICATION
    # ════════════════════════════════════════════════════════════════════
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('logout/', views.logout_view, name='logout'),

    # ════════════════════════════════════════════════════════════════════
    # PASSWORD RESET
    # ════════════════════════════════════════════════════════════════════
    path('password-reset/', 
        auth_views.PasswordResetView.as_view(
            template_name='accounts/password_reset.html',
            email_template_name='accounts/password_reset_email.html',
            subject_template_name='accounts/password_reset_subject.txt',
            success_url=reverse_lazy('accounts:password_reset_done')
        ), 
        name='password_reset'
    ),

    path('password-reset/done/', 
        auth_views.PasswordResetDoneView.as_view(
            template_name='accounts/password_reset_done.html'
        ), 
        name='password_reset_done'
    ),

    path('password-reset-confirm/<uidb64>/<token>/', 
        auth_views.PasswordResetConfirmView.as_view(
            template_name='accounts/password_reset_confirm.html',
            success_url=reverse_lazy('accounts:password_reset_complete')
        ), 
        name='password_reset_confirm'
    ),

    path('password-reset-complete/', 
        auth_views.PasswordResetCompleteView.as_view(
            template_name='accounts/password_reset_complete.html'
        ), 
        name='password_reset_complete'
    ),

    # ════════════════════════════════════════════════════════════════════
    # CUSTOMERS
    # ════════════════════════════════════════════════════════════════════
    path('customers/', views.customer_list, name='customer_list'),
    path('customers/search/', views.customer_search, name='customer_search'),
    path('customers/create/', views.add_customer, name='create_customer'),
    path('customers/<uuid:customer_id>/', views.get_customer_details, name='get_customer_details'),
    path('customers/<uuid:customer_id>/edit/', views.customer_edit, name='customer_edit'),
    path('customers/<uuid:customer_id>/delete/', views.delete_customer, name='delete_customer'),
    path('customers/<uuid:customer_id>/toggle-status/', views.toggle_customer_status, name='toggle_customer_status'),
    # ════════════════════════════════════════════════════════════════════
    # INVOICES
    # ════════════════════════════════════════════════════════════════════
    path('invoices/', views.invoices_list, name='invoices'),
    path('create-invoice/', views.create_invoice, name='create_invoice'),
    path('invoices/<uuid:invoice_id>/edit/', views.update_invoice, name='update_invoice'),
    path('invoices/<uuid:invoice_id>/delete/', views.delete_invoice, name='delete_invoice'),
    path('invoices/<uuid:invoice_id>/pdf/', views.generate_invoice_pdf, name='invoice_pdf'),
    path('invoices/<uuid:invoice_id>/email/', views.email_invoice, name='email_invoice'),

    # ════════════════════════════════════════════════════════════════════
    # TICKETS
    # ════════════════════════════════════════════════════════════════════
    path('tickets/', views.tickets_list, name='tickets'),
    path('create-ticket/', views.create_ticket, name='create_ticket'),
    path('tickets/<uuid:ticket_id>/', views.ticket_detail_view, name='ticket_detail'),
    path('tickets/<uuid:ticket_id>/update/', views.update_ticket_status_view, name='update_ticket'),

    # ════════════════════════════════════════════════════════════════════
    # REPORTS & PLANS
    # ════════════════════════════════════════════════════════════════════
    path('reports/', views.billing_reports, name='reports'),
    path('plans/', views.plans_list, name='plans'),
    path('plans/signup/', views.plan_signup, name='plan_signup'),

    # ════════════════════════════════════════════════════════════════════
    # SETTINGS
    # ════════════════════════════════════════════════════════════════════
    path('settings/', views.settings_view, name='settings'),
]
