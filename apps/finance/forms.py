from django import forms
from .models import Account, Beneficiary, Category, Transaction


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
        fields = ['category', 'subcategory', 'default_transaction_type']
        widgets = {
            'category': forms.TextInput(attrs={'required': True}),
            'subcategory': forms.TextInput(attrs={'required': True}),
            'default_transaction_type': forms.Select(attrs={'required': True}),
        }


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['account', 'beneficiary', 'category', 'value', 'due_date', 'registration_date', 'purchase_date', 'notes']
        widgets = {
            'account': forms.Select(attrs={'required': True}),
            'beneficiary': forms.Select(attrs={'required': True}),
            'category': forms.Select(attrs={'required': True}),
            'value': forms.NumberInput(attrs={'step': '0.01', 'required': True}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'registration_date': forms.DateInput(attrs={'type': 'date'}),
            'purchase_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 4}),
        }

