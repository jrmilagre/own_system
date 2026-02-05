from django import forms
from django.forms import formset_factory, inlineformset_factory, BaseFormSet
from .models import Account, Beneficiary, Category, Subcategory, Transaction, Scheduler, Asset, AssetTransaction, AssetPosition, Inventory, CashFlowItem, Budget, AssetTransactionCategoryConfig


class AccountForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ['name', 'account_type', 'currency', 'opening_balance']
        widgets = {
            'name': forms.TextInput(attrs={'required': True}),
            'account_type': forms.Select(attrs={'required': True}),
            'currency': forms.TextInput(attrs={'required': True}),
            'opening_balance': forms.NumberInput(attrs={'step': '0.01', 'required': True}),
        }


class BeneficiaryForm(forms.ModelForm):
    class Meta:
        model = Beneficiary
        fields = ['full_name']
        widgets = {
            'full_name': forms.TextInput(attrs={'required': True}),
        }


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['category']
        widgets = {
            'category': forms.TextInput(attrs={'required': True}),
        }


class SubcategoryForm(forms.ModelForm):
    class Meta:
        model = Subcategory
        fields = ['category', 'subcategory', 'default_transaction_type']
        widgets = {
            'category': forms.Select(attrs={'required': True}),
            'subcategory': forms.TextInput(attrs={'required': True}),
            'default_transaction_type': forms.Select(attrs={'required': True}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ordenar categoria alfabeticamente
        self.fields['category'].queryset = Category.objects.all().order_by('category')


class TransactionForm(forms.ModelForm):
    is_transfer = forms.BooleanField(
        required=False,
        label='É uma transferência entre contas',
        widget=forms.CheckboxInput()
    )
    source_account = forms.ModelChoiceField(
        queryset=Account.objects.all().order_by('name'),
        required=False,
        label='Conta de origem',
        widget=forms.Select(attrs={'required': False})
    )
    destination_account = forms.ModelChoiceField(
        queryset=Account.objects.all().order_by('name'),
        required=False,
        label='Conta de destino',
        widget=forms.Select(attrs={'required': False})
    )

    class Meta:
        model = Transaction
        fields = ['account', 'beneficiary', 'subcategory', 'transaction_type', 'value', 'due_date', 'transaction_date', 'purchase_date', 'notes']
        widgets = {
            'account': forms.Select(attrs={'required': False}),
            'beneficiary': forms.Select(attrs={'required': False}),
            'subcategory': forms.Select(attrs={'required': False}),
            'transaction_type': forms.Select(attrs={'required': False}),
            'value': forms.NumberInput(attrs={'step': '0.01', 'required': True}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'transaction_date': forms.DateInput(attrs={'type': 'date'}),
            'purchase_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Tornar account não obrigatório por padrão (será validado no clean)
        self.fields['account'].required = False
        self.fields['transaction_type'].required = False
        # Ordenar campos alfabeticamente
        self.fields['account'].queryset = Account.objects.all().order_by('name')
        self.fields['beneficiary'].queryset = Beneficiary.objects.all().order_by('full_name')
        self.fields['subcategory'].queryset = Subcategory.objects.all().order_by('category__category', 'subcategory')

    def clean(self):
        cleaned_data = super().clean()
        is_transfer = cleaned_data.get('is_transfer', False)
        
        if is_transfer:
            source_account = cleaned_data.get('source_account')
            destination_account = cleaned_data.get('destination_account')
            
            if not source_account:
                raise forms.ValidationError({
                    'source_account': 'Conta de origem é obrigatória para transferências.'
                })
            
            if not destination_account:
                raise forms.ValidationError({
                    'destination_account': 'Conta de destino é obrigatória para transferências.'
                })
            
            if source_account == destination_account:
                raise forms.ValidationError({
                    'destination_account': 'A conta de destino deve ser diferente da conta de origem.'
                })
        else:
            # Para transações normais, validar campos obrigatórios
            account = cleaned_data.get('account')
            beneficiary = cleaned_data.get('beneficiary')
            subcategory = cleaned_data.get('subcategory')
            transaction_type = cleaned_data.get('transaction_type')
            
            if not account:
                raise forms.ValidationError({
                    'account': 'Conta é obrigatória para transações normais.'
                })
            
            if not beneficiary:
                raise forms.ValidationError({
                    'beneficiary': 'Beneficiário é obrigatório para transações normais.'
                })
            
            if not subcategory:
                raise forms.ValidationError({
                    'subcategory': 'Subcategoria é obrigatória para transações normais.'
                })
            
            if not transaction_type:
                raise forms.ValidationError({
                    'transaction_type': 'Tipo de transação é obrigatório para transações normais.'
                })
        
        return cleaned_data


class TransferTransactionForm(forms.Form):
    """Formulário específico para transferências entre contas"""
    source_account = forms.ModelChoiceField(
        queryset=Account.objects.all().order_by('name'),
        required=True,
        label='Conta de origem',
        widget=forms.Select(attrs={'required': True})
    )
    destination_account = forms.ModelChoiceField(
        queryset=Account.objects.all().order_by('name'),
        required=True,
        label='Conta de destino',
        widget=forms.Select(attrs={'required': True})
    )
    value = forms.DecimalField(
        required=True,
        label='Valor',
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'step': '0.01', 'required': True})
    )
    due_date = forms.DateField(
        required=False,
        label='Data do vencimento',
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    transaction_date = forms.DateField(
        required=False,
        label='Data da transação',
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    purchase_date = forms.DateField(
        required=False,
        label='Data da compra',
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    notes = forms.CharField(
        required=False,
        label='Anotações',
        widget=forms.Textarea(attrs={'rows': 4})
    )

    def clean(self):
        cleaned_data = super().clean()
        source_account = cleaned_data.get('source_account')
        destination_account = cleaned_data.get('destination_account')
        
        if source_account and destination_account:
            if source_account == destination_account:
                raise forms.ValidationError({
                    'destination_account': 'A conta de destino deve ser diferente da conta de origem.'
                })
        
        return cleaned_data


class SchedulerForm(forms.ModelForm):
    class Meta:
        model = Scheduler
        fields = [
            'account', 'beneficiary', 'subcategory', 'transaction_type', 'value', 'due_date', 'purchase_date', 'notes',
            'recurrence_type', 'recurrence_interval',
            'termination_type', 'remaining_installments', 'final_date',
            'status'
        ]
        widgets = {
            'account': forms.Select(attrs={'required': True}),
            'beneficiary': forms.Select(attrs={'required': True}),
            'subcategory': forms.Select(attrs={'required': True}),
            'transaction_type': forms.Select(attrs={'required': True}),
            'value': forms.NumberInput(attrs={'step': '0.01', 'required': True}),
            'due_date': forms.DateInput(attrs={'type': 'date', 'required': True}),
            'purchase_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 4}),
            'recurrence_type': forms.Select(attrs={'required': True}),
            'recurrence_interval': forms.NumberInput(attrs={'min': 1, 'required': True}),
            'termination_type': forms.Select(attrs={'required': True}),
            'remaining_installments': forms.NumberInput(attrs={'min': 1}),
            'final_date': forms.DateInput(attrs={'type': 'date'}),
            'status': forms.Select(attrs={'required': True}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ordenar campos alfabeticamente
        self.fields['account'].queryset = Account.objects.all().order_by('name')
        self.fields['beneficiary'].queryset = Beneficiary.objects.all().order_by('full_name')
        self.fields['subcategory'].queryset = Subcategory.objects.all().order_by('category__category', 'subcategory')
        # Forçar avaliação dos querysets para evitar problemas com cursor do banco
        # durante a renderização do template
        list(self.fields['account'].queryset)
        list(self.fields['beneficiary'].queryset)
        list(self.fields['subcategory'].queryset)

    def clean(self):
        cleaned_data = super().clean()
        recurrence_type = cleaned_data.get('recurrence_type')
        termination_type = cleaned_data.get('termination_type')
        remaining_installments = cleaned_data.get('remaining_installments')
        final_date = cleaned_data.get('final_date')

        # Se for agendamento único (sem recorrência), não validar campos de recorrência e término
        if recurrence_type == 'NONE':
            # Limpar campos de recorrência e término para agendamentos únicos
            cleaned_data['recurrence_interval'] = 1
            cleaned_data['termination_type'] = 'INFINITE'
            cleaned_data['remaining_installments'] = None
            cleaned_data['final_date'] = None
            return cleaned_data

        if termination_type == 'INSTALLMENTS':
            if not remaining_installments or remaining_installments <= 0:
                raise forms.ValidationError({
                    'remaining_installments': 'Número de parcelas é obrigatório quando o tipo de término é "Número de parcelas".'
                })

        if termination_type == 'FINAL_DATE':
            if not final_date:
                raise forms.ValidationError({
                    'final_date': 'Data final é obrigatória quando o tipo de término é "Data final".'
                })

        return cleaned_data


class MultipleTransactionItemForm(forms.Form):
    """Formulário para cada item de uma transação múltipla"""
    transaction_type = forms.ChoiceField(
        choices=[('CR', 'Crédito'), ('DB', 'Débito')],
        label='Tipo',
        required=True
    )
    subcategory = forms.ModelChoiceField(
        queryset=Subcategory.objects.all().order_by('category__category', 'subcategory'),
        label='Subcategoria',
        required=False
    )
    value = forms.DecimalField(
        label='Valor',
        max_digits=12,
        decimal_places=2,
        required=True,
        widget=forms.NumberInput(attrs={'step': '0.01'})
    )
    is_transfer = forms.BooleanField(
        label='É transferência',
        required=False,
        widget=forms.CheckboxInput()
    )
    destination_account = forms.ModelChoiceField(
        queryset=Account.objects.all().order_by('name'),
        label='Conta de destino',
        required=False
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Forçar avaliação dos querysets para evitar problemas com cursor do banco
        # durante a renderização do template
        if self.fields['subcategory'].queryset:
            list(self.fields['subcategory'].queryset)
        if self.fields['destination_account'].queryset:
            list(self.fields['destination_account'].queryset)

    def clean(self):
        cleaned_data = super().clean()
        is_transfer = cleaned_data.get('is_transfer', False)
        
        if is_transfer:
            destination_account = cleaned_data.get('destination_account')
            
            if not destination_account:
                raise forms.ValidationError({
                    'destination_account': 'Conta de destino é obrigatória para transferências.'
                })
        else:
            # Para transações normais, validar campos obrigatórios
            subcategory = cleaned_data.get('subcategory')
            
            if not subcategory:
                raise forms.ValidationError({
                    'subcategory': 'Subcategoria é obrigatória para transações normais.'
                })
        
        return cleaned_data


MultipleTransactionItemFormSet = formset_factory(
    MultipleTransactionItemForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True
)


class MultipleTransactionForm(forms.Form):
    """Formulário base para transação múltipla com campos compartilhados"""
    account = forms.ModelChoiceField(
        queryset=Account.objects.all().order_by('name'),
        label='Conta',
        required=True
    )
    beneficiary = forms.ModelChoiceField(
        queryset=Beneficiary.objects.all().order_by('full_name'),
        label='Beneficiário',
        required=True
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Forçar avaliação dos querysets para evitar problemas com cursor do banco
        # durante a renderização do template
        if self.fields['account'].queryset:
            list(self.fields['account'].queryset)
        if self.fields['beneficiary'].queryset:
            list(self.fields['beneficiary'].queryset)
    due_date = forms.DateField(
        label='Data do vencimento',
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    transaction_date = forms.DateField(
        label='Data da transação',
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    purchase_date = forms.DateField(
        label='Data da compra',
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    notes = forms.CharField(
        label='Anotações',
        required=False,
        widget=forms.Textarea(attrs={'rows': 4})
    )


class MultipleSchedulerItemForm(forms.Form):
    """Formulário para cada item de um agendamento múltiplo"""
    transaction_type = forms.ChoiceField(
        choices=[('CR', 'Crédito'), ('DB', 'Débito')],
        label='Tipo',
        required=False  # Será validado no clean() baseado em is_transfer
    )
    subcategory = forms.ModelChoiceField(
        queryset=Subcategory.objects.all().order_by('category__category', 'subcategory'),
        label='Subcategoria',
        required=False
    )
    value = forms.DecimalField(
        label='Valor',
        max_digits=12,
        decimal_places=2,
        required=True,
        widget=forms.NumberInput(attrs={'step': '0.01'})
    )
    is_transfer = forms.BooleanField(
        label='É transferência',
        required=False,
        widget=forms.CheckboxInput()
    )
    destination_account = forms.ModelChoiceField(
        queryset=Account.objects.all().order_by('name'),
        label='Conta de destino',
        required=False
    )
    notes = forms.CharField(
        label='Anotações',
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Forçar avaliação dos querysets para evitar problemas com cursor do banco
        # durante a renderização do template
        if self.fields['subcategory'].queryset:
            list(self.fields['subcategory'].queryset)
        if self.fields['destination_account'].queryset:
            list(self.fields['destination_account'].queryset)

    def clean(self):
        cleaned_data = super().clean()
        is_transfer = cleaned_data.get('is_transfer', False)
        
        if is_transfer:
            destination_account = cleaned_data.get('destination_account')
            
            if not destination_account:
                raise forms.ValidationError({
                    'destination_account': 'Conta de destino é obrigatória para transferências.'
                })
        else:
            # Para transações normais, validar campos obrigatórios
            subcategory = cleaned_data.get('subcategory')
            transaction_type = cleaned_data.get('transaction_type')
            
            if not subcategory:
                raise forms.ValidationError({
                    'subcategory': 'Subcategoria é obrigatória para transações normais.'
                })
            
            if not transaction_type:
                raise forms.ValidationError({
                    'transaction_type': 'Tipo de transação é obrigatório para transações normais.'
                })
        
        return cleaned_data


class MultipleSchedulerItemFormSetBase(BaseFormSet):
    """Formset customizado que ignora formulários completamente vazios"""
    
    def clean(self):
        """Valida o formset, ignorando formulários completamente vazios"""
        if any(self.errors):
            return
        
        # Contar apenas formulários não vazios e não deletados
        non_empty_forms = 0
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                # Verificar se o formulário tem pelo menos um campo preenchido
                has_value = form.cleaned_data.get('value')
                if has_value:
                    non_empty_forms += 1
        
        if non_empty_forms < 1:
            raise forms.ValidationError('É necessário pelo menos um item válido.')


MultipleSchedulerItemFormSet = formset_factory(
    MultipleSchedulerItemForm,
    formset=MultipleSchedulerItemFormSetBase,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True
)


class MultipleSchedulerForm(forms.Form):
    """Formulário base para agendamento múltiplo com campos compartilhados"""
    account = forms.ModelChoiceField(
        queryset=Account.objects.all().order_by('name'),
        label='Conta',
        required=True
    )
    beneficiary = forms.ModelChoiceField(
        queryset=Beneficiary.objects.all().order_by('full_name'),
        label='Beneficiário',
        required=True
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Forçar avaliação dos querysets para evitar problemas com cursor do banco
        # durante a renderização do template
        if self.fields['account'].queryset:
            list(self.fields['account'].queryset)
        if self.fields['beneficiary'].queryset:
            list(self.fields['beneficiary'].queryset)
    due_date = forms.DateField(
        label='Data do vencimento',
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    purchase_date = forms.DateField(
        label='Data da compra',
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    notes = forms.CharField(
        label='Anotações',
        required=False,
        widget=forms.Textarea(attrs={'rows': 4})
    )
    recurrence_type = forms.ChoiceField(
        choices=Scheduler.RECURRENCE_TYPE_CHOICES,
        label='Tipo de recorrência',
        required=True,
        initial='NONE'
    )
    recurrence_interval = forms.IntegerField(
        label='Intervalo da recorrência',
        required=True,
        initial=1,
        min_value=1,
        widget=forms.NumberInput(attrs={'min': 1})
    )
    termination_type = forms.ChoiceField(
        choices=Scheduler.TERMINATION_TYPE_CHOICES,
        label='Tipo de término',
        required=True,
        initial='INFINITE'
    )
    remaining_installments = forms.IntegerField(
        label='Parcelas restantes',
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={'min': 1})
    )
    final_date = forms.DateField(
        label='Data final',
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    status = forms.ChoiceField(
        choices=Scheduler.STATUS_CHOICES,
        label='Status',
        required=True,
        initial='ACTIVE'
    )

    def clean(self):
        cleaned_data = super().clean()
        termination_type = cleaned_data.get('termination_type')
        remaining_installments = cleaned_data.get('remaining_installments')
        final_date = cleaned_data.get('final_date')

        if termination_type == 'INSTALLMENTS':
            if not remaining_installments or remaining_installments <= 0:
                raise forms.ValidationError({
                    'remaining_installments': 'Número de parcelas é obrigatório quando o tipo de término é "Número de parcelas".'
                })

        if termination_type == 'FINAL_DATE':
            if not final_date:
                raise forms.ValidationError({
                    'final_date': 'Data final é obrigatória quando o tipo de término é "Data final".'
                })

        return cleaned_data


class MultipleSchedulerRegisterItemForm(forms.Form):
    """Formulário para editar item antes do registro"""
    subcategory = forms.ModelChoiceField(
        queryset=Subcategory.objects.all().order_by('category__category', 'subcategory'),
        label='Subcategoria',
        required=False
    )
    transaction_type = forms.ChoiceField(
        choices=[('CR', 'Crédito'), ('DB', 'Débito')],
        label='Tipo',
        required=False  # Será validado no clean() baseado em is_transfer
    )
    value = forms.DecimalField(
        label='Valor',
        max_digits=12,
        decimal_places=2,
        required=True,
        widget=forms.NumberInput(attrs={'step': '0.01'})
    )
    is_transfer = forms.BooleanField(
        label='É transferência',
        required=False,
        widget=forms.CheckboxInput()
    )
    destination_account = forms.ModelChoiceField(
        queryset=Account.objects.all().order_by('name'),
        label='Conta de destino',
        required=False
    )

    def clean(self):
        cleaned_data = super().clean()
        is_transfer = cleaned_data.get('is_transfer', False)
        
        if is_transfer:
            destination_account = cleaned_data.get('destination_account')
            
            if not destination_account:
                raise forms.ValidationError({
                    'destination_account': 'Conta de destino é obrigatória para transferências.'
                })
        else:
            # Para transações normais, validar campos obrigatórios
            subcategory = cleaned_data.get('subcategory')
            transaction_type = cleaned_data.get('transaction_type')
            
            if not subcategory:
                raise forms.ValidationError({
                    'subcategory': 'Subcategoria é obrigatória para transações normais.'
                })
            
            if not transaction_type:
                raise forms.ValidationError({
                    'transaction_type': 'Tipo de transação é obrigatório para transações normais.'
                })
        
        return cleaned_data


MultipleSchedulerRegisterItemFormSet = formset_factory(
    MultipleSchedulerRegisterItemForm,
    extra=0,
    can_delete=False,
    min_num=1,
    validate_min=True
)


class AssetForm(forms.ModelForm):
    class Meta:
        model = Asset
        fields = ['code', 'name', 'asset_type', 'sector', 'currency', 'notes']
        widgets = {
            'code': forms.TextInput(attrs={'required': True}),
            'name': forms.TextInput(attrs={'required': True}),
            'asset_type': forms.Select(attrs={'required': True}),
            'sector': forms.TextInput(attrs={'required': False}),
            'currency': forms.TextInput(attrs={'required': True}),
            'notes': forms.Textarea(attrs={'rows': 4, 'required': False}),
        }


class AssetTransactionForm(forms.ModelForm):
    cash_account = forms.ModelChoiceField(
        queryset=Account.objects.none(),
        required=False,
        label='Conta Cash',
        empty_label='Selecione uma conta',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    class Meta:
        model = AssetTransaction
        fields = ['asset', 'account', 'operation_type', 'date', 'quantity', 'price', 'total_value', 'fees', 'income_value', 'notes', 'assessoria', 'invoice']
        widgets = {
            'asset': forms.Select(attrs={'required': True}),
            'account': forms.Select(attrs={'required': True}),
            'operation_type': forms.Select(attrs={'required': True}),
            'date': forms.DateInput(attrs={'type': 'date', 'required': True}),
            'quantity': forms.NumberInput(attrs={'step': '0.00000001', 'required': False}),
            'price': forms.NumberInput(attrs={'step': '0.0001', 'required': False}),
            'total_value': forms.NumberInput(attrs={'step': '0.01', 'required': False}),
            'fees': forms.NumberInput(attrs={'step': '0.01', 'required': False}),
            'income_value': forms.NumberInput(attrs={'step': '0.01', 'required': False}),
            'notes': forms.Textarea(attrs={'rows': 4, 'required': False}),
            'assessoria': forms.CheckboxInput(attrs={'class': 'form-check-input', 'required': False}),
            'invoice': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 100, 'required': False}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrar contas do tipo INVEST para o campo account e ordenar
        self.fields['account'].queryset = Account.objects.filter(account_type='INVEST').order_by('name')
        # Renomear label do campo account
        self.fields['account'].label = 'Conta Investimento'
        
        # Filtrar contas para o campo cash_account
        # Para PORTABILITY: permitir contas de investimento (portabilidade entre contas INVEST)
        # Para outros tipos: apenas BANK, CASH, CREDCARD (não INVEST)
        operation_type = self.instance.operation_type if self.instance and self.instance.pk else None
        if not operation_type and 'operation_type' in self.data:
            operation_type = self.data.get('operation_type')
        
        if operation_type == 'PORTABILITY':
            # Para portabilidade, permitir contas de investimento
            self.fields['cash_account'].queryset = Account.objects.filter(
                account_type='INVEST'
            ).order_by('name')
        else:
            # Para outros tipos, excluir contas de investimento
            self.fields['cash_account'].queryset = Account.objects.filter(
                account_type__in=['BANK', 'CASH', 'CREDCARD']
            ).order_by('name')
        
        # Se for edição, tentar obter cash_account das Transactions relacionadas
        if self.instance and self.instance.pk:
            from .models import Transaction
            # Buscar Transaction de débito relacionada que não seja da conta de investimento
            related_transactions = Transaction.objects.filter(
                asset_transaction=self.instance, 
                is_transfer=True
            )
            if related_transactions.exists():
                # Pegar a primeira transaction de débito que não seja da conta de investimento
                for trans in related_transactions.filter(transaction_type='DB'):
                    if trans.account != self.instance.account:
                        self.fields['cash_account'].initial = trans.account
                        break

    def clean(self):
        cleaned_data = super().clean()
        operation_type = cleaned_data.get('operation_type')
        quantity = cleaned_data.get('quantity', 0)
        price = cleaned_data.get('price', 0)
        fees = cleaned_data.get('fees', 0)
        income_value = cleaned_data.get('income_value', 0)

        # Validações baseadas no tipo de operação
        if operation_type in ['BUY', 'SELL', 'SUB', 'REDEMPTION']:
            if quantity <= 0:
                raise forms.ValidationError({
                    'quantity': 'Quantidade deve ser maior que zero para este tipo de operação.'
                })
            if price <= 0:
                raise forms.ValidationError({
                    'price': 'Preço deve ser maior que zero para este tipo de operação.'
                })
        elif operation_type in ['BONUS', 'SPLIT', 'GROUP', 'CAPITAL_INCREASE', 'RIGHTS_EXERCISE']:
            if quantity <= 0:
                raise forms.ValidationError({
                    'quantity': 'Quantidade deve ser maior que zero para este tipo de operação.'
                })
        elif operation_type in ['DIVIDEND', 'JCP', 'INTEREST', 'AMORTIZATION']:
            if income_value <= 0:
                raise forms.ValidationError({
                    'income_value': 'Valor de rendimento deve ser maior que zero para este tipo de operação.'
                })
        elif operation_type == 'TRANSFER_IN':
            if quantity <= 0:
                raise forms.ValidationError({
                    'quantity': 'Quantidade deve ser maior que zero para transferência de entrada.'
                })
            if price <= 0:
                raise forms.ValidationError({
                    'price': 'Preço deve ser maior que zero para transferência de entrada.'
                })
        elif operation_type == 'PORTABILITY':
            if quantity <= 0:
                raise forms.ValidationError({
                    'quantity': 'Quantidade deve ser maior que zero para portabilidade.'
                })
            if price <= 0:
                raise forms.ValidationError({
                    'price': 'Preço deve ser maior que zero para portabilidade.'
                })
            cash_account = cleaned_data.get('cash_account')
            if not cash_account:
                raise forms.ValidationError({
                    'cash_account': 'Conta de destino é obrigatória para portabilidade.'
                })
            if cash_account.account_type != 'INVEST':
                raise forms.ValidationError({
                    'cash_account': 'A conta de destino deve ser uma conta de investimento para portabilidade.'
                })

        return cleaned_data


class MultipleAssetTransactionItemForm(forms.Form):
    """Formulário para cada item de uma transação múltipla de ativos"""
    asset = forms.ModelChoiceField(
        queryset=Asset.objects.all().order_by('code'),
        label='Ativo',
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    quantity = forms.DecimalField(
        label='Quantidade',
        max_digits=15,
        decimal_places=8,
        required=True,
        widget=forms.NumberInput(attrs={'step': '0.00000001', 'class': 'form-control'})
    )
    price = forms.DecimalField(
        label='Preço unitário',
        max_digits=12,
        decimal_places=4,
        required=True,
        widget=forms.NumberInput(attrs={'step': '0.0001', 'class': 'form-control'})
    )
    total_value = forms.DecimalField(
        label='Valor total',
        max_digits=12,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control', 'readonly': True})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Forçar avaliação do queryset para evitar problemas com cursor do banco
        if self.fields['asset'].queryset:
            list(self.fields['asset'].queryset)
    
    def clean(self):
        cleaned_data = super().clean()
        quantity = cleaned_data.get('quantity', 0)
        price = cleaned_data.get('price', 0)
        
        if quantity <= 0:
            raise forms.ValidationError({
                'quantity': 'Quantidade deve ser maior que zero.'
            })
        
        if price <= 0:
            raise forms.ValidationError({
                'price': 'Preço deve ser maior que zero.'
            })
        
        # Calcular total_value se não foi preenchido
        if not cleaned_data.get('total_value'):
            cleaned_data['total_value'] = quantity * price
        
        return cleaned_data


MultipleAssetTransactionItemFormSet = formset_factory(
    MultipleAssetTransactionItemForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True
)


class MultipleAssetTransactionForm(forms.Form):
    """Formulário base para transação múltipla de ativos com campos compartilhados"""
    account = forms.ModelChoiceField(
        queryset=Account.objects.filter(account_type='INVEST').order_by('name'),
        label='Conta Investimento',
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    operation_type = forms.ChoiceField(
        choices=AssetTransaction.OPERATION_TYPE_CHOICES,
        label='Tipo de operação',
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    date = forms.DateField(
        label='Data da operação',
        required=True,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    fees = forms.DecimalField(
        label='Taxas e impostos (total)',
        max_digits=12,
        decimal_places=2,
        required=True,
        initial=0,
        widget=forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control'})
    )
    cash_account = forms.ModelChoiceField(
        queryset=Account.objects.none(),
        required=False,
        label='Conta Cash',
        empty_label='Selecione uma conta',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    notes = forms.CharField(
        label='Observações',
        required=False,
        widget=forms.Textarea(attrs={'rows': 4, 'class': 'form-control'})
    )
    assessoria = forms.BooleanField(
        label='Assessoria',
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    invoice = forms.CharField(
        label='Nota Fiscal',
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'maxlength': 100})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Forçar avaliação dos querysets para evitar problemas com cursor do banco
        if self.fields['account'].queryset:
            list(self.fields['account'].queryset)
        
        # Filtrar contas para o campo cash_account baseado no operation_type
        operation_type = self.data.get('operation_type') if self.data else None
        if not operation_type and 'operation_type' in self.initial:
            operation_type = self.initial.get('operation_type')
        
        if operation_type == 'PORTABILITY':
            # Para portabilidade, permitir contas de investimento
            self.fields['cash_account'].queryset = Account.objects.filter(
                account_type='INVEST'
            ).order_by('name')
        else:
            # Para outros tipos, excluir contas de investimento
            self.fields['cash_account'].queryset = Account.objects.filter(
                account_type__in=['BANK', 'CASH', 'CREDCARD']
            ).order_by('name')
    
    def clean(self):
        cleaned_data = super().clean()
        operation_type = cleaned_data.get('operation_type')
        fees = cleaned_data.get('fees', 0)
        
        if fees < 0:
            raise forms.ValidationError({
                'fees': 'Taxas e impostos não podem ser negativos.'
            })
        
        # Validar cash_account para operações que requerem
        cash_account = cleaned_data.get('cash_account')
        operations_with_cash_account = ['BUY', 'SELL', 'DIVIDEND', 'JCP', 'INTEREST', 'AMORTIZATION', 'REDEMPTION', 'SUB']
        
        if operation_type in operations_with_cash_account and not cash_account:
            # Não é obrigatório, mas recomendado
            pass
        
        if operation_type == 'PORTABILITY':
            if not cash_account:
                raise forms.ValidationError({
                    'cash_account': 'Conta de destino é obrigatória para portabilidade.'
                })
            if cash_account and cash_account.account_type != 'INVEST':
                raise forms.ValidationError({
                    'cash_account': 'A conta de destino deve ser uma conta de investimento para portabilidade.'
                })
        
        return cleaned_data


class AssetPositionForm(forms.ModelForm):
    class Meta:
        model = AssetPosition
        fields = ['asset', 'account', 'date', 'quantity', 'average_cost', 'current_price']
        widgets = {
            'asset': forms.Select(attrs={'required': True}),
            'account': forms.Select(attrs={'required': True}),
            'date': forms.DateInput(attrs={'type': 'date', 'required': True}),
            'quantity': forms.NumberInput(attrs={'step': '0.00000001', 'required': True}),
            'average_cost': forms.NumberInput(attrs={'step': '0.0001', 'required': True}),
            'current_price': forms.NumberInput(attrs={'step': '0.0001', 'required': False}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrar contas do tipo INVEST para o campo account e ordenar
        self.fields['account'].queryset = Account.objects.filter(account_type='INVEST').order_by('name')


class InventoryForm(forms.ModelForm):
    class Meta:
        model = Inventory
        fields = [
            'type', 'description', 'buy_price', 'buy_date', 'actual_price',
            'brand', 'model', 'serial_number', 'condition', 'status', 'location',
            'warranty_end_date', 'sale_date', 'sale_price', 'purchase_transaction', 'notes'
        ]
        widgets = {
            'type': forms.Select(attrs={'required': True}),
            'description': forms.TextInput(attrs={'required': True}),
            'buy_price': forms.NumberInput(attrs={'step': '0.01', 'required': True}),
            'buy_date': forms.DateInput(attrs={'type': 'date', 'required': True}),
            'actual_price': forms.NumberInput(attrs={'step': '0.01', 'required': False}),
            'brand': forms.TextInput(attrs={'required': False}),
            'model': forms.TextInput(attrs={'required': False}),
            'serial_number': forms.TextInput(attrs={'required': False}),
            'condition': forms.Select(attrs={'required': True}),
            'status': forms.Select(attrs={'required': True}),
            'location': forms.TextInput(attrs={'required': False}),
            'warranty_end_date': forms.DateInput(attrs={'type': 'date', 'required': False}),
            'sale_date': forms.DateInput(attrs={'type': 'date', 'required': False}),
            'sale_price': forms.NumberInput(attrs={'step': '0.01', 'required': False}),
            'purchase_transaction': forms.Select(attrs={'required': False}),
            'notes': forms.Textarea(attrs={'rows': 4, 'required': False}),
        }


class CashFlowCalculationRuleForm(forms.Form):
    """Formulário para cada regra de cálculo"""
    
    RULE_TYPE_CHOICES = [
        ('subcategory', 'Por Subcategoria'),
        ('transfer', 'Por Transferência entre Contas'),
        ('asset_transaction', 'Por Transação de Ativo'),
    ]
    
    VALUE_TYPE_CHOICES = [
        ('debit', 'Débito (origem)'),
        ('credit', 'Crédito (destino)'),
    ]
    
    # Campo para tipo de regra
    rule_type = forms.ChoiceField(
        choices=RULE_TYPE_CHOICES,
        label='Tipo de Regra',
        required=True,
        initial='subcategory',
        widget=forms.Select(attrs={'class': 'rule-type-field form-select'})
    )
    
    # Campo para regra de subcategoria (condicional)
    subcategory = forms.ModelChoiceField(
        queryset=Subcategory.objects.all().order_by('category__category', 'subcategory'),
        label='Subcategoria',
        required=False,
        widget=forms.Select(attrs={'class': 'subcategory-field form-select'})
    )
    
    # Campos para regra de transferência (condicionais)
    destination_account = forms.ModelChoiceField(
        queryset=Account.objects.all().order_by('name'),
        label='Conta de Destino',
        required=False,
        widget=forms.Select(attrs={'class': 'destination-account-field form-select'})
    )
    
    value_type = forms.ChoiceField(
        choices=VALUE_TYPE_CHOICES,
        label='Tipo de Valor',
        required=False,
        widget=forms.Select(attrs={'class': 'value-type-field form-select'})
    )
    
    # Campos para regra de transação de ativo (condicionais)
    OPERATION_TYPE_CHOICES = [
        ('', 'Todos'),
        ('BUY', 'Compra'),
        ('SELL', 'Venda'),
        ('DIVIDEND', 'Dividendo'),
        ('JCP', 'Juros sobre Capital Próprio'),
        ('INTEREST', 'Juros (Renda Fixa)'),
        ('AMORTIZATION', 'Amortização'),
        ('REDEMPTION', 'Resgate (Renda Fixa)'),
        ('SUB', 'Subscrição'),
        ('TRANSFER_IN', 'Transferência Entrada'),
        ('PORTABILITY', 'Portabilidade'),
    ]
    
    ASSET_TYPE_CHOICES = [
        ('', 'Todos'),
        ('STOCK', 'Ação'),
        ('FII', 'Fundo Imobiliário'),
        ('ETF', 'ETF'),
        ('BOND', 'Renda Fixa'),
        ('REIT', 'REIT'),
        ('CRYPTO', 'Criptomoeda'),
        ('OTHER', 'Outro'),
    ]
    
    ASSET_VALUE_TYPE_CHOICES = [
        ('net_value', 'Valor Líquido (net_value)'),
        ('total_value', 'Valor Total (total_value)'),
        ('income_value', 'Valor de Rendimento (income_value)'),
    ]
    
    operation_type = forms.ChoiceField(
        choices=OPERATION_TYPE_CHOICES,
        label='Tipo de Operação',
        required=False,
        widget=forms.Select(attrs={'class': 'operation-type-field form-select'})
    )
    
    asset_type = forms.ChoiceField(
        choices=ASSET_TYPE_CHOICES,
        label='Tipo de Ativo',
        required=False,
        widget=forms.Select(attrs={'class': 'asset-type-field form-select'})
    )
    
    asset_value_type = forms.ChoiceField(
        choices=ASSET_VALUE_TYPE_CHOICES,
        label='Tipo de Valor',
        required=False,
        initial='net_value',
        widget=forms.Select(attrs={'class': 'asset-value-type-field form-select'})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        rule_type = cleaned_data.get('rule_type')
        
        if rule_type == 'subcategory':
            if not cleaned_data.get('subcategory'):
                raise forms.ValidationError({
                    'subcategory': 'Subcategoria é obrigatória para regras de subcategoria.'
                })
        elif rule_type == 'transfer':
            if not cleaned_data.get('destination_account'):
                raise forms.ValidationError({
                    'destination_account': 'Conta de destino é obrigatória para regras de transferência.'
                })
            if not cleaned_data.get('value_type'):
                raise forms.ValidationError({
                    'value_type': 'Tipo de valor é obrigatório para regras de transferência.'
                })
        elif rule_type == 'asset_transaction':
            if not cleaned_data.get('operation_type'):
                raise forms.ValidationError({
                    'operation_type': 'Tipo de operação é obrigatório para regras de transação de ativo.'
                })
            if not cleaned_data.get('asset_value_type'):
                raise forms.ValidationError({
                    'asset_value_type': 'Tipo de valor é obrigatório para regras de transação de ativo.'
                })
        
        return cleaned_data


CashFlowCalculationRuleFormSet = formset_factory(
    CashFlowCalculationRuleForm,
    extra=1,
    can_delete=True,
    min_num=0
)


class CashFlowItemForm(forms.ModelForm):
    class Meta:
        model = CashFlowItem
        fields = ['code', 'description', 'calculation_type', 'accumulates_in', 'order']
        widgets = {
            'code': forms.TextInput(attrs={'required': True}),
            'description': forms.TextInput(attrs={'required': True}),
            'calculation_type': forms.Select(attrs={'id': 'id_calculation_type'}),
            'accumulates_in': forms.Select(attrs={'required': False}),
            'order': forms.NumberInput(attrs={'min': 0}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrar accumulates_in para não incluir o próprio item
        if self.instance and self.instance.pk:
            self.fields['accumulates_in'].queryset = CashFlowItem.objects.exclude(
                pk=self.instance.pk
            )
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Converter formset em JSON
        if hasattr(self, 'rules_formset'):
            rules_data = []
            for form in self.rules_formset:
                # Verificar se o form tem dados válidos e não foi deletado
                if form.is_valid() and form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                    rule_type = form.cleaned_data.get('rule_type')
                    
                    if rule_type == 'subcategory':
                        subcategory = form.cleaned_data.get('subcategory')
                        if subcategory:
                            rule_dict = {
                                'type': 'subcategory',
                                'subcategory_id': subcategory.id
                            }
                            rules_data.append(rule_dict)
                    elif rule_type == 'transfer':
                        destination_account = form.cleaned_data.get('destination_account')
                        value_type = form.cleaned_data.get('value_type')
                        if destination_account and value_type:
                            rule_dict = {
                                'type': 'transfer',
                                'destination_account_id': destination_account.id,
                                'value_type': value_type
                            }
                            rules_data.append(rule_dict)
                    elif rule_type == 'asset_transaction':
                        operation_type = form.cleaned_data.get('operation_type')
                        asset_type = form.cleaned_data.get('asset_type')
                        asset_value_type = form.cleaned_data.get('asset_value_type')
                        if operation_type and asset_value_type:
                            rule_dict = {
                                'type': 'asset_transaction',
                                'operation_type': operation_type,
                                'asset_value_type': asset_value_type
                            }
                            # Adicionar campo opcional apenas se preenchido
                            if asset_type:
                                rule_dict['asset_type'] = asset_type
                            rules_data.append(rule_dict)
            
            instance.calculation_rules = rules_data
        
        if commit:
            instance.save()
        
        return instance


class TransactionFilterForm(forms.Form):
    """Formulário de filtros para a lista de transações"""
    account = forms.ModelMultipleChoiceField(
        queryset=Account.objects.all().order_by('name'),
        required=False,
        label='Conta',
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    beneficiary = forms.ModelMultipleChoiceField(
        queryset=Beneficiary.objects.all().order_by('full_name'),
        required=False,
        label='Beneficiário',
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    category = forms.ModelMultipleChoiceField(
        queryset=Category.objects.all().order_by('category'),
        required=False,
        label='Categoria',
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    subcategory = forms.ModelMultipleChoiceField(
        queryset=Subcategory.objects.all().order_by('category__category', 'subcategory'),
        required=False,
        label='Subcategoria',
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Forçar avaliação dos querysets para evitar problemas com cursor do banco
        # durante a renderização do template
        if self.fields['account'].queryset:
            list(self.fields['account'].queryset)
        if self.fields['beneficiary'].queryset:
            list(self.fields['beneficiary'].queryset)
        if self.fields['category'].queryset:
            list(self.fields['category'].queryset)
        if self.fields['subcategory'].queryset:
            list(self.fields['subcategory'].queryset)
    date_start = forms.DateField(
        required=False,
        label='Data início',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    date_end = forms.DateField(
        required=False,
        label='Data fim',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )


class AssetTransactionFilterForm(forms.Form):
    """Formulário de filtros para a lista de transações de ativos"""
    asset = forms.ModelMultipleChoiceField(
        queryset=Asset.objects.all().order_by('code'),
        required=False,
        label='Ativo',
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    account = forms.ModelMultipleChoiceField(
        queryset=Account.objects.all().order_by('name'),
        required=False,
        label='Conta',
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    operation_type = forms.MultipleChoiceField(
        choices=AssetTransaction.OPERATION_TYPE_CHOICES,
        required=False,
        label='Tipo de Operação',
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    date_start = forms.DateField(
        required=False,
        label='Data início',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    date_end = forms.DateField(
        required=False,
        label='Data fim',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Forçar avaliação dos querysets para evitar problemas com cursor do banco
        # durante a renderização do template
        if self.fields['asset'].queryset:
            list(self.fields['asset'].queryset)
        if self.fields['account'].queryset:
            list(self.fields['account'].queryset)


class AccountFilterForm(forms.Form):
    """Formulário de filtros para a lista de contas"""
    account_type = forms.MultipleChoiceField(
        choices=Account.ACCOUNT_TYPE_CHOICES,
        required=False,
        label='Tipo de Conta',
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    name_search = forms.CharField(
        required=False,
        label='Buscar por nome',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Digite o nome da conta...'})
    )


class AssetFilterForm(forms.Form):
    """Formulário de filtros para a lista de ativos"""
    asset_type = forms.MultipleChoiceField(
        choices=Asset.ASSET_TYPE_CHOICES,
        required=False,
        label='Tipo de Ativo',
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    currency = forms.MultipleChoiceField(
        choices=[],  # Será preenchido no __init__
        required=False,
        label='Moeda',
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    sector = forms.CharField(
        required=False,
        label='Setor',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Digite o setor...'})
    )
    code_search = forms.CharField(
        required=False,
        label='Buscar por código',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Digite o código...'})
    )
    name_search = forms.CharField(
        required=False,
        label='Buscar por nome',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Digite o nome...'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Preencher opções de moeda dinamicamente
        currencies = Asset.objects.values_list('currency', flat=True).distinct().order_by('currency')
        self.fields['currency'].choices = [(c, c) for c in currencies if c]


class SchedulerFilterForm(forms.Form):
    """Formulário de filtros para a lista de agendamentos (múltipla escolha com checkbox)"""
    account = forms.ModelMultipleChoiceField(
        queryset=Account.objects.all().order_by('name'),
        required=False,
        label='Conta',
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    beneficiary = forms.ModelMultipleChoiceField(
        queryset=Beneficiary.objects.all().order_by('full_name'),
        required=False,
        label='Beneficiário',
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    category = forms.ModelMultipleChoiceField(
        queryset=Category.objects.all().order_by('category'),
        required=False,
        label='Categoria',
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    subcategory = forms.ModelMultipleChoiceField(
        queryset=Subcategory.objects.all().order_by('category__category', 'subcategory'),
        required=False,
        label='Subcategoria',
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    status = forms.MultipleChoiceField(
        choices=Scheduler.STATUS_CHOICES,
        required=False,
        label='Status',
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    date_start = forms.DateField(
        required=False,
        label='Data início',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    date_end = forms.DateField(
        required=False,
        label='Data fim',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Forçar avaliação dos querysets para evitar problemas com cursor do banco
        if self.fields['account'].queryset:
            list(self.fields['account'].queryset)
        if self.fields['beneficiary'].queryset:
            list(self.fields['beneficiary'].queryset)
        if self.fields['category'].queryset:
            list(self.fields['category'].queryset)
        if self.fields['subcategory'].queryset:
            list(self.fields['subcategory'].queryset)


class BudgetForm(forms.ModelForm):
    class Meta:
        model = Budget
        fields = ['subcategory', 'budget_date', 'amount', 'notes']
        widgets = {
            'subcategory': forms.Select(attrs={'required': True}),
            'budget_date': forms.DateInput(attrs={'type': 'date', 'required': True}),
            'amount': forms.NumberInput(attrs={'step': '0.01', 'required': True}),
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Digite suas anotações aqui...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ordenar subcategoria alfabeticamente
        self.fields['subcategory'].queryset = Subcategory.objects.all().order_by('category__category', 'subcategory')


class TransactionsImportForm(forms.Form):
    """Formulário para upload do arquivo transactions.txt"""
    file = forms.FileField(
        label='Arquivo transactions.txt',
        help_text='Selecione o arquivo transactions.txt',
        widget=forms.FileInput(attrs={
            'accept': '.txt',
            'class': 'form-control',
            'required': True
        })
    )


class TransactionsStagingFilterForm(forms.Form):
    """Formulário de filtros para a página de staging"""
    date_start = forms.DateField(
        required=False,
        label='Data início',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    date_end = forms.DateField(
        required=False,
        label='Data fim',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    account = forms.CharField(
        required=False,
        label='Conta',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Filtrar por conta...'})
    )
    beneficiary = forms.CharField(
        required=False,
        label='Beneficiário',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Filtrar por beneficiário...'})
    )
    category = forms.CharField(
        required=False,
        label='Categoria',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Filtrar por categoria...'})
    )
    transaction_type = forms.ChoiceField(
        choices=[('', 'Todos'), ('CR', 'Crédito'), ('DB', 'Débito')],
        required=False,
        label='Tipo',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    min_value = forms.DecimalField(
        required=False,
        label='Valor mínimo',
        widget=forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control'})
    )
    max_value = forms.DecimalField(
        required=False,
        label='Valor máximo',
        widget=forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control'})
    )
    import_status = forms.ChoiceField(
        choices=[('', 'Todas'), ('imported', 'Já importadas'), ('not_imported', 'Não importadas')],
        required=False,
        label='Status de importação',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Este formulário usa campos CharField simples para filtros de texto
        # Não há necessidade de configurar querysets


class SubcategoryMoveForm(forms.Form):
    """Formulário para mover subcategoria - seleciona subcategoria destino"""
    destination_subcategory = forms.ModelChoiceField(
        queryset=Subcategory.objects.all().order_by('category__category', 'subcategory'),
        label='Subcategoria de destino',
        required=True,
        widget=forms.Select(attrs={'required': True, 'class': 'form-select'})
    )
    
    def __init__(self, *args, **kwargs):
        self.source_subcategory = kwargs.pop('source_subcategory', None)
        super().__init__(*args, **kwargs)
        
        if self.source_subcategory:
            # Excluir a subcategoria origem das opções
            self.fields['destination_subcategory'].queryset = Subcategory.objects.exclude(
                pk=self.source_subcategory.pk
            ).order_by('category__category', 'subcategory')
    
    def clean(self):
        cleaned_data = super().clean()
        destination_subcategory = cleaned_data.get('destination_subcategory')
        
        if destination_subcategory and self.source_subcategory:
            # Validação adicional: garantir que não seja a mesma subcategoria
            # (já tratado no __init__, mas adicionar aqui como segurança)
            if destination_subcategory.pk == self.source_subcategory.pk:
                raise forms.ValidationError({
                    'destination_subcategory': 'A subcategoria de destino deve ser diferente da origem.'
                })
        
        return cleaned_data


class AssetTransactionCategoryConfigForm(forms.ModelForm):
    class Meta:
        model = AssetTransactionCategoryConfig
        fields = [
            'operation_type',
            'asset_type',
            'subcategory_principal',
            'transaction_type_principal',
            'subcategory_fees',
            'transaction_type_fees',
        ]
        widgets = {
            'operation_type': forms.Select(attrs={'class': 'form-select', 'required': True}),
            'asset_type': forms.Select(attrs={'class': 'form-select'}),
            'subcategory_principal': forms.Select(attrs={'class': 'form-select', 'required': True}),
            'transaction_type_principal': forms.Select(attrs={'class': 'form-select', 'required': True}),
            'subcategory_fees': forms.Select(attrs={'class': 'form-select'}),
            'transaction_type_fees': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ordenar subcategorias por categoria e nome
        self.fields['subcategory_principal'].queryset = Subcategory.objects.all().select_related('category').order_by('category__category', 'subcategory')
        self.fields['subcategory_fees'].queryset = Subcategory.objects.all().select_related('category').order_by('category__category', 'subcategory')
        
        # Adicionar labels mais descritivos
        self.fields['subcategory_principal'].label = 'Subcategoria Principal'
        self.fields['subcategory_fees'].label = 'Subcategoria de Taxas (opcional)'
        
        # Tornar asset_type opcional (pode ser None para aplicar a todos)
        self.fields['asset_type'].required = False
        self.fields['subcategory_fees'].required = False
        self.fields['transaction_type_fees'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        operation_type = cleaned_data.get('operation_type')
        asset_type = cleaned_data.get('asset_type')
        
        # Verificar se já existe uma configuração com a mesma combinação
        if self.instance.pk:
            # Se estiver editando, excluir a própria instância da verificação
            existing = AssetTransactionCategoryConfig.objects.filter(
                operation_type=operation_type,
                asset_type=asset_type
            ).exclude(pk=self.instance.pk).first()
        else:
            existing = AssetTransactionCategoryConfig.objects.filter(
                operation_type=operation_type,
                asset_type=asset_type
            ).first()
        
        if existing:
            asset_type_display = existing.get_asset_type_display() if existing.asset_type else "Todos os tipos"
            raise forms.ValidationError(
                f'Já existe uma configuração para {existing.get_operation_type_display()} - {asset_type_display}.'
            )
        
        return cleaned_data


class AssetTransactionsImportForm(forms.Form):
    """Formulário para upload do arquivo asset_transactions.txt"""
    file = forms.FileField(
        label='Arquivo asset_transactions.txt',
        help_text='Selecione o arquivo asset_transactions.txt',
        widget=forms.FileInput(attrs={
            'accept': '.txt',
            'class': 'form-control',
            'required': True
        })
    )


class AssetTransactionsStagingFilterForm(forms.Form):
    """Formulário de filtros para a página de staging de transações de ativos"""
    date_start = forms.DateField(
        required=False,
        label='Data início',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    date_end = forms.DateField(
        required=False,
        label='Data fim',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    investment_account = forms.CharField(
        required=False,
        label='Conta de investimento',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Filtrar por conta...'})
    )
    cash_account = forms.CharField(
        required=False,
        label='Conta Cash',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Filtrar por conta cash...'})
    )
    asset_code = forms.CharField(
        required=False,
        label='Ativo',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Filtrar por código do ativo...'})
    )
    operation_type = forms.ChoiceField(
        choices=[
            ('', 'Todos'),
            ('BUY', 'Compra'),
            ('SELL', 'Venda'),
            ('DIVIDEND', 'Dividendo'),
            ('JCP', 'Juros sobre Capital Próprio'),
            ('INTEREST', 'Juros'),
            ('BONUS', 'Bonificação'),
            ('REDEMPTION', 'Resgate'),
        ],
        required=False,
        label='Tipo de operação',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    min_value = forms.DecimalField(
        required=False,
        label='Valor mínimo',
        widget=forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control'})
    )
    max_value = forms.DecimalField(
        required=False,
        label='Valor máximo',
        widget=forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control'})
    )
    import_status = forms.ChoiceField(
        choices=[('', 'Todas'), ('imported', 'Já importadas'), ('not_imported', 'Não importadas')],
        required=False,
        label='Status de importação',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)