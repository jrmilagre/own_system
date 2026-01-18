# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0031_rename_finance_ass_operati_idx_finance_ass_operati_12aec4_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='budget',
            name='notes',
            field=models.TextField(blank=True, help_text='Anotações sobre o orçamento', null=True, verbose_name='Anotações'),
        ),
    ]
