# Generated manually on 2026-01-20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0034_alter_budget_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='assettransaction',
            name='import_hash',
            field=models.CharField(blank=True, help_text='Hash MD5 gerado a partir dos dados originais da importação para prevenir duplicatas', max_length=32, null=True, unique=True, verbose_name='Hash de importação'),
        ),
    ]
