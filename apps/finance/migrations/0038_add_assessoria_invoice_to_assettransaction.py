# Generated manually on 2026-01-26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0037_add_multiple_group_id_to_assettransaction'),
    ]

    operations = [
        migrations.AddField(
            model_name='assettransaction',
            name='assessoria',
            field=models.BooleanField(default=False, help_text='Indica se há assessoria nesta transação', verbose_name='Assessoria'),
        ),
        migrations.AddField(
            model_name='assettransaction',
            name='invoice',
            field=models.CharField(blank=True, help_text='Número da nota fiscal', max_length=100, verbose_name='Nota Fiscal'),
        ),
    ]
