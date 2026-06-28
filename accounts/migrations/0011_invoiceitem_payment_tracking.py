# Generated migration for InvoiceItem payment tracking fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0010_add_product_category_and_upgrade_product'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoiceitem',
            name='amount_paid',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='invoiceitem',
            name='payment_status',
            field=models.CharField(
                choices=[('pending', 'Pending'), ('partial', 'Partial'), ('paid', 'Paid')],
                default='pending',
                max_length=20
            ),
            preserve_default=False,
        ),
        migrations.AddIndex(
            model_name='invoiceitem',
            index=models.Index(fields=['payment_status'], name='accounts_in_payment_idx'),
        ),
    ]