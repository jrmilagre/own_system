from django.db import models
from datetime import date
from dateutil.relativedelta import relativedelta
import uuid

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
    category = models.CharField('Categoria', max_length=200)

    class Meta:
        verbose_name = 'Categoria'
        verbose_name_plural = 'Categorias'
        ordering = ('category',)

    def __str__(self):
        return self.category


class Subcategory(BaseModel):
    TRANSACTION_TYPE_CHOICES = [
        ('CR', 'Crédito'),
        ('DB', 'Débito'),
    ]

    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        verbose_name='Categoria'
    )
    subcategory = models.CharField('Subcategoria', max_length=200)
    default_transaction_type = models.CharField(
        'Tipo de transação padrão',
        max_length=2,
        choices=TRANSACTION_TYPE_CHOICES,
        default='DB',
    )

    class Meta:
        verbose_name = 'Subcategoria'
        verbose_name_plural = 'Subcategorias'
        ordering = ('category', 'subcategory')

    def __str__(self):
        return f"{self.category.category} - {self.subcategory}"


class Transaction(BaseModel):
    account = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        verbose_name='Conta'
    )
    beneficiary = models.ForeignKey(
        Beneficiary,
        on_delete=models.CASCADE,
        verbose_name='Beneficiário',
        null=True,
        blank=True
    )
    subcategory = models.ForeignKey(
        Subcategory,
        on_delete=models.CASCADE,
        verbose_name='Subcategoria',
        null=True,
        blank=True
    )
    transaction_type = models.CharField(
        'Tipo de transação',
        max_length=2,
        choices=[('CR', 'Crédito'), ('DB', 'Débito')],
        default='DB',
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
    transfer_group_id = models.UUIDField(
        'ID do grupo de transferência',
        null=True,
        blank=True,
        help_text='UUID que vincula as duas transações de uma transferência'
    )
    is_transfer = models.BooleanField(
        'É transferência',
        default=False,
        help_text='Indica se esta transação faz parte de uma transferência entre contas'
    )

    class Meta:
        verbose_name = 'Transação'
        verbose_name_plural = 'Transações'
        ordering = ('-created_at',)

    def __str__(self):
        if self.is_transfer:
            return f"Transferência: {self.account} - {self.value}"
        beneficiary_str = self.beneficiary if self.beneficiary else "N/A"
        return f"{self.account} - {beneficiary_str} - {self.value}"

    def get_transfer_pair(self):
        """Retorna a transação vinculada em uma transferência, se existir"""
        if not self.is_transfer or not self.transfer_group_id:
            return None
        return Transaction.objects.filter(
            transfer_group_id=self.transfer_group_id
        ).exclude(pk=self.pk).first()


class Scheduler(BaseModel):
    RECURRENCE_TYPE_CHOICES = [
        ('DAILY', 'Diária'),
        ('WEEKLY', 'Semanal'),
        ('MONTHLY', 'Mensal'),
        ('YEARLY', 'Anual'),
    ]

    TERMINATION_TYPE_CHOICES = [
        ('INFINITE', 'Infinito'),
        ('INSTALLMENTS', 'Número de parcelas'),
        ('FINAL_DATE', 'Data final'),
    ]

    STATUS_CHOICES = [
        ('ACTIVE', 'Ativo'),
        ('PAUSED', 'Pausado'),
        ('COMPLETED', 'Concluído'),
    ]

    # Campos de Transação (sem registration_date)
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
    subcategory = models.ForeignKey(
        'Subcategory',
        on_delete=models.CASCADE,
        verbose_name='Subcategoria'
    )
    transaction_type = models.CharField(
        'Tipo de transação',
        max_length=2,
        choices=[('CR', 'Crédito'), ('DB', 'Débito')],
        default='DB',
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
    purchase_date = models.DateField(
        'Data da compra',
        null=True,
        blank=True
    )
    notes = models.TextField(
        'Anotações',
        blank=True
    )

    # Campos de Recorrência
    recurrence_type = models.CharField(
        'Tipo de recorrência',
        max_length=10,
        choices=RECURRENCE_TYPE_CHOICES,
        default='MONTHLY'
    )
    recurrence_interval = models.IntegerField(
        'Intervalo da recorrência',
        default=1
    )

    # Campos de Término
    termination_type = models.CharField(
        'Tipo de término',
        max_length=15,
        choices=TERMINATION_TYPE_CHOICES,
        default='INFINITE'
    )
    remaining_installments = models.IntegerField(
        'Parcelas restantes',
        null=True,
        blank=True
    )
    final_date = models.DateField(
        'Data final',
        null=True,
        blank=True
    )

    # Campos de Controle
    status = models.CharField(
        'Status',
        max_length=10,
        choices=STATUS_CHOICES,
        default='ACTIVE'
    )
    original_due_date = models.DateField(
        'Data de vencimento original',
        null=True,
        blank=True
    )
    registered_count = models.IntegerField(
        'Contador de registros',
        default=0
    )

    class Meta:
        verbose_name = 'Agendamento'
        verbose_name_plural = 'Agendamentos'
        ordering = ('-created_at',)

    def __str__(self):
        return f"{self.account} - {self.beneficiary} - {self.value} - {self.get_recurrence_type_display()}"

    def save(self, *args, **kwargs):
        # Ao criar, definir original_due_date se não estiver definido
        if not self.pk and self.due_date and not self.original_due_date:
            self.original_due_date = self.due_date
        super().save(*args, **kwargs)

    def calculate_next_due_date(self):
        """Calcula a próxima data baseada no estado atual (após incremento do registered_count).
        Usado dentro de register() após incrementar o contador."""
        if not self.original_due_date:
            return None

        base_date = self.original_due_date
        # Após incrementar registered_count no register(), este método calcula a próxima
        # registered_count já foi incrementado, então próxima transação é registered_count + 1
        multiplier = self.registered_count + 1

        if self.recurrence_type == 'DAILY':
            return base_date + relativedelta(days=multiplier * self.recurrence_interval)
        elif self.recurrence_type == 'WEEKLY':
            return base_date + relativedelta(weeks=multiplier * self.recurrence_interval)
        elif self.recurrence_type == 'MONTHLY':
            return base_date + relativedelta(months=multiplier * self.recurrence_interval)
        elif self.recurrence_type == 'YEARLY':
            return base_date + relativedelta(years=multiplier * self.recurrence_interval)
        return None

    def get_next_due_date_after_registration(self):
        """Calcula a próxima data APÓS registrar a transação atual.
        Usado para visualização pré-registro (antes de chamar register()).
        
        Este método usa a mesma lógica do register(): calcula a próxima data
        baseada na due_date atual + intervalo, garantindo consistência entre
        a visualização e o registro real.
        """
        if not self.due_date:
            return None

        base_date = self.due_date

        if self.recurrence_type == 'DAILY':
            return base_date + relativedelta(days=self.recurrence_interval)
        elif self.recurrence_type == 'WEEKLY':
            return base_date + relativedelta(weeks=self.recurrence_interval)
        elif self.recurrence_type == 'MONTHLY':
            return base_date + relativedelta(months=self.recurrence_interval)
        elif self.recurrence_type == 'YEARLY':
            return base_date + relativedelta(years=self.recurrence_interval)
        return None

    def sync_registered_count(self):
        """Sincroniza registered_count com o número real de transações registradas.
        Útil para corrigir inconsistências quando transações foram deletadas manualmente."""
        count = Transaction.objects.filter(
            account=self.account,
            beneficiary=self.beneficiary,
            subcategory=self.subcategory,
            value=self.value,
            due_date__gte=self.original_due_date if self.original_due_date else date.min
        ).count()
        
        if self.registered_count != count:
            self.registered_count = count
            self.save(update_fields=['registered_count'])

    def is_valid(self):
        """Verifica se o agendamento pode criar transações"""
        if self.status != 'ACTIVE':
            return False

        if self.termination_type == 'INSTALLMENTS':
            if self.remaining_installments is not None and self.remaining_installments <= 0:
                return False

        if self.termination_type == 'FINAL_DATE':
            if self.final_date and date.today() > self.final_date:
                return False

        return True

    def mark_completed(self):
        """Marca o status como Concluído"""
        self.status = 'COMPLETED'
        self.save()

    def calculate_next_due_date_from_current(self):
        """Calcula a próxima data baseada na due_date atual + intervalo.
        Usado no método register() para atualizar a próxima data após registrar.
        
        Este método usa self.due_date como base e adiciona o intervalo de recorrência,
        não dependendo de original_due_date ou registered_count.
        """
        if not self.due_date:
            return None

        base_date = self.due_date

        if self.recurrence_type == 'DAILY':
            return base_date + relativedelta(days=self.recurrence_interval)
        elif self.recurrence_type == 'WEEKLY':
            return base_date + relativedelta(weeks=self.recurrence_interval)
        elif self.recurrence_type == 'MONTHLY':
            return base_date + relativedelta(months=self.recurrence_interval)
        elif self.recurrence_type == 'YEARLY':
            return base_date + relativedelta(years=self.recurrence_interval)
        return None

    def register(self, transaction_data=None):
        """Registra uma transação do agendamento
        
        Args:
            transaction_data: Dicionário opcional com dados para sobrescrever valores padrão do agendamento.
                             Se não fornecido, usa os valores do agendamento.
                             registration_date padrão é self.due_date (não date.today()).
        """
        if not self.is_valid():
            raise ValueError("Agendamento não está válido para registro")

        transaction_data = transaction_data or {}
        
        # Usar dados do agendamento como padrão, sobrescrever com transaction_data
        account = transaction_data.get('account', self.account)
        beneficiary = transaction_data.get('beneficiary', self.beneficiary)
        subcategory = transaction_data.get('subcategory', self.subcategory)
        transaction_type = transaction_data.get('transaction_type', self.transaction_type)
        value = transaction_data.get('value', self.value)
        due_date = transaction_data.get('due_date', self.due_date)
        registration_date = transaction_data.get('registration_date', self.due_date)
        purchase_date = transaction_data.get('purchase_date', self.purchase_date)
        notes = transaction_data.get('notes', self.notes)

        # Criar a Transaction
        transaction = Transaction.objects.create(
            account=account,
            beneficiary=beneficiary,
            subcategory=subcategory,
            transaction_type=transaction_type,
            value=value,
            due_date=due_date,
            registration_date=registration_date,
            purchase_date=purchase_date,
            notes=notes
        )

        # Incrementar contador
        self.registered_count += 1

        # Decrementar parcelas restantes se aplicável
        if self.termination_type == 'INSTALLMENTS' and self.remaining_installments is not None:
            self.remaining_installments -= 1

        # Calcular próxima data baseada na due_date atual + intervalo
        next_due_date = self.calculate_next_due_date_from_current()
        if next_due_date:
            self.due_date = next_due_date

        # Verificar se deve marcar como concluído
        if self.termination_type == 'INSTALLMENTS':
            if self.remaining_installments is not None and self.remaining_installments <= 0:
                self.mark_completed()
            else:
                self.save()
        elif self.termination_type == 'FINAL_DATE':
            if self.final_date and next_due_date and next_due_date > self.final_date:
                self.mark_completed()
            else:
                self.save()
        else:
            self.save()

        return transaction