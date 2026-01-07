from django import forms
from .models import Account, Beneficiary, Category, Subcategory, Transaction, Scheduler


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


class TransactionForm(forms.ModelForm):
    is_transfer = forms.BooleanField(
        required=False,
        label='É uma transferência entre contas',
        widget=forms.CheckboxInput()
    )
    source_account = forms.ModelChoiceField(
        queryset=Account.objects.all(),
        required=False,
        label='Conta de origem',
        widget=forms.Select(attrs={'required': False})
    )
    destination_account = forms.ModelChoiceField(
        queryset=Account.objects.all(),
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
        queryset=Account.objects.all(),
        required=True,
        label='Conta de origem',
        widget=forms.Select(attrs={'required': True})
    )
    destination_account = forms.ModelChoiceField(
        queryset=Account.objects.all(),
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

