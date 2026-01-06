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
    class Meta:
        model = Transaction
        fields = ['account', 'beneficiary', 'subcategory', 'transaction_type', 'value', 'due_date', 'registration_date', 'purchase_date', 'notes']
        widgets = {
            'account': forms.Select(attrs={'required': True}),
            'beneficiary': forms.Select(attrs={'required': True}),
            'subcategory': forms.Select(attrs={'required': True}),
            'transaction_type': forms.Select(attrs={'required': True}),
            'value': forms.NumberInput(attrs={'step': '0.01', 'required': True}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'registration_date': forms.DateInput(attrs={'type': 'date'}),
            'purchase_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 4}),
        }


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

