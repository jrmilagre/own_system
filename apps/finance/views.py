from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Account, Beneficiary, Category, Transaction, Scheduler
from .forms import AccountForm, BeneficiaryForm, CategoryForm, TransactionForm, SchedulerForm


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


# Scheduler Views
def scheduler_list(request):
    """Lista de agendamentos"""
    schedulers = Scheduler.objects.all()
    return render(request, 'finance/scheduler_list.html', {'schedulers': schedulers})


def scheduler_create(request):
    """Criar novo agendamento"""
    if request.method == 'POST':
        form = SchedulerForm(request.POST)
        if form.is_valid():
            scheduler = form.save(commit=False)
            # Garantir que original_due_date seja definido
            if scheduler.due_date and not scheduler.original_due_date:
                scheduler.original_due_date = scheduler.due_date
            scheduler.save()
            return redirect('finance:scheduler_list')
    else:
        form = SchedulerForm()
    return render(request, 'finance/scheduler_form.html', {'form': form})


def scheduler_update(request, pk):
    """Editar agendamento existente"""
    scheduler = get_object_or_404(Scheduler, pk=pk)
    if request.method == 'POST':
        form = SchedulerForm(request.POST, instance=scheduler)
        if form.is_valid():
            scheduler = form.save(commit=False)
            # Atualizar original_due_date se due_date mudou e original_due_date não está definido
            if scheduler.due_date and not scheduler.original_due_date:
                scheduler.original_due_date = scheduler.due_date
            scheduler.save()
            return redirect('finance:scheduler_list')
    else:
        form = SchedulerForm(instance=scheduler)
    return render(request, 'finance/scheduler_form.html', {'form': form, 'scheduler': scheduler})


def scheduler_delete(request, pk):
    """Deletar agendamento"""
    scheduler = get_object_or_404(Scheduler, pk=pk)
    if request.method == 'POST':
        scheduler.delete()
        return redirect('finance:scheduler_list')
    return render(request, 'finance/scheduler_confirm_delete.html', {'scheduler': scheduler})


def scheduler_register(request, pk):
    """Registrar uma transação do agendamento"""
    scheduler = get_object_or_404(Scheduler, pk=pk)
    # Garantir que temos os valores mais atualizados do banco
    scheduler.refresh_from_db()
    # Sincronizar registered_count com transações existentes para evitar inconsistências
    scheduler.sync_registered_count()
    
    if request.method == 'POST':
        form = TransactionForm(request.POST)
        if form.is_valid():
            try:
                # Preparar dados do formulário para passar ao método register()
                transaction_data = {
                    'account': form.cleaned_data['account'],
                    'beneficiary': form.cleaned_data['beneficiary'],
                    'category': form.cleaned_data['category'],
                    'value': form.cleaned_data['value'],
                    'due_date': form.cleaned_data['due_date'],
                    'registration_date': form.cleaned_data.get('registration_date') or scheduler.due_date,
                    'purchase_date': form.cleaned_data.get('purchase_date'),
                    'notes': form.cleaned_data.get('notes', ''),
                }
                transaction = scheduler.register(transaction_data=transaction_data)
                messages.success(request, f'Transação registrada com sucesso! Próxima data: {scheduler.due_date}')
                return redirect('finance:scheduler_list')
            except ValueError as e:
                messages.error(request, str(e))
        else:
            # Se o formulário não for válido, mostrar erros
            next_due_date = scheduler.get_next_due_date_after_registration()
            return render(request, 'finance/scheduler_register.html', {
                'scheduler': scheduler,
                'form': form,
                'next_due_date': next_due_date
            })
    else:
        # Criar formulário com valores iniciais do agendamento
        initial_data = {
            'account': scheduler.account,
            'beneficiary': scheduler.beneficiary,
            'category': scheduler.category,
            'value': scheduler.value,
            'due_date': scheduler.due_date,
            'registration_date': scheduler.due_date,  # Padrão é due_date
            'purchase_date': scheduler.purchase_date,
            'notes': scheduler.notes,
        }
        form = TransactionForm(initial=initial_data)
        next_due_date = scheduler.get_next_due_date_after_registration()
        return render(request, 'finance/scheduler_register.html', {
            'scheduler': scheduler,
            'form': form,
            'next_due_date': next_due_date
        })
