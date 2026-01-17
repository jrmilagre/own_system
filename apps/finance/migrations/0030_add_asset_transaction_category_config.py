# Generated manually for asset transaction integration

from django.db import migrations, models
import django.db.models.deletion


def create_initial_configs(apps, schema_editor):
    """Cria configurações iniciais de categorias para transações de ativos"""
    AssetTransactionCategoryConfig = apps.get_model('finance', 'AssetTransactionCategoryConfig')
    Subcategory = apps.get_model('finance', 'Subcategory')
    Category = apps.get_model('finance', 'Category')
    
    # Criar categorias e subcategorias se não existirem
    # Categoria: Compra de investimento
    cat_compra, _ = Category.objects.get_or_create(category='Compra de investimento')
    subcat_fii, _ = Subcategory.objects.get_or_create(
        category=cat_compra,
        subcategory='Fundo imobiliário',
        defaults={'default_transaction_type': 'DB'}
    )
    subcat_acao, _ = Subcategory.objects.get_or_create(
        category=cat_compra,
        subcategory='Ações',
        defaults={'default_transaction_type': 'DB'}
    )
    subcat_renda_fixa, _ = Subcategory.objects.get_or_create(
        category=cat_compra,
        subcategory='Renda Fixa',
        defaults={'default_transaction_type': 'DB'}
    )
    
    # Categoria: Venda de investimento
    cat_venda, _ = Category.objects.get_or_create(category='Venda de investimento')
    subcat_venda_fii, _ = Subcategory.objects.get_or_create(
        category=cat_venda,
        subcategory='Fundo imobiliário',
        defaults={'default_transaction_type': 'CR'}
    )
    subcat_venda_acao, _ = Subcategory.objects.get_or_create(
        category=cat_venda,
        subcategory='Ações',
        defaults={'default_transaction_type': 'CR'}
    )
    subcat_venda_renda_fixa, _ = Subcategory.objects.get_or_create(
        category=cat_venda,
        subcategory='Renda Fixa',
        defaults={'default_transaction_type': 'CR'}
    )
    
    # Categoria: Rendimentos
    cat_rendimentos, _ = Category.objects.get_or_create(category='Rendimentos')
    subcat_dividendos, _ = Subcategory.objects.get_or_create(
        category=cat_rendimentos,
        subcategory='Dividendos',
        defaults={'default_transaction_type': 'CR'}
    )
    subcat_jcp, _ = Subcategory.objects.get_or_create(
        category=cat_rendimentos,
        subcategory='JCP',
        defaults={'default_transaction_type': 'CR'}
    )
    subcat_juros, _ = Subcategory.objects.get_or_create(
        category=cat_rendimentos,
        subcategory='Juros',
        defaults={'default_transaction_type': 'CR'}
    )
    
    # Categoria: Taxas financeiras
    cat_taxas, _ = Category.objects.get_or_create(category='Taxas financeiras')
    subcat_corretagem, _ = Subcategory.objects.get_or_create(
        category=cat_taxas,
        subcategory='Corretagem',
        defaults={'default_transaction_type': 'DB'}
    )
    
    # Criar configurações
    # BUY - FII
    AssetTransactionCategoryConfig.objects.get_or_create(
        operation_type='BUY',
        asset_type='FII',
        defaults={
            'subcategory_principal': subcat_fii,
            'transaction_type_principal': 'DB',
            'subcategory_fees': subcat_corretagem,
            'transaction_type_fees': 'DB'
        }
    )
    
    # BUY - STOCK
    AssetTransactionCategoryConfig.objects.get_or_create(
        operation_type='BUY',
        asset_type='STOCK',
        defaults={
            'subcategory_principal': subcat_acao,
            'transaction_type_principal': 'DB',
            'subcategory_fees': subcat_corretagem,
            'transaction_type_fees': 'DB'
        }
    )
    
    # BUY - BOND
    AssetTransactionCategoryConfig.objects.get_or_create(
        operation_type='BUY',
        asset_type='BOND',
        defaults={
            'subcategory_principal': subcat_renda_fixa,
            'transaction_type_principal': 'DB',
            'subcategory_fees': subcat_corretagem,
            'transaction_type_fees': 'DB'
        }
    )
    
    # SELL - FII
    AssetTransactionCategoryConfig.objects.get_or_create(
        operation_type='SELL',
        asset_type='FII',
        defaults={
            'subcategory_principal': subcat_venda_fii,
            'transaction_type_principal': 'CR',
            'subcategory_fees': subcat_corretagem,
            'transaction_type_fees': 'DB'
        }
    )
    
    # SELL - STOCK
    AssetTransactionCategoryConfig.objects.get_or_create(
        operation_type='SELL',
        asset_type='STOCK',
        defaults={
            'subcategory_principal': subcat_venda_acao,
            'transaction_type_principal': 'CR',
            'subcategory_fees': subcat_corretagem,
            'transaction_type_fees': 'DB'
        }
    )
    
    # SELL - BOND
    AssetTransactionCategoryConfig.objects.get_or_create(
        operation_type='SELL',
        asset_type='BOND',
        defaults={
            'subcategory_principal': subcat_venda_renda_fixa,
            'transaction_type_principal': 'CR',
            'subcategory_fees': subcat_corretagem,
            'transaction_type_fees': 'DB'
        }
    )
    
    # DIVIDEND
    AssetTransactionCategoryConfig.objects.get_or_create(
        operation_type='DIVIDEND',
        asset_type=None,
        defaults={
            'subcategory_principal': subcat_dividendos,
            'transaction_type_principal': 'CR',
            'subcategory_fees': None,
            'transaction_type_fees': 'DB'
        }
    )
    
    # JCP
    AssetTransactionCategoryConfig.objects.get_or_create(
        operation_type='JCP',
        asset_type=None,
        defaults={
            'subcategory_principal': subcat_jcp,
            'transaction_type_principal': 'CR',
            'subcategory_fees': None,
            'transaction_type_fees': 'DB'
        }
    )
    
    # INTEREST
    AssetTransactionCategoryConfig.objects.get_or_create(
        operation_type='INTEREST',
        asset_type=None,
        defaults={
            'subcategory_principal': subcat_juros,
            'transaction_type_principal': 'CR',
            'subcategory_fees': None,
            'transaction_type_fees': 'DB'
        }
    )
    
    # AMORTIZATION
    AssetTransactionCategoryConfig.objects.get_or_create(
        operation_type='AMORTIZATION',
        asset_type=None,
        defaults={
            'subcategory_principal': subcat_juros,
            'transaction_type_principal': 'CR',
            'subcategory_fees': None,
            'transaction_type_fees': 'DB'
        }
    )
    
    # REDEMPTION
    AssetTransactionCategoryConfig.objects.get_or_create(
        operation_type='REDEMPTION',
        asset_type=None,
        defaults={
            'subcategory_principal': subcat_venda_renda_fixa,
            'transaction_type_principal': 'CR',
            'subcategory_fees': subcat_corretagem,
            'transaction_type_fees': 'DB'
        }
    )
    
    # SUB
    AssetTransactionCategoryConfig.objects.get_or_create(
        operation_type='SUB',
        asset_type=None,
        defaults={
            'subcategory_principal': subcat_acao,
            'transaction_type_principal': 'DB',
            'subcategory_fees': subcat_corretagem,
            'transaction_type_fees': 'DB'
        }
    )


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0029_add_fixed_account_type'),
    ]

    operations = [
        # Add asset_transaction field to Transaction
        migrations.AddField(
            model_name='transaction',
            name='asset_transaction',
            field=models.ForeignKey(
                blank=True,
                help_text='Transação de ativo relacionada (criada automaticamente)',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='transactions',
                to='finance.assettransaction',
                verbose_name='Transação de Ativo'
            ),
        ),
        # Create AssetTransactionCategoryConfig model
        migrations.CreateModel(
            name='AssetTransactionCategoryConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True, null=True)),
                ('operation_type', models.CharField(
                    choices=[
                        ('BUY', 'Compra'),
                        ('SELL', 'Venda'),
                        ('DIVIDEND', 'Dividendo'),
                        ('JCP', 'Juros sobre Capital Próprio'),
                        ('BONUS', 'Bonificação'),
                        ('SPLIT', 'Desdobramento'),
                        ('GROUP', 'Grupamento'),
                        ('SUB', 'Subscrição'),
                        ('CAPITAL_INCREASE', 'Aumento de Capital'),
                        ('RIGHTS_EXERCISE', 'Exercício de Direitos'),
                        ('AMORTIZATION', 'Amortização'),
                        ('INTEREST', 'Juros (Renda Fixa)'),
                        ('REDEMPTION', 'Resgate (Renda Fixa)'),
                    ],
                    help_text='Tipo de operação de ativo (BUY, SELL, DIVIDEND, etc.)',
                    max_length=20,
                    verbose_name='Tipo de operação'
                )),
                ('asset_type', models.CharField(
                    blank=True,
                    choices=[
                        ('STOCK', 'Ação'),
                        ('FII', 'Fundo Imobiliário'),
                        ('ETF', 'ETF'),
                        ('BOND', 'Renda Fixa'),
                        ('REIT', 'REIT'),
                        ('CRYPTO', 'Criptomoeda'),
                        ('OTHER', 'Outro'),
                    ],
                    help_text='Tipo de ativo específico (opcional). Se None, aplica a todos os tipos.',
                    max_length=10,
                    null=True,
                    verbose_name='Tipo de ativo'
                )),
                ('transaction_type_principal', models.CharField(
                    choices=[('CR', 'Crédito'), ('DB', 'Débito')],
                    default='DB',
                    help_text='Tipo de transação para o valor principal',
                    max_length=2,
                    verbose_name='Tipo de transação principal'
                )),
                ('transaction_type_fees', models.CharField(
                    choices=[('CR', 'Crédito'), ('DB', 'Débito')],
                    default='DB',
                    help_text='Tipo de transação para taxas (geralmente DB)',
                    max_length=2,
                    verbose_name='Tipo de transação de taxas'
                )),
                ('subcategory_principal', models.ForeignKey(
                    help_text='Subcategoria para o valor principal da operação (ex: Compra de investimento > Fundo imobiliário)',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='asset_configs_principal',
                    to='finance.subcategory',
                    verbose_name='Subcategoria Principal'
                )),
                ('subcategory_fees', models.ForeignKey(
                    blank=True,
                    help_text='Subcategoria para taxas (ex: Taxas financeiras > Corretagem). Se None, não cria transação de taxas.',
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='asset_configs_fees',
                    to='finance.subcategory',
                    verbose_name='Subcategoria de Taxas'
                )),
            ],
            options={
                'verbose_name': 'Configuração de Categoria para Transação de Ativo',
                'verbose_name_plural': 'Configurações de Categoria para Transações de Ativos',
                'ordering': ('operation_type', 'asset_type'),
            },
        ),
        migrations.AddIndex(
            model_name='assettransactioncategoryconfig',
            index=models.Index(fields=['operation_type', 'asset_type'], name='finance_ass_operati_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='assettransactioncategoryconfig',
            unique_together={('operation_type', 'asset_type')},
        ),
        migrations.RunPython(create_initial_configs, migrations.RunPython.noop),
    ]
