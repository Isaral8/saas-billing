# accounts/forms.py

from django import forms
from django.core.exceptions import ValidationError
from accounts.models import CustomUser, Invoice, Customer, SupportTicket

# ============================================
# INVOICE FORM
# ============================================

class InvoiceForm(forms.ModelForm):

    class Meta:
        model  = Invoice
        fields = [
            'customer', 'invoice_number', 'issued_date', 'due_date',
            'hsn_sac_code', 'notes',
            # ↑ fixed: removed 'description' — model field is 'notes'
            'subtotal', 'gst_rate',
            'gst_amount', 'cgst_amount', 'sgst_amount', 'igst_amount',
            'total', 'status',
        ]
        widgets = {
            'customer':       forms.Select(attrs={'class': 'form-control', 'id': 'id_customer'}),
            'invoice_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. INV-2026-001',
            }),
            'issued_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'due_date':    forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'hsn_sac_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. 998314 (services) or 8471 (goods)',
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Additional notes for the customer...',
            }),
            'subtotal': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0',
                'id': 'id_subtotal',
            }),
            'gst_rate': forms.Select(
                choices=[
                    ('0',  '0% — Exempt'),
                    ('5',  '5%'),
                    ('12', '12%'),
                    ('18', '18%'),
                    ('28', '28%'),
                ],
                attrs={'class': 'form-control', 'id': 'id_gst_rate'},
            ),
            # ↓ All calculated fields hidden — populated by view, not user
            'gst_amount':  forms.HiddenInput(attrs={'id': 'id_gst_amount'}),
            'cgst_amount': forms.HiddenInput(attrs={'id': 'id_cgst_amount'}),
            'sgst_amount': forms.HiddenInput(attrs={'id': 'id_sgst_amount'}),
            'igst_amount': forms.HiddenInput(attrs={'id': 'id_igst_amount'}),
            'total':       forms.HiddenInput(attrs={'id': 'id_total'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'customer':       'Customer',
            'invoice_number': 'Invoice number',
            'issued_date':    'Invoice date',
            'due_date':       'Due date',
            'hsn_sac_code':   'HSN / SAC code',
            'notes':          'Notes',
            'subtotal':       'Amount (₹)',
            'gst_rate':       'GST rate',
            'status':         'Status',
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields['customer'].queryset = Customer.objects.filter(user=self.user)
        # ↓ KEY FIX: make all calculated fields not required
        for f in ('gst_amount', 'cgst_amount', 'sgst_amount', 'igst_amount', 'total'):
            self.fields[f].required = False

    def clean_invoice_number(self):
        number = self.cleaned_data.get('invoice_number', '').strip()
        if not number:
            raise forms.ValidationError('Invoice number is required.')
        return number

    def clean_subtotal(self):
        subtotal = self.cleaned_data.get('subtotal')
        if subtotal is not None and subtotal < 0:
            raise forms.ValidationError('Amount cannot be negative.')
        return subtotal


# ============================================
# SUPPORT TICKET FORM
# ============================================

class SupportTicketForm(forms.ModelForm):

    PRODUCT_CHOICES = [
        ('',                  'Select product / service'),
        ('tally_prime',       'Tally Prime'),
        ('isaral_billing',    'iSaral Billing'),
        ('isaral_crm',        'iSaral CRM'),
        ('isaral_hrms',       'iSaral HRMS'),
        ('digital_signature', 'Digital Signature'),
        ('ai_courses',        'AI Courses'),
        ('others',            'Others'),
    ]

    product = forms.ChoiceField(
        choices=PRODUCT_CHOICES,
        label='Product / service *',
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    tally_sno = forms.CharField(
        required=False,
        max_length=100,
        label='Tally serial number',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter Tally serial number',
        }),
    )
    other_product_name = forms.CharField(
        required=False,
        max_length=200,
        label='Other product name',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Specify product name',
        }),
    )

    class Meta:
        model  = SupportTicket
        fields = ['customer_name', 'customer_email', 'customer_mobile',
                  'subject', 'description', 'priority']
        widgets = {
            'customer_name':   forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full name'}),
            'customer_email':  forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@example.com'}),
            'customer_mobile': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+91 98765 43210'}),
            'subject':         forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Brief description'}),
            'description':     forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Describe the issue...'}),
            'priority':        forms.Select(attrs={'class': 'form-control'}),
        }

    def clean(self):
        cleaned_data       = super().clean()
        product            = cleaned_data.get('product')
        tally_sno          = cleaned_data.get('tally_sno', '').strip()
        other_product_name = cleaned_data.get('other_product_name', '').strip()

        if not product:
            self.add_error('product', 'Please select a product or service.')
        if product == 'tally_prime' and not tally_sno:
            self.add_error('tally_sno', 'Tally serial number is required for Tally Prime.')
        if product == 'others' and not other_product_name:
            self.add_error('other_product_name', 'Please specify the product name.')

        return cleaned_data


# ============================================
# PASSWORD CHANGE FORM
# ============================================

class ChangePasswordForm(forms.Form):

    current_password = forms.CharField(
        label='Current password',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Current password'}),
    )
    new_password = forms.CharField(
        label='New password',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Min. 8 characters'}),
    )
    confirm_password = forms.CharField(
        label='Confirm new password',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Repeat new password'}),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_current_password(self):
        pw = self.cleaned_data.get('current_password')
        if self.user and not self.user.check_password(pw):
            raise ValidationError('Current password is incorrect.')
        return pw

    def clean_new_password(self):
        pw = self.cleaned_data.get('new_password')
        if pw and len(pw) < 8:
            raise ValidationError('Password must be at least 8 characters.')
        return pw

    def clean(self):
        cleaned_data = super().clean()
        new_pw  = cleaned_data.get('new_password')
        confirm = cleaned_data.get('confirm_password')
        if new_pw and confirm and new_pw != confirm:
            raise ValidationError('New passwords do not match.')
        return cleaned_data