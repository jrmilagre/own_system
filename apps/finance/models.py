from django.db import models
from django.db import transaction as db_transaction
from datetime import date, timedelta
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
    
    def get_balance(self, date=None):
        """
        Calcula o saldo da conta até uma data específica.
        Se date=None, calcula o saldo atual (todas as movimentações).
        """
        from django.db.models import Q
        from decimal import Decimal
        
        balance = self.opening_balance
        
        # Filtro de data para transações
        date_filter = Q()
        if date:
            date_filter = Q(transaction_date__lte=date) | Q(transaction_date__isnull=True, due_date__lte=date)
        
        # Transações normais
        transactions = Transaction.objects.filter(account=self)
        if date:
            transactions = transactions.filter(date_filter)
        
        for trans in transactions:
            if trans.transaction_type == 'CR':
                balance += trans.value
            elif trans.transaction_type == 'DB':
                balance -= trans.value
        
        # Movimentações de ativos que afetam dinheiro
        asset_transactions = AssetTransaction.objects.filter(account=self)
        if date:
            asset_transactions = asset_transactions.filter(date__lte=date)
        
        for asset_trans in asset_transactions:
            net_value = asset_trans.get_net_value()
            balance += net_value  # get_net_value() já retorna negativo para saídas
        
        return balance
    
    def get_previous_balance(self, date):
        """
        Calcula o saldo anterior a uma data específica.
        Retorna: saldo de abertura + todas as movimentações antes da data.
        Se date for None, retorna apenas o saldo de abertura.
        """
        if date is None:
            return self.opening_balance
        # Calcular saldo até o dia anterior
        previous_date = date - timedelta(days=1)
        return self.get_balance(previous_date)
    
    def get_statement(self, start_date=None, end_date=None):
        """
        Retorna o extrato da conta no período especificado.
        Retorna uma lista ordenada de movimentações com saldo acumulado.
        """
        from django.db.models import Q
        from datetime import datetime, timedelta
        from decimal import Decimal
        
        movements = []
        
        # Transações normais
        transactions = Transaction.objects.filter(account=self)
        if start_date:
            transactions = transactions.filter(
                Q(transaction_date__gte=start_date) | 
                Q(transaction_date__isnull=True, due_date__gte=start_date)
            )
        if end_date:
            transactions = transactions.filter(
                Q(transaction_date__lte=end_date) | 
                Q(transaction_date__isnull=True, due_date__lte=end_date)
            )
        
        for trans in transactions:
            movement_date = trans.transaction_date or trans.due_date
            if movement_date:  # Só adicionar se tiver data
                description = ""
                if trans.beneficiary:
                    description = str(trans.beneficiary)
                if trans.subcategory:
                    description += f" - {trans.subcategory.subcategory}"
                if not description:
                    description = "Transação"
                
                movements.append({
                    'date': movement_date,
                    'type': 'TRANSACTION',
                    'description': description,
                    'debit': trans.value if trans.transaction_type == 'DB' else None,
                    'credit': trans.value if trans.transaction_type == 'CR' else None,
                    'transaction': trans,
                    'asset_transaction': None,
                })
        
        # Movimentações de ativos que afetam dinheiro
        asset_transactions = AssetTransaction.objects.filter(account=self)
        if start_date:
            asset_transactions = asset_transactions.filter(date__gte=start_date)
        if end_date:
            asset_transactions = asset_transactions.filter(date__lte=end_date)
        
        for asset_trans in asset_transactions:
            net_value = asset_trans.get_net_value()
            if net_value != 0:  # Apenas operações que afetam dinheiro
                description = f"{asset_trans.get_operation_type_display()} - {asset_trans.asset.code}"
                if asset_trans.notes:
                    description += f" ({asset_trans.notes})"
                
                movements.append({
                    'date': asset_trans.date,
                    'type': 'ASSET',
                    'description': description,
                    'debit': abs(net_value) if net_value < 0 else None,
                    'credit': net_value if net_value > 0 else None,
                    'transaction': None,
                    'asset_transaction': asset_trans,
                })
        
        # Ordenar por data
        movements.sort(key=lambda x: x['date'] if x['date'] else datetime.min.date())
        
        # Calcular saldo acumulado
        # Começar com saldo anterior ao período
        previous_balance = self.get_previous_balance(start_date) if start_date else self.opening_balance
        balance = previous_balance
        
        for movement in movements:
            if movement['debit']:
                balance -= movement['debit']
            if movement['credit']:
                balance += movement['credit']
            movement['balance'] = balance
        
        return movements


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
    
    def is_mapped_to_cash_flow(self):
        """Verifica se esta subcategoria está mapeada em algum item do fluxo de caixa"""
        return self.get_cash_flow_mapping_count() > 0
    
    def get_cash_flow_mapping_count(self):
        """Conta quantas vezes esta subcategoria aparece nas regras de CashFlowItem"""
        count = 0
        cash_flow_items = CashFlowItem.objects.filter(calculation_type='RULES')
        
        for item in cash_flow_items:
            if item.calculation_rules:
                for rule in item.calculation_rules:
                    if rule.get('type') == 'subcategory' and rule.get('subcategory_id') == self.id:
                        count += 1
        
        return count
    
    def has_duplicate_mapping(self):
        """Retorna True se esta subcategoria está mapeada mais de uma vez"""
        return self.get_cash_flow_mapping_count() > 1


