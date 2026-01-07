# Generated manually for renaming registration_date to transaction_date

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0009_transaction_is_transfer_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='transaction',
            old_name='registration_date',
            new_name='transaction_date',
        ),
    ]

