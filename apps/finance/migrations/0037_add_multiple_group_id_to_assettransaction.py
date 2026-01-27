# Generated manually on 2026-01-26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0036_alter_cashflowitem_calculation_rules'),
    ]

    operations = [
        migrations.AddField(
            model_name='assettransaction',
            name='multiple_group_id',
            field=models.UUIDField(blank=True, help_text='UUID que vincula as transações de uma transação múltipla de ativos', null=True, verbose_name='ID do grupo de transação múltipla'),
        ),
    ]
