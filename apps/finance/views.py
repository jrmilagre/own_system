from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction as db_transaction
import uuid
from .models import Account, Beneficiary, Category, Subcategory, Transaction, Scheduler
from .forms import AccountForm, BeneficiaryForm, CategoryForm, SubcategoryForm, TransactionForm, SchedulerForm


def index(request):
    """Página inicial da aplicação finance"""
    return render(request, 'finance/index.html')


def get_subcategory_default_transaction_type(request, subcategory_id):
    """Retorna o default_transaction_type de uma subcategoria (para JavaScript)"""
    subcategory = get_object_or_404(Subcategory, pk=subcategory_id)
    return JsonResponse({
        'default_transaction_type': subcategory.default_transaction_type
    })


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
    # Adicionar contagem de subcategorias para cada categoria
    for category in categories:
        category.subcategory_count = Subcategory.objects.filter(category=category).count()
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


# Subcategory Views
def subcategory_list(request, category_pk):
    """Lista de subcategorias de uma categoria"""
    category = get_object_or_404(Category, pk=category_pk)
    subcategories = Subcategory.objects.filter(category=category)
    return render(request, 'finance/subcategory_list.html', {
        'category': category,
        'subcategories': subcategories
    })


def subcategory_create(request, category_pk):
    """Criar nova subcategoria"""
    category = get_object_or_404(Category, pk=category_pk)
    if request.method == 'POST':
        form = SubcategoryForm(request.POST)
        if form.is_valid():
            subcategory = form.save(commit=False)
            subcategory.category = category
            subcategory.save()
            return redirect('finance:subcategory_list', category_pk=category_pk)
    else:
        form = SubcategoryForm(initial={'category': category})
    return render(request, 'finance/subcategory_form.html', {
        'form': form,
        'category': category
    })


def subcategory_update(request, category_pk, pk):
    """Editar subcategoria existente"""
    category = get_object_or_404(Category, pk=category_pk)
    subcategory = get_object_or_404(Subcategory, pk=pk, category=category)
    if request.method == 'POST':
        form = SubcategoryForm(request.POST, instance=subcategory)
        if form.is_valid():
            form.save()
            return redirect('finance:subcategory_list', category_pk=category_pk)
    else:
        form = SubcategoryForm(instance=subcategory)
    return render(request, 'finance/subcategory_form.html', {
        'form': form,
        'category': category,
        'subcategory': subcategory
    })


def subcategory_delete(request, category_pk, pk):
    """Deletar subcategoria"""
    category = get_object_or_404(Category, pk=category_pk)
    subcategory = get_object_or_404(Subcategory, pk=pk, category=category)
    if request.method == 'POST':
        subcategory.delete()
        return redirect('finance:subcategory_list', category_pk=category_pk)
    return render(request, 'finance/subcategory_confirm_delete.html', {
        'category': category,
        'subcategory': subcategory
    })


# Transaction Views
def transaction_list(request):
    """Lista de transações"""
    transactions = Transaction.objects.all().select_related('account', 'beneficiary', 'subcategory')
    # Adicionar informação sobre transferências para cada transação
    for transaction in transactions:
        if transaction.is_transfer:
            transfer_pair = transaction.get_transfer_pair()
            if transfer_pair:
                if transaction.transaction_type == 'DB':
                    transaction.transfer_info = f"De: {transaction.account} → Para: {transfer_pair.account}"
                else:
                    transaction.transfer_info = f"De: {transfer_pair.account} → Para: {transaction.account}"
            else:
                transaction.transfer_info = "Transferência (parceiro não encontrado)"
    return render(request, 'finance/transaction_list.html', {'transactions': transactions})


def transaction_create(request):
    """Criar nova transação"""
    if request.method == 'POST':
        form = TransactionForm(request.POST)
        if form.is_valid():
            is_transfer = form.cleaned_data.get('is_transfer', False)
            
            if is_transfer:
                # Criar transferência (2 transações)
                source_account = form.cleaned_data['source_account']
                destination_account = form.cleaned_data['destination_account']
                value = form.cleaned_data['value']
                due_date = form.cleaned_data.get('due_date')
                transaction_date = form.cleaned_data.get('transaction_date')
                purchase_date = form.cleaned_data.get('purchase_date')
                notes = form.cleaned_data.get('notes', '')
                
                # Gerar UUID para vincular as duas transações
                transfer_group_id = uuid.uuid4()
                
                # Criar ambas as transações em uma transação de banco de dados
                with db_transaction.atomic():
                    # Transação de débito (conta origem)
                    debit_transaction = Transaction.objects.create(
                        account=source_account,
                        beneficiary=None,
                        subcategory=None,
                        transaction_type='DB',
                        value=value,
                        due_date=due_date,
                        transaction_date=transaction_date,
                        purchase_date=purchase_date,
                        notes=notes,
                        transfer_group_id=transfer_group_id,
                        is_transfer=True
                    )
                    
                    # Transação de crédito (conta destino)
                    credit_transaction = Transaction.objects.create(
                        account=destination_account,
                        beneficiary=None,
                        subcategory=None,
                        transaction_type='CR',
                        value=value,
                        due_date=due_date,
                        transaction_date=transaction_date,
                        purchase_date=purchase_date,
                        notes=notes,
                        transfer_group_id=transfer_group_id,
                        is_transfer=True
                    )
                
                messages.success(request, 'Transferência criada com sucesso!')
            else:
                # Criar transação normal
                form.save()
                messages.success(request, 'Transação criada com sucesso!')
            
            return redirect('finance:transaction_list')
        else:
            # Formulário inválido - mostrar erros
            messages.error(request, 'Por favor, corrija os erros abaixo.')
    else:
        form = TransactionForm()
    return render(request, 'finance/transaction_form.html', {'form': form})