class Budget(BaseModel):
    """Modelo para armazenar orçamento por subcategoria e mês/ano"""
    
    subcategory = models.ForeignKey(
        Subcategory,
        on_delete=models.CASCADE,
        verbose_name='Subcategoria',
        related_name='budgets'
    )
    budget_date = models.DateField(
        'Data do orçamento',
        help_text='Data do orçamento (sempre dia 1 do mês/ano)'
    )
    amount = models.DecimalField(
        'Valor',
        max_digits=12,
        decimal_places=2,
        default=0
    )
    
    class Meta:
        verbose_name = 'Orçamento'
        verbose_name_plural = 'Orçamentos'
        ordering = ('budget_date', 'subcategory')
        unique_together = [['subcategory', 'budget_date']]
        indexes = [
            models.Index(fields=['subcategory', 'budget_date']),
            models.Index(fields=['budget_date']),
        ]
    
    def __str__(self):
        return f"{self.subcategory} - {self.budget_date.strftime('%m/%Y')} - R$ {self.amount}"
    
    @property
    def year(self):
        """Retorna o ano do orçamento"""
        return self.budget_date.year
    
    @property
    def month(self):
        """Retorna o mês do orçamento"""
        return self.budget_date.month
    
    @property
    def transaction_type(self):
        """Retorna o tipo de transação padrão da subcategoria"""
        return self.subcategory.default_transaction_type
    
    def save(self, *args, **kwargs):
        """Garante que budget_date sempre tenha dia = 1"""
        if self.budget_date:
            # Normalizar para sempre ter dia 1
            self.budget_date = self.budget_date.replace(day=1)
        super().save(*args, **kwargs)
    
    @classmethod
    def get_average_previous_year(cls, subcategory, year):
        """Calcula a média do ano anterior para uma subcategoria"""
        from django.db.models import Avg
        previous_year = year - 1
        budgets = cls.objects.filter(
            subcategory=subcategory,
            budget_date__year=previous_year
        )
        result = budgets.aggregate(avg=Avg('amount'))
        return result['avg'] or 0
    
    @classmethod
    def get_year_total(cls, subcategory, year):
        """Calcula o total do ano para uma subcategoria"""
        from django.db.models import Sum
        budgets = cls.objects.filter(
            subcategory=subcategory,
            budget_date__year=year
        )
        result = budgets.aggregate(total=Sum('amount'))
        return result['total'] or 0
    
    @classmethod
    def get_totals_by_type(cls, year):
        """Calcula totais separados por tipo (CR/DB) para um ano"""
        from django.db.models import Sum, Q
        
        # Total de receitas (CR)
        credit_total = cls.objects.filter(
            budget_date__year=year,
            subcategory__default_transaction_type='CR'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Total de despesas (DB)
        debit_total = cls.objects.filter(
            budget_date__year=year,
            subcategory__default_transaction_type='DB'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        return {
            'credit': credit_total,
            'debit': debit_total,
            'balance': credit_total - debit_total
        }


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
    transaction_date = models.DateField(
        'Data da transação',
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
    multiple_transaction_group_id = models.UUIDField(
        'ID do grupo de transação múltipla',
        null=True,
        blank=True,
        help_text='UUID que vincula as transações de uma transação múltipla'
    )
    is_multiple = models.BooleanField(
        'É transação múltipla',
        default=False,
        help_text='Indica se esta transação faz parte de uma transação múltipla'
    )
    import_hash = models.CharField(
        'Hash de importação',
        max_length=32,
        unique=True,
        null=True,
        blank=True,
        help_text='Hash MD5 gerado a partir dos dados originais da importação para prevenir duplicatas'
    )

    class Meta:
        verbose_name = 'Transação'
        verbose_name_plural = 'Transações'
        ordering = ('-created_at',)

    def __str__(self):
        if self.is_transfer:
            return f"Transferência: {self.account} - {self.value}"
        if self.is_multiple:
            return f"Transação Múltipla: {self.account} - {self.value}"
        beneficiary_str = self.beneficiary if self.beneficiary else "N/A"
        return f"{self.account} - {beneficiary_str} - {self.value}"

    def get_transfer_pair(self):
        """Retorna a transação vinculada em uma transferência, se existir"""
        if not self.is_transfer or not self.transfer_group_id:
            return None
        return Transaction.objects.filter(
            transfer_group_id=self.transfer_group_id
        ).exclude(pk=self.pk).first()

    def get_multiple_transaction_group(self):
        """Retorna todas as transações do mesmo grupo de transação múltipla"""
        if not self.is_multiple or not self.multiple_transaction_group_id:
            return Transaction.objects.none()
        return Transaction.objects.filter(
            multiple_transaction_group_id=self.multiple_transaction_group_id
        ).order_by('id')


class Scheduler(BaseModel):
    RECURRENCE_TYPE_CHOICES = [
        ('NONE', 'Único (sem recorrência)'),
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

    # Campos de Transação (sem transaction_date)
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

    # Campos para Agendamento Múltiplo
    multiple_scheduler_group_id = models.UUIDField(
        'ID do grupo de agendamento múltiplo',
        null=True,
        blank=True,
        help_text='UUID que vincula os agendamentos de um agendamento múltiplo'
    )
    is_multiple = models.BooleanField(
        'É agendamento múltiplo',
        default=False,
        help_text='Indica se este agendamento faz parte de um agendamento múltiplo'
    )
    is_transfer = models.BooleanField(
        'É transferência',
        default=False,
        help_text='Indica se este agendamento é uma transferência entre contas (apenas para múltiplos)'
    )
    destination_account = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        verbose_name='Conta de destino',
        null=True,
        blank=True,
        related_name='scheduler_destination_items',
        help_text='Conta de destino (apenas para transferências em agendamentos múltiplos)'
    )

    class Meta:
        verbose_name = 'Agendamento'
        verbose_name_plural = 'Agendamentos'
        ordering = ('-created_at',)

    def __str__(self):
        if self.is_multiple:
            return f"Agendamento Múltiplo: {self.account} - {self.value} - {self.get_recurrence_type_display()}"
        return f"{self.account} - {self.beneficiary} - {self.value} - {self.get_recurrence_type_display()}"
    
    def get_multiple_scheduler_group(self):
        """Retorna todos os agendamentos do mesmo grupo de agendamento múltiplo"""
        if not self.is_multiple or not self.multiple_scheduler_group_id:
            return Scheduler.objects.none()
        return Scheduler.objects.filter(
            multiple_scheduler_group_id=self.multiple_scheduler_group_id
        ).order_by('id')

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
                             transaction_date padrão é self.due_date (não date.today()).
                             Pode incluir: is_multiple, multiple_transaction_group_id, is_transfer, transfer_group_id
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
        transaction_date = transaction_data.get('transaction_date', self.due_date)
        purchase_date = transaction_data.get('purchase_date', self.purchase_date)
        notes = transaction_data.get('notes', self.notes)
        
        # Campos para transações múltiplas
        is_multiple = transaction_data.get('is_multiple', False)
        multiple_transaction_group_id = transaction_data.get('multiple_transaction_group_id', None)
        is_transfer = transaction_data.get('is_transfer', False)
        transfer_group_id = transaction_data.get('transfer_group_id', None)

        # Criar a Transaction
        transaction = Transaction.objects.create(
            account=account,
            beneficiary=beneficiary,
            subcategory=subcategory,
            transaction_type=transaction_type,
            value=value,
            due_date=due_date,
            transaction_date=transaction_date,
            purchase_date=purchase_date,
            notes=notes,
            is_multiple=is_multiple,
            multiple_transaction_group_id=multiple_transaction_group_id,
            is_transfer=is_transfer,
            transfer_group_id=transfer_group_id
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



# REMOVIDO: MultipleScheduler e MultipleSchedulerItem unificados em Scheduler
# Os modelos foram removidos apÃ³s migraÃ§Ã£o de dados


class Asset(BaseModel):
    """Modelo para representar um ativo financeiro"""
    
    ASSET_TYPE_CHOICES = [
        ('STOCK', 'Ação'),
        ('FII', 'Fundo Imobiliário'),
        ('ETF', 'ETF'),
        ('BOND', 'Renda Fixa'),
        ('REIT', 'REIT'),
        ('CRYPTO', 'Criptomoeda'),
        ('OTHER', 'Outro'),
    ]
    
    # Identificação
    code = models.CharField(
        'Código',
        max_length=20,
        unique=True,
        help_text='Código do ativo (ex: PETR4, HGLG11, CDB123)'
    )
    name = models.CharField(
        'Nome',
        max_length=200,
        help_text='Nome completo do ativo'
    )
    asset_type = models.CharField(
        'Tipo de ativo',
        max_length=10,
        choices=ASSET_TYPE_CHOICES,
        default='STOCK'
    )
    
    # Informações adicionais
    sector = models.CharField(
        'Setor',
        max_length=100,
        blank=True,
        help_text='Setor do ativo (ex: Petróleo, Varejo)'
    )
    currency = models.CharField(
        'Moeda',
        max_length=10,
        default='BRL',
        help_text='Moeda de negociação (BRL, USD, etc.)'
    )
    notes = models.TextField(
        'Observações',
        blank=True
    )
    
    class Meta:
        verbose_name = 'Ativo'
        verbose_name_plural = 'Ativos'
        ordering = ('code',)
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['asset_type']),
        ]
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    def get_current_position(self, account=None):
        """Retorna a posição atual do ativo"""
        from django.db.models import Sum, F, Q
        
        filters = {'asset': self}
        if account:
            filters['account'] = account
        
        # Operações que AUMENTAM a quantidade
        increases = AssetTransaction.objects.filter(
            **filters,
            operation_type__in=[
                'BUY',           # Compra
                'BONUS',         # Bonificação (ações gratuitas)
                'SUB',           # Subscrição
                'SPLIT',         # Desdobramento (aumenta quantidade)
                'CAPITAL_INCREASE',  # Aumento de capital
                'RIGHTS_EXERCISE',   # Exercício de direitos
            ]
        ).aggregate(
            total_quantity=Sum('quantity'),
            total_cost=Sum(F('quantity') * F('price') + F('fees'))
        )
        
        # Operações que DIMINUEM a quantidade
        decreases = AssetTransaction.objects.filter(
            **filters,
            operation_type__in=['SELL', 'GROUP']  # Venda e Grupamento
        ).aggregate(
            total_quantity=Sum('quantity'),
            total_revenue=Sum(F('quantity') * F('price') - F('fees'))
        )
        
        quantity = (increases['total_quantity'] or 0) - (decreases['total_quantity'] or 0)
        avg_cost = 0
        if quantity > 0:
            # Preço médio baseado no custo médio ponderado das compras
            # Para simplificar, usamos o custo médio de todas as compras
            # (método de custo médio simples, não PEPS)
            total_cost = increases['total_cost'] or 0
            total_quantity_bought = increases['total_quantity'] or 0
            if total_quantity_bought > 0:
                avg_cost = total_cost / total_quantity_bought
        
        return {
            'quantity': quantity,
            'average_cost': avg_cost,
            'total_cost': avg_cost * quantity if quantity > 0 else 0
        }


class AssetTransaction(BaseModel):
    """Modelo para registrar transações de ativos"""
    
    OPERATION_TYPE_CHOICES = [
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
    ]
    
    # Relacionamentos
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        verbose_name='Ativo',
        related_name='transactions'
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        verbose_name='Conta',
        help_text='Conta onde o ativo está alocado'
    )
    
    # Tipo de operação
    operation_type = models.CharField(
        'Tipo de operação',
        max_length=20,
        choices=OPERATION_TYPE_CHOICES
    )
    
    # Dados da operação
    date = models.DateField(
        'Data da operação'
    )
    quantity = models.DecimalField(
        'Quantidade',
        max_digits=15,
        decimal_places=8,
        default=0,
        help_text='Quantidade de ativos (0 para dividendos, juros, etc.)'
    )
    price = models.DecimalField(
        'Preço unitário',
        max_digits=12,
        decimal_places=4,
        default=0,
        help_text='Preço por unidade (0 para dividendos, juros, etc.)'
    )
    fees = models.DecimalField(
        'Taxas e impostos',
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text='Taxas de corretagem, emolumentos, etc.'
    )
    
    # Valor total (calculado ou manual)
    total_value = models.DecimalField(
        'Valor total',
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text='Valor total da operação (quantity * price ± fees)'
    )
    
    # Para operações de renda (dividendos, juros)
    income_value = models.DecimalField(
        'Valor de rendimento',
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text='Valor recebido em dividendos, juros, etc.'
    )
    
    # Referência a transação financeira (opcional)
    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Transação relacionada',
        help_text='Transação financeira relacionada (para integração com o sistema existente)'
    )
    
    # Informações adicionais
    notes = models.TextField(
        'Observações',
        blank=True
    )
    
    class Meta:
        verbose_name = 'Transação de Ativo'
        verbose_name_plural = 'Transações de Ativos'
        ordering = ('-date', '-created_at')
        indexes = [
            models.Index(fields=['asset', 'date']),
            models.Index(fields=['operation_type', 'date']),
            models.Index(fields=['account', 'date']),
        ]
    
    def __str__(self):
        return f"{self.asset.code} - {self.get_operation_type_display()} - {self.date} - {self.quantity}"
    
    def save(self, *args, **kwargs):
        # Calcular total_value automaticamente baseado no tipo de operação
        # Se total_value não foi preenchido (é 0), calcular automaticamente
        # Caso contrário, usar o valor preenchido (pode ter sido preenchido manualmente ou calculado pelo JS)
        calculated_base = self.quantity * self.price
        
        if self.operation_type in ['BUY', 'SELL', 'SUB', 'REDEMPTION']:
            # Se total_value é 0 ou muito próximo de 0, calcular automaticamente
            if abs(self.total_value) < 0.01:
                if self.operation_type == 'BUY':
                    self.total_value = calculated_base + self.fees
                elif self.operation_type == 'SELL':
                    self.total_value = calculated_base - self.fees
                elif self.operation_type == 'SUB':
                    self.total_value = calculated_base + self.fees
                else:  # REDEMPTION
                    self.total_value = calculated_base - self.fees
            # Se total_value foi preenchido (diferente de 0), manter como está
            # O usuário pode ter preenchido manualmente ou foi calculado pelo JS
        elif self.operation_type in ['DIVIDEND', 'JCP', 'INTEREST', 'AMORTIZATION']:
            # Para rendimentos, usar income_value se total_value não foi preenchido
            if abs(self.total_value) < 0.01:
                self.total_value = self.income_value
        elif self.operation_type in ['BONUS', 'SPLIT', 'GROUP', 'CAPITAL_INCREASE', 'RIGHTS_EXERCISE']:
            # Operações que não envolvem dinheiro
            self.total_value = 0
        
        super().save(*args, **kwargs)
    
    def get_net_value(self):
        """Retorna o valor líquido da operação para o fluxo de caixa
        Sempre calcula baseado em quantity * price e adiciona/subtrai fees
        para garantir consistência, independentemente de como total_value foi preenchido
        """
        calculated_base = self.quantity * self.price
        
        if self.operation_type == 'BUY':
            # Para compras: quantity * price + fees (saída de dinheiro)
            return -(calculated_base + self.fees)
        elif self.operation_type == 'SELL':
            # Para vendas: quantity * price - fees (entrada de dinheiro)
            return calculated_base - self.fees
        elif self.operation_type == 'SUB':
            # Para subscrições: quantity * price + fees (saída de dinheiro)
            return -(calculated_base + self.fees)
        elif self.operation_type == 'REDEMPTION':
            # Para resgates: quantity * price - fees (entrada de dinheiro)
            return calculated_base - self.fees
        elif self.operation_type in ['DIVIDEND', 'JCP', 'INTEREST', 'AMORTIZATION']:
            return self.income_value  # Entrada de dinheiro
        return 0


