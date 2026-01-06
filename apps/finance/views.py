from django.shortcuts import render, redirect, get_object_or_404
from .models import Account, Beneficiary, Category, Transaction
from .forms import AccountForm, BeneficiaryForm, CategoryForm, TransactionForm


def index(request):
    """Página inicial da aplicação finance"""
    return render(request, 'finance/index.html')


# Account Views
def account_list(request):
    """Lista de contas"""
    accounts = Account.objects.all()
    return render(request, 'finance/account_list.html', {'accounts': accounts})


def account_create(request):
    """Criar nova conta"""
    if request.method == 'POST':
        form = AccountForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('finance:account_list')
    else:
        form = AccountForm()
    return render(request, 'finance/account_form.html', {'form': form})


def account_update(request, pk):
    """Editar conta existente"""
    account = get_object_or_404(Account, pk=pk)
    if request.method == 'POST':
        form = AccountForm(request.POST, instance=account)
        if form.is_valid():
            form.save()
            return redirect('finance:account_list')
    else:
        form = AccountForm(instance=account)
    return render(request, 'finance/account_form.html', {'form': form, 'account': account})


def account_delete(request, pk):
    """Deletar conta"""
    account = get_object_or_404(Account, pk=pk)
    if request.method == 'POST':
        account.delete()
        return redirect('finance:account_list')
    return render(request, 'finance/account_confirm_delete.html', {'account': account})


# Beneficiary Views
def beneficiary_list(request):
    """Lista de beneficiários"""
    beneficiaries = Beneficiary.objects.all()
    return render(request, 'finance/beneficiary_list.html', {'beneficiaries': beneficiaries})


def beneficiary_create(request):
    """Criar novo beneficiário"""
    if request.method == 'POST':
        form = BeneficiaryForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('finance:beneficiary_list')
    else:
        form = BeneficiaryForm()
    return render(request, 'finance/beneficiary_form.html', {'form': form})


def beneficiary_update(request, pk):
    """Editar beneficiário existente"""
    beneficiary = get_object_or_404(Beneficiary, pk=pk)
    if request.method == 'POST':
        form = BeneficiaryForm(request.POST, instance=beneficiary)
        if form.is_valid():
            form.save()
            return redirect('finance:beneficiary_list')
    else:
        form = BeneficiaryForm(instance=beneficiary)
    return render(request, 'finance/beneficiary_form.html', {'form': form, 'beneficiary': beneficiary})


def beneficiary_delete(request, pk):
    """Deletar beneficiário"""
    beneficiary = get_object_or_404(Beneficiary, pk=pk)
    if request.method == 'POST':
        beneficiary.delete()
        return redirect('finance:beneficiary_list')
    return render(request, 'finance/beneficiary_confirm_delete.html', {'beneficiary': beneficiary})


# Category Views
def category_list(request):
    """Lista de categorias"""
    categories = Category.objects.all()
    return render(request, 'finance/category_list.html', {'categories': categories})


def category_create(request):
    """Criar nova categoria"""
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('finance:category_list')
    else:
        form = CategoryForm()
    return render(request, 'finance/category_form.html', {'form': form})


def category_update(request, pk):
    """Editar categoria existente"""
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            return redirect('finance:category_list')
    else:
        form = CategoryForm(instance=category)
    return render(request, 'finance/category_form.html', {'form': form, 'category': category})


def category_delete(request, pk):
    """Deletar categoria"""
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        category.delete()
        return redirect('finance:category_list')
    return render(request, 'finance/category_confirm_delete.html', {'category': category})


# Transaction Views
def transaction_list(request):
    """Lista de transações"""
    transactions = Transaction.objects.all()
    return render(request, 'finance/transaction_list.html', {'transactions': transactions})


def transaction_create(request):
    """Criar nova transação"""
    if request.method == 'POST':
        form = TransactionForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('finance:transaction_list')
    else:
        form = TransactionForm()
    return render(request, 'finance/transaction_form.html', {'form': form})


def transaction_update(request, pk):
    """Editar transação existente"""
    transaction = get_object_or_404(Transaction, pk=pk)
    if request.method == 'POST':
        form = TransactionForm(request.POST, instance=transaction)
        if form.is_valid():
            form.save()
            return redirect('finance:transaction_list')
    else:
        form = TransactionForm(instance=transaction)
    return render(request, 'finance/transaction_form.html', {'form': form, 'transaction': transaction})


def transaction_delete(request, pk):
    """Deletar transação"""
    transaction = get_object_or_404(Transaction, pk=pk)
    if request.method == 'POST':
        transaction.delete()
        return redirect('finance:transaction_list')
    return render(request, 'finance/transaction_confirm_delete.html', {'transaction': transaction})
