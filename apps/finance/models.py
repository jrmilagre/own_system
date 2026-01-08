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
        decimal_places=6,
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
        if self.operation_type in ['BUY', 'SELL', 'SUB']:
            # Para compras: quantity * price + fees
            # Para vendas: quantity * price - fees
            if self.operation_type == 'BUY':
                self.total_value = (self.quantity * self.price) + self.fees
            elif self.operation_type == 'SELL':
                self.total_value = (self.quantity * self.price) - self.fees
            else:  # SUB
                self.total_value = (self.quantity * self.price) + self.fees
        elif self.operation_type in ['DIVIDEND', 'JCP', 'INTEREST', 'AMORTIZATION']:
            # Para rendimentos, usar income_value
            self.total_value = self.income_value
        elif self.operation_type in ['BONUS', 'SPLIT', 'GROUP', 'CAPITAL_INCREASE', 'RIGHTS_EXERCISE']:
            # Operações que não envolvem dinheiro
            self.total_value = 0
        
        super().save(*args, **kwargs)
    
    def get_net_value(self):
        """Retorna o valor líquido da operação"""
        if self.operation_type == 'BUY':
            return -self.total_value  # Saída de dinheiro
        elif self.operation_type == 'SELL':
            return self.total_value  # Entrada de dinheiro
        elif self.operation_type == 'SUB':
            return -self.total_value  # Saída de dinheiro (pagamento para exercer direito)
        elif self.operation_type == 'REDEMPTION':
            return self.total_value  # Entrada de dinheiro (resgate)
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
        decimal_places=6
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