def transaction_update(request, pk):
    """Editar transação existente"""
    transaction = get_object_or_404(Transaction, pk=pk)
    
    if request.method == 'POST':
        # Para transferências, não usar instance para evitar validação do campo account
        if transaction.is_transfer:
            form = TransactionForm(request.POST)
        else:
            form = TransactionForm(request.POST, instance=transaction)
            
        if form.is_valid():
            if transaction.is_transfer:
                # Atualizar ambas as transações da transferência
                transfer_pair = transaction.get_transfer_pair()
                if transfer_pair:
                    # Campos que devem ser sincronizados
                    source_account = form.cleaned_data['source_account']
                    destination_account = form.cleaned_data['destination_account']
                    value = form.cleaned_data['value']
                    due_date = form.cleaned_data.get('due_date')
                    transaction_date = form.cleaned_data.get('transaction_date')
                    purchase_date = form.cleaned_data.get('purchase_date')
                    notes = form.cleaned_data.get('notes', '')
                    
                    with db_transaction.atomic():
                        # Determinar qual transação é débito e qual é crédito
                        if transaction.transaction_type == 'DB':
                            # Esta é a transação de débito (origem)
                            debit_transaction = transaction
                            credit_transaction = transfer_pair
                        else:
                            # Esta é a transação de crédito (destino)
                            debit_transaction = transfer_pair
                            credit_transaction = transaction
                        
                        # Atualizar transação de débito (conta origem)
                        debit_transaction.account = source_account
                        debit_transaction.value = value
                        debit_transaction.due_date = due_date
                        debit_transaction.transaction_date = transaction_date
                        debit_transaction.purchase_date = purchase_date
                        debit_transaction.notes = notes
                        debit_transaction.save()
                        
                        # Atualizar transação de crédito (conta destino)
                        credit_transaction.account = destination_account
                        credit_transaction.value = value
                        credit_transaction.due_date = due_date
                        credit_transaction.transaction_date = transaction_date
                        credit_transaction.purchase_date = purchase_date
                        credit_transaction.notes = notes
                        credit_transaction.save()
                    
                    messages.success(request, 'Transferência atualizada com sucesso!')
                else:
                    messages.error(request, 'Transação vinculada não encontrada.')
            else:
                # Atualizar transação normal
                form.save()
                messages.success(request, 'Transação atualizada com sucesso!')
            
            return redirect('finance:transaction_list')
        else:
            # Formulário inválido - mostrar erros
            messages.error(request, 'Por favor, corrija os erros abaixo.')
    else:
        # Se for transferência, criar formulário sem instance para evitar conflito com campo account
        if transaction.is_transfer:
            transfer_pair = transaction.get_transfer_pair()
            if transfer_pair:
                if transaction.transaction_type == 'DB':
                    # Esta é a transação de débito (origem)
                    source_account = transaction.account
                    destination_account = transfer_pair.account
                else:
                    # Esta é a transação de crédito (destino)
                    source_account = transfer_pair.account
                    destination_account = transaction.account
                
                initial_data = {
                    'is_transfer': True,
                    'source_account': source_account,
                    'destination_account': destination_account,
                    'value': transaction.value,
                    'due_date': transaction.due_date,
                    'transaction_date': transaction.transaction_date,
                    'purchase_date': transaction.purchase_date,
                    'notes': transaction.notes,
                }
                form = TransactionForm(initial=initial_data)
            else:
                form = TransactionForm(instance=transaction)
        else:
            form = TransactionForm(instance=transaction)
    
    return render(request, 'finance/transaction_form.html', {'form': form, 'transaction': transaction})


def transaction_delete(request, pk):
    """Deletar transação"""
    transaction = get_object_or_404(Transaction, pk=pk)
    if request.method == 'POST':
        if transaction.is_transfer:
            # Deletar ambas as transações da transferência
            transfer_pair = transaction.get_transfer_pair()
            if transfer_pair:
                with db_transaction.atomic():
                    transfer_pair.delete()
                    transaction.delete()
                messages.success(request, 'Transferência deletada com sucesso!')
            else:
                transaction.delete()
                messages.warning(request, 'Transação deletada, mas a transação vinculada não foi encontrada.')
        else:
            transaction.delete()
            messages.success(request, 'Transação deletada com sucesso!')
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
                    'subcategory': form.cleaned_data['subcategory'],
                    'transaction_type': form.cleaned_data.get('transaction_type', scheduler.transaction_type),
                    'value': form.cleaned_data['value'],
                    'due_date': form.cleaned_data['due_date'],
                    'transaction_date': form.cleaned_data.get('transaction_date') or scheduler.due_date,
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
            'subcategory': scheduler.subcategory,
            'transaction_type': scheduler.transaction_type,
            'value': scheduler.value,
            'due_date': scheduler.due_date,
            'transaction_date': scheduler.due_date,  # Padrão é due_date
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