class AssetPosition(BaseModel):
    """Snapshot de posição de ativo em uma data específica (opcional, para histórico)"""
    
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        verbose_name='Ativo',
        related_name='positions'
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        verbose_name='Conta'
    )
    date = models.DateField(
        'Data da posição'
    )
    quantity = models.DecimalField(
        'Quantidade',
        max_digits=15,
        decimal_places=8
    )
    average_cost = models.DecimalField(
        'Preço médio',
        max_digits=12,
        decimal_places=4
    )
    current_price = models.DecimalField(
        'Preço atual',
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True
    )
    
    class Meta:
        verbose_name = 'Posição de Ativo'
        verbose_name_plural = 'Posições de Ativos'
        ordering = ('-date', 'asset')
        unique_together = [['asset', 'account', 'date']]
        indexes = [
            models.Index(fields=['asset', 'account', 'date']),
        ]
    
    def __str__(self):
        return f"{self.asset.code} - {self.date} - {self.quantity}"
    
    def get_total_cost(self):
        """Retorna o custo total da posição"""
        return self.quantity * self.average_cost
    
    def get_market_value(self):
        """Retorna o valor de mercado da posição"""
        if self.current_price:
            return self.quantity * self.current_price
        return None
    
    def get_profit_loss(self):
        """Retorna o lucro/prejuízo da posição"""
        market_value = self.get_market_value()
        if market_value:
            return market_value - self.get_total_cost()
        return None


