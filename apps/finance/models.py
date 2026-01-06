from django.db import models

# Create your models here.
class BaseModel(models.Model):
    # Allow nulls to avoid default prompts when adding the base fields
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        abstract = True
        
class Account(BaseModel):
    ACCOUNT_TYPE_CHOICES = [
        ('CASH', 'Dinheiro'),
        ('BANK', 'Banco'),
        ('INVEST', 'Investimento'),
        ('CREDCARD', 'Cartão de crédito'),
    ]

    name = models.CharField('Nome da conta', max_length=100)
    account_type = models.CharField(
        'Tipo',
        max_length=10,
        choices=ACCOUNT_TYPE_CHOICES,
        default='BANK',
    )
    currency = models.CharField('Unidade monetária', max_length=30, default='Real brasileiro')
    opening_balance = models.DecimalField('Saldo de abertura', max_digits=12, decimal_places=2, default=0)

    class Meta:
        verbose_name = 'Conta'
        verbose_name_plural = 'Contas'

    def __str__(self):
        return self.name


class Beneficiary(BaseModel):
    full_name = models.CharField('Nome completo', max_length=200)

    class Meta:
        verbose_name = 'Beneficiário'
        verbose_name_plural = 'Beneficiários'

    def __str__(self):
        return self.full_name


class Category(BaseModel):
    TRANSACTION_TYPE_CHOICES = [
        ('CR', 'Crédito'),
        ('DB', 'Débito'),
    ]

    category = models.CharField('Categoria', max_length=200)
    subcategory = models.CharField('Subcategoria', max_length=200)
    default_transaction_type = models.CharField(
        'Tipo de transação padrão',
        max_length=2,
        choices=TRANSACTION_TYPE_CHOICES,
        default='DB',
    )

    class Meta:
        verbose_name = 'Categoria'
        verbose_name_plural = 'Categorias'
        ordering = ('category', 'subcategory')

    def __str__(self):
        return f"{self.category} - {self.subcategory}"


class Transaction(BaseModel):
    account = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        verbose_name='Conta'
    )
    beneficiary = models.ForeignKey(
        Beneficiary,
        on_delete=models.CASCADE,
        verbose_name='Beneficiário'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        verbose_name='Categoria'
    )
    value = models.DecimalField(
        'Valor',
        max_digits=12,
        decimal_places=2
    )
    due_date = models.DateField(
        'Data do vencimento',
        null=True,
        blank=True
    )
    registration_date = models.DateField(
        'Data do registro',
        null=True,
        blank=True
    )
    purchase_date = models.DateField(
        'Data da compra',
        null=True,
        blank=True
    )
    notes = models.TextField(
        'Anotações',
        blank=True
    )

    class Meta:
        verbose_name = 'Transação'
        verbose_name_plural = 'Transações'
        ordering = ('-created_at',)

    def __str__(self):
        return f"{self.account} - {self.beneficiary} - {self.value}"