class Inventory(BaseModel):
    """Modelo para cadastrar bens duráveis de um lar"""
    
    INVENTORY_TYPE_CHOICES = [
        ('ELECTRO', 'Eletrodoméstico'),
        ('ART', 'Obra de arte'),
        ('BOOK', 'Livro'),
        ('MUSIC', 'Música'),
        ('OFFICE', 'Escritório'),
        ('TOOL', 'Ferramenta'),
        ('VEHICLE', 'Veículo'),
        ('ELECTRONIC', 'Eletrônico'),
        ('REAL_ESTATE', 'Imobiliário'),
        ('HOBBY', 'Hobby'),
    ]
    
    CONDITION_CHOICES = [
        ('NEW', 'Novo'),
        ('EXCELLENT', 'Excelente'),
        ('GOOD', 'Bom'),
        ('FAIR', 'Regular'),
        ('POOR', 'Ruim'),
        ('DAMAGED', 'Danificado'),
    ]
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Ativo'),
        ('SOLD', 'Vendido'),
        ('DONATED', 'Doado'),
        ('DISCARDED', 'Descartado'),
        ('LOST', 'Perdido'),
    ]
    
    # Campos principais
    type = models.CharField(
        'Tipo',
        max_length=20,
        choices=INVENTORY_TYPE_CHOICES,
        help_text='Categoria do bem'
    )
    description = models.CharField(
        'Descrição',
        max_length=200,
        help_text='Descrição do item'
    )
    buy_price = models.DecimalField(
        'Preço de compra',
        max_digits=12,
        decimal_places=2,
        help_text='Valor pago na compra'
    )
    buy_date = models.DateField(
        'Data de compra',
        help_text='Data em que o item foi adquirido'
    )
    actual_price = models.DecimalField(
        'Preço atual',
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Valor atual estimado do item'
    )
    
    # Informações adicionais
    brand = models.CharField(
        'Marca',
        max_length=100,
        blank=True,
        help_text='Marca do produto'
    )
    model = models.CharField(
        'Modelo',
        max_length=100,
        blank=True,
        help_text='Modelo do produto'
    )
    serial_number = models.CharField(
        'Número de série',
        max_length=100,
        blank=True,
        help_text='Número de série do produto'
    )
    condition = models.CharField(
        'Condição',
        max_length=20,
        choices=CONDITION_CHOICES,
        default='GOOD',
        help_text='Estado atual do item'
    )
    status = models.CharField(
        'Status',
        max_length=20,
        choices=STATUS_CHOICES,
        default='ACTIVE',
        help_text='Status do item no inventário'
    )
    location = models.CharField(
        'Localização',
        max_length=200,
        blank=True,
        help_text='Onde o item está guardado'
    )
    
    # Garantia
    warranty_end_date = models.DateField(
        'Data de término da garantia',
        null=True,
        blank=True,
        help_text='Data de término da garantia'
    )
    
    # Informações de venda (se aplicável)
    sale_date = models.DateField(
        'Data de venda',
        null=True,
        blank=True,
        help_text='Data em que o item foi vendido'
    )
    sale_price = models.DecimalField(
        'Preço de venda',
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Valor pelo qual o item foi vendido'
    )
    
    # Integração com sistema financeiro
    purchase_transaction = models.ForeignKey(
        Transaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Transação de compra',
        related_name='inventory_items',
        help_text='Transação financeira relacionada à compra deste item'
    )
    
    # Anotações
    notes = models.TextField(
        'Anotações',
        blank=True,
        help_text='Observações adicionais sobre o item'
    )
    
    class Meta:
        verbose_name = 'Item do Inventário'
        verbose_name_plural = 'Itens do Inventário'
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=['type', 'status']),
            models.Index(fields=['status']),
            models.Index(fields=['buy_date']),
        ]
    
    def __str__(self):
        return f"{self.get_type_display()} - {self.description}"
    
    def get_depreciation(self):
        """Calcula a depreciação do item baseada em buy_price e actual_price"""
        if not self.actual_price or not self.buy_price:
            return None
        return self.buy_price - self.actual_price
    
    def get_depreciation_percentage(self):
        """Calcula a porcentagem de depreciação"""
        if not self.actual_price or not self.buy_price or self.buy_price == 0:
            return None
        return ((self.buy_price - self.actual_price) / self.buy_price) * 100
    
    def get_age_days(self):
        """Calcula a idade do item em dias"""
        if not self.buy_date:
            return None
        from datetime import date
        return (date.today() - self.buy_date).days
    
    def is_under_warranty(self):
        """Verifica se o item ainda está na garantia"""
        if not self.warranty_end_date:
            return None
        from datetime import date
        return date.today() <= self.warranty_end_date
    
    def get_profit_loss_on_sale(self):
        """Calcula lucro/prejuízo na venda (se vendido)"""
        if not self.sale_price or not self.buy_price:
            return None
        return self.sale_price - self.buy_price


class CashFlowItem(BaseModel):
    """Modelo para itens do fluxo de caixa gerencial"""
    
    CALCULATION_TYPE_CHOICES = [
        ('SUBTOTAL', 'Totaliza subníveis'),
        ('RULES', 'Calcula por regras'),
    ]
    
    code = models.CharField(
        'Código',
        max_length=50,
        unique=True,
        help_text='Código hierárquico (ex: 1.01, 1.01.1, 1.01.1.01)'
    )
    description = models.CharField(
        'Descrição',
        max_length=200
    )
    calculation_type = models.CharField(
        'Tipo de cálculo',
        max_length=20,
        choices=CALCULATION_TYPE_CHOICES,
        default='RULES',
        help_text='SUBTOTAL: totaliza filhos ou itens que acumulam. RULES: calcula por regras configuradas.'
    )
    accumulates_in = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='accumulated_items',
        verbose_name='Acumula em',
        help_text='Item onde este valor será acumulado (pode ser diferente do pai estrutural)'
    )
    calculation_rules = models.JSONField(
        default=list,
        blank=True,
        help_text="""
        Lista de regras de cálculo. Exemplos:
        
        Por subcategoria:
        [{"type": "subcategory", "subcategory_id": 5}]
        
        Por operação de ativo:
        [{"type": "asset_operation", "operation_type": "DIVIDEND"}]
        
        Por operação + tipo de ativo:
        [{"type": "asset_operation", "operation_type": "BUY", "asset_type": "STOCK"}]
        
        Múltiplas regras (soma todas):
        [
            {"type": "subcategory", "subcategory_id": 5},
            {"type": "asset_operation", "operation_type": "DIVIDEND"}
        ]
        """
    )
    order = models.IntegerField(
        'Ordem',
        default=0,
        help_text='Ordem de exibição'
    )
    
    class Meta:
        verbose_name = 'Item do Fluxo de Caixa'
        verbose_name_plural = 'Itens do Fluxo de Caixa'
        ordering = ('order', 'code')
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['calculation_type']),
            models.Index(fields=['accumulates_in']),
        ]
    
    def __str__(self):
        return f"{self.code} - {self.description}"
    
    def get_parent_code(self):
        """Retorna o código do pai baseado na hierarquia do código"""
        parts = self.code.split('.')
        if len(parts) > 1:
            return '.'.join(parts[:-1])
        return None
    
    def get_parent(self):
        """Retorna o item pai baseado no código"""
        parent_code = self.get_parent_code()
        if parent_code:
            try:
                return CashFlowItem.objects.get(code=parent_code)
            except CashFlowItem.DoesNotExist:
                return None
        return None
    
    def get_children(self):
        """Retorna todos os filhos diretos baseado no código"""
        # Filhos diretos: códigos que começam com self.code + "."
        # Mas não são netos (não têm mais pontos após)
        prefix = self.code + "."
        
        all_children = CashFlowItem.objects.filter(code__startswith=prefix)
        
        # Filtrar apenas filhos diretos (sem mais pontos após o prefix)
        direct_children = []
        for item in all_children:
            remaining = item.code[len(prefix):]
            if '.' not in remaining:  # Filho direto
                direct_children.append(item.code)
        
        return CashFlowItem.objects.filter(code__in=direct_children).order_by('code')
    
    def get_siblings(self):
        """Retorna todos os irmãos (mesmo pai hierárquico)"""
        parent_code = self.get_parent_code()
        if not parent_code:
            # Se não tem pai, retorna todos os itens de nível raiz
            return CashFlowItem.objects.filter(code__regex=r'^\d+$').exclude(pk=self.pk).order_by('code')
        
        # Buscar todos os filhos do mesmo pai
        siblings = CashFlowItem.objects.filter(
            code__startswith=parent_code + "."
        ).exclude(pk=self.pk)
        
        # Filtrar apenas irmãos diretos (mesmo nível)
        parent_level = parent_code.count('.')
        direct_siblings = []
        for item in siblings:
            if item.code.count('.') == parent_level + 1:
                direct_siblings.append(item.code)
        
        return CashFlowItem.objects.filter(code__in=direct_siblings).order_by('code')
    
    def get_next_sibling_code(self):
        """Calcula o próximo código irmão sequencial"""
        siblings = self.get_siblings()
        
        if not siblings.exists():
            # Se não tem irmãos, retorna próximo código sequencial
            parts = self.code.split('.')
            last_part = int(parts[-1])
            next_part = last_part + 1
            parts[-1] = str(next_part).zfill(len(parts[-1]))
            return '.'.join(parts)
        
        # Encontrar o maior código irmão
        max_code = None
        max_last_part = -1
        for sibling in siblings:
            sibling_parts = sibling.code.split('.')
            sibling_last_part = int(sibling_parts[-1])
            if sibling_last_part > max_last_part:
                max_last_part = sibling_last_part
                max_code = sibling.code
        
        # Incrementar o último número
        parts = max_code.split('.')
        last_part = int(parts[-1])
        next_part = last_part + 1
        parts[-1] = str(next_part).zfill(len(parts[-1]))
        return '.'.join(parts)
    
    def get_next_child_code(self):
        """Calcula o próximo código filho"""
        children = self.get_children()
        
        if not children.exists():
            # Se não tem filhos, retorna primeiro código filho
            return self.code + ".01"
        
        # Encontrar o maior código filho
        max_code = None
        max_last_part = -1
        for child in children:
            child_parts = child.code.split('.')
            child_last_part = int(child_parts[-1])
            if child_last_part > max_last_part:
                max_last_part = child_last_part
                max_code = child.code
        
        # Incrementar o último número
        parts = max_code.split('.')
        last_part = int(parts[-1])
        next_part = last_part + 1
        parts[-1] = str(next_part).zfill(2)  # Sempre 2 dígitos para filhos
        return '.'.join(parts)
    
    @classmethod
    def get_next_order_for_code(cls, code):
        """Calcula a ordem apropriada para um código baseado na posição hierárquica"""
        # Buscar todos os itens ordenados por ordem atual
        all_items = cls.objects.all().order_by('order', 'code')
        
        # Encontrar a maior ordem entre itens do mesmo nível ou anteriores
        parent_code = None
        parts = code.split('.')
        if len(parts) > 1:
            parent_code = '.'.join(parts[:-1])
        
        max_order = 0
        for item in all_items:
            # Se o item é do mesmo nível ou anterior na hierarquia
            item_level = item.code.count('.')
            code_level = code.count('.')
            
            if item_level <= code_level:
                if item.order > max_order:
                    max_order = item.order
        
        return max_order + 1
    
    @classmethod
    def find_next_available_code(cls, desired_code):
        """Encontra o próximo código disponível quando o código desejado já existe"""
        # Verificar se código já existe
        if not cls.objects.filter(code=desired_code).exists():
            return desired_code
        
        # Código existe, encontrar próximo disponível
        parts = desired_code.split('.')
        
        if len(parts) > 1:
            # Tem pai: encontrar próximo código irmão
            parent_code = '.'.join(parts[:-1])
            try:
                parent_item = cls.objects.get(code=parent_code)
                # Buscar todos os irmãos (filhos do mesmo pai)
                siblings = parent_item.get_children()
                
                # Encontrar maior número do último segmento
                max_last_part = int(parts[-1])
                for sibling in siblings:
                    sibling_parts = sibling.code.split('.')
                    sibling_last_part = int(sibling_parts[-1])
                    if sibling_last_part > max_last_part:
                        max_last_part = sibling_last_part
                
                # Próximo código disponível
                next_part = max_last_part + 1
                parts[-1] = str(next_part).zfill(len(parts[-1]))
                return '.'.join(parts)
            except cls.DoesNotExist:
                # Pai não existe, incrementar último segmento
                last_part = int(parts[-1])
                next_part = last_part + 1
                parts[-1] = str(next_part).zfill(len(parts[-1]))
                return '.'.join(parts)
        else:
            # Nível raiz: encontrar próximo código raiz disponível
            root_items = cls.objects.filter(code__regex=r'^\d+$')
            max_code = int(desired_code)
            for item in root_items:
                try:
                    item_code = int(item.code)
                    if item_code > max_code:
                        max_code = item_code
                except ValueError:
                    pass
            return str(max_code + 1)
    
    @classmethod
    def renumber_code_and_descendants(cls, old_code, new_code):
        """Renumerar item e todos os descendentes, atualizando também accumulates_in"""
        from django.db import transaction as db_transaction
        
        with db_transaction.atomic():
            # Buscar item a ser renumerado
            try:
                item = cls.objects.get(code=old_code)
            except cls.DoesNotExist:
                return
            
            # Buscar todos os descendentes (códigos que começam com old_code + ".")
            all_descendants = list(cls.objects.filter(code__startswith=old_code + "."))
            
            # Renumerar item principal
            item.code = new_code
            item.save()
            
            # Nota: accumulates_in é um ForeignKey (por ID), então itens que já referenciam
            # este item continuam referenciando corretamente mesmo após renumerar o código.
            # Não precisamos atualizar accumulates_in para o item principal.
            
            # Renumerar descendentes
            for descendant in all_descendants:
                # Substituir prefixo old_code por new_code
                old_descendant_code = descendant.code
                new_descendant_code = old_descendant_code.replace(old_code, new_code, 1)
                
                # Renumerar o descendente
                descendant.code = new_descendant_code
                descendant.save()
                
                # Nota: accumulates_in é um ForeignKey (por ID), então itens que já referenciam
                # este descendente continuam referenciando corretamente mesmo após renumerar.
                # Não precisamos atualizar accumulates_in para descendentes.
    
    @classmethod
    def reorganize_orders(cls):
        """Reorganizar ordens automaticamente para evitar conflitos"""
        from django.db import transaction as db_transaction
        
        with db_transaction.atomic():
            # Buscar todos os itens ordenados por código (hierarquia)
            all_items = cls.objects.all().order_by('code')
            
            # Atribuir ordens sequenciais baseado na posição
            order = 1
            for item in all_items:
                item.order = order
                item.save(update_fields=['order'])
                order += 1
    
    @classmethod
    def get_all_mapped_subcategory_ids(cls):
        """Retorna um set com todos os IDs de subcategorias mapeadas em CashFlowItem"""
        mapped_ids = set()
        cash_flow_items = cls.objects.filter(calculation_type='RULES')
        
        for item in cash_flow_items:
            if item.calculation_rules:
                for rule in item.calculation_rules:
                    if rule.get('type') == 'subcategory':
                        subcategory_id = rule.get('subcategory_id')
                        if subcategory_id:
                            mapped_ids.add(subcategory_id)
        
        return mapped_ids
    
    @classmethod
    def get_subcategory_mapping_count(cls):
        """Retorna um dicionário {subcategory_id: count} com a contagem de mapeamentos por subcategoria"""
        mapping_count = {}
        cash_flow_items = cls.objects.filter(calculation_type='RULES')
        
        for item in cash_flow_items:
            if item.calculation_rules:
                for rule in item.calculation_rules:
                    if rule.get('type') == 'subcategory':
                        subcategory_id = rule.get('subcategory_id')
                        if subcategory_id:
                            mapping_count[subcategory_id] = mapping_count.get(subcategory_id, 0) + 1
        
        return mapping_count
    
    def calculate_value(self, start_date, end_date, account=None):
        """Calcula o valor deste item baseado nas regras"""
        from decimal import Decimal
        
        if self.calculation_type == 'SUBTOTAL':
            total = Decimal('0')
            
            # Cenário 1: Totaliza filhos hierárquicos (se existirem)
            # Mas apenas filhos que não têm accumulates_in definido ou que acumulam no próprio pai
            children = self.get_children()
            children_codes = set()
            if children.exists():
                for child in children:
                    # Só somar se o filho não tem accumulates_in OU se acumula no próprio pai
                    if not child.accumulates_in or child.accumulates_in == self:
                        children_codes.add(child.code)
                        total += child.calculate_value(start_date, end_date, account)
            
            # Cenário 2: Acumula valores de itens que apontam para este
            # Buscar itens que têm accumulates_in apontando para este item
            # MAS excluir filhos hierárquicos que já foram somados (para evitar duplicação)
            accumulated_items = CashFlowItem.objects.filter(
                accumulates_in=self
            ).exclude(code__in=children_codes)
            
            for item in accumulated_items:
                # Calcular valor do item que acumula aqui
                item_value = item.calculate_value(start_date, end_date, account)
                total += item_value
            
            return total
        
        elif self.calculation_type == 'RULES':
            # Calcula por regras
            total = Decimal('0')
            for rule in self.calculation_rules:
                rule_type = rule.get('type')
                
                if rule_type == 'subcategory':
                    subcategory_id = rule.get('subcategory_id')
                    value = self._calculate_by_subcategory(
                        subcategory_id, start_date, end_date, account
                    )
                    total += value
                
                elif rule_type == 'asset_operation':
                    value = self._calculate_by_asset_operation(
                        rule, start_date, end_date, account
                    )
                    total += value
            
            return total
        
        return Decimal('0')
    
    def _calculate_by_subcategory(self, subcategory_id, start_date, end_date, account):
        """Calcula valor por subcategoria"""
        from django.db.models import Q
        from decimal import Decimal
        
        filters = {
            'subcategory_id': subcategory_id,
        }
        
        date_filter = Q(
            Q(transaction_date__gte=start_date, transaction_date__lte=end_date) |
            Q(transaction_date__isnull=True, due_date__gte=start_date, due_date__lte=end_date)
        )
        
        if account:
            filters['account'] = account
        
        transactions = Transaction.objects.filter(**filters).filter(date_filter)
        
        total = Decimal('0')
        for trans in transactions:
            if trans.transaction_type == 'CR':
                total += trans.value
            elif trans.transaction_type == 'DB':
                total -= trans.value
        
        return total
    
    def _calculate_by_asset_operation(self, rule, start_date, end_date, account):
        """Calcula valor por operação de ativo"""
        from decimal import Decimal
        
        filters = {
            'date__gte': start_date,
            'date__lte': end_date,
        }
        
        if 'operation_type' in rule:
            filters['operation_type'] = rule['operation_type']
        
        if 'asset_type' in rule:
            filters['asset__asset_type'] = rule['asset_type']
        
        if account:
            filters['account'] = account
        
        transactions = AssetTransaction.objects.filter(**filters)
        
        total = Decimal('0')
        for trans in transactions:
            total += trans.get_net_value()  # Já tem sinal correto
        
        return total
    
    def calculate_budget_value(self, start_date, end_date, account=None):
        """Calcula o valor orçado deste item baseado nas regras"""
        from decimal import Decimal
        
        if self.calculation_type == 'SUBTOTAL':
            total = Decimal('0')
            
            # Cenário 1: Totaliza filhos hierárquicos (se existirem)
            # Mas apenas filhos que não têm accumulates_in definido ou que acumulam no próprio pai
            children = self.get_children()
            children_codes = set()
            if children.exists():
                for child in children:
                    # Só somar se o filho não tem accumulates_in OU se acumula no próprio pai
                    if not child.accumulates_in or child.accumulates_in == self:
                        children_codes.add(child.code)
                        total += child.calculate_budget_value(start_date, end_date, account)
            
            # Cenário 2: Acumula valores de itens que apontam para este
            # Buscar itens que têm accumulates_in apontando para este item
            # MAS excluir filhos hierárquicos que já foram somados (para evitar duplicação)
            accumulated_items = CashFlowItem.objects.filter(
                accumulates_in=self
            ).exclude(code__in=children_codes)
            
            for item in accumulated_items:
                # Calcular valor do item que acumula aqui
                item_value = item.calculate_budget_value(start_date, end_date, account)
                total += item_value
            
            return total
        
        elif self.calculation_type == 'RULES':
            # Calcula por regras
            total = Decimal('0')
            for rule in self.calculation_rules:
                rule_type = rule.get('type')
                
                if rule_type == 'subcategory':
                    subcategory_id = rule.get('subcategory_id')
                    value = self._calculate_budget_by_subcategory(
                        subcategory_id, start_date, end_date, account
                    )
                    total += value
                
                # Nota: asset_operation não se aplica a budgets
                # elif rule_type == 'asset_operation':
                #     Não há orçamento para operações de ativo
            
            return total
        
        return Decimal('0')
    
    def _calculate_budget_by_subcategory(self, subcategory_id, start_date, end_date, account):
        """Calcula valor orçado por subcategoria"""
        from decimal import Decimal
        
        try:
            subcategory = Subcategory.objects.get(pk=subcategory_id)
        except Subcategory.DoesNotExist:
            return Decimal('0')
        
        # Budgets são armazenados por mês/ano (sempre dia 1)
        # Precisamos buscar todos os budgets cujo budget_date está dentro do período
        # budget_date está sempre no dia 1 do mês, então precisamos verificar se o mês/ano
        # está dentro do range de datas
        
        # Calcular o primeiro e último mês/ano do período
        start_year = start_date.year
        start_month = start_date.month
        end_year = end_date.year
        end_month = end_date.month
        
        # Buscar budgets da subcategoria no período
        # Usar Q objects para filtrar por range de datas
        from django.db.models import Q
        budgets = Budget.objects.filter(
            subcategory_id=subcategory_id,
            budget_date__gte=start_date.replace(day=1),
            budget_date__lte=end_date.replace(day=1)
        )
        
        total = Decimal('0')
        for budget in budgets:
            # Aplicar sinal baseado no tipo de transação padrão da subcategoria
            if subcategory.default_transaction_type == 'CR':
                total += budget.amount
            elif subcategory.default_transaction_type == 'DB':
                total -= budget.amount
        
        return total