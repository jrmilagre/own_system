from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction as db_transaction
from django.core.paginator import Paginator
from django.db.models import Q
from datetime import datetime, date
import uuid
from .models import Account, Beneficiary, Category, Subcategory, Transaction, Scheduler, Asset, AssetTransaction, AssetPosition, Budget, Inventory, CashFlowItem
from .forms import (
    AccountForm, BeneficiaryForm, CategoryForm, SubcategoryForm, TransactionForm, SchedulerForm,
    MultipleTransactionForm, MultipleTransactionItemForm, MultipleTransactionItemFormSet,
    MultipleSchedulerForm, MultipleSchedulerItemForm, MultipleSchedulerItemFormSet,
    MultipleSchedulerRegisterItemFormSet, AssetForm, AssetTransactionForm, AssetPositionForm, InventoryForm,
    CashFlowItemForm, CashFlowCalculationRuleFormSet, TransactionFilterForm
)


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
    # Calcular datas padrão para o botão de extrato
    today = date.today()
    first_day_of_month = date(today.year, today.month, 1)
    return render(request, 'finance/account_list.html', {
        'accounts': accounts,
        'default_start_date': first_day_of_month,
        'default_end_date': today,
    })


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
    """Lista de transações com filtros e paginação"""
    # Inicializar formulário de filtros
    filter_form = TransactionFilterForm(request.GET)
    
    # Query base
    transactions = Transaction.objects.all().select_related('account', 'beneficiary', 'subcategory')
    
    # Aplicar filtros
    if filter_form.is_valid():
        account = filter_form.cleaned_data.get('account')
        beneficiary = filter_form.cleaned_data.get('beneficiary')
        category = filter_form.cleaned_data.get('category')
        subcategory = filter_form.cleaned_data.get('subcategory')
        date_start = filter_form.cleaned_data.get('date_start')
        date_end = filter_form.cleaned_data.get('date_end')
        
        if account:
            transactions = transactions.filter(account=account)
        
        if beneficiary:
            transactions = transactions.filter(beneficiary=beneficiary)
        
        if category:
            transactions = transactions.filter(subcategory__category=category)
        
        if subcategory:
            transactions = transactions.filter(subcategory=subcategory)
        
        if date_start or date_end:
            date_filter = Q()
            if date_start and date_end:
                # Ambos definidos: transaction_date ou due_date devem estar no intervalo
                date_filter = (
                    (Q(transaction_date__gte=date_start) & Q(transaction_date__lte=date_end)) |
                    (Q(transaction_date__isnull=True) & Q(due_date__gte=date_start) & Q(due_date__lte=date_end))
                )
            elif date_start:
                # Apenas date_start: transaction_date >= date_start OU (transaction_date é null E due_date >= date_start)
                date_filter = Q(transaction_date__gte=date_start) | Q(transaction_date__isnull=True, due_date__gte=date_start)
            elif date_end:
                # Apenas date_end: transaction_date <= date_end OU (transaction_date é null E due_date <= date_end)
                date_filter = Q(transaction_date__lte=date_end) | Q(transaction_date__isnull=True, due_date__lte=date_end)
            transactions = transactions.filter(date_filter)
    
    # Ordenar
    transactions = transactions.order_by('-transaction_date', '-due_date', '-created_at')
    
    # Paginação
    paginator = Paginator(transactions, 50)  # 50 transações por página
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Agrupar transações múltiplas
    multiple_groups = {}
    single_transactions = []
    
    for transaction in page_obj:
        if transaction.is_multiple and transaction.multiple_transaction_group_id:
            group_id = str(transaction.multiple_transaction_group_id)
            if group_id not in multiple_groups:
                multiple_groups[group_id] = {
                    'group_id': transaction.multiple_transaction_group_id,
                    'transactions': [],
                    'representative': transaction  # Primeira transação do grupo
                }
            multiple_groups[group_id]['transactions'].append(transaction)
        else:
            single_transactions.append(transaction)
    
    # Adicionar informação sobre transferências para cada transação
    for transaction in single_transactions:
        if transaction.is_transfer:
            transfer_pair = transaction.get_transfer_pair()
            if transfer_pair:
                if transaction.transaction_type == 'DB':
                    transaction.transfer_info = f"De: {transaction.account} → Para: {transfer_pair.account}"
                else:
                    transaction.transfer_info = f"De: {transfer_pair.account} → Para: {transaction.account}"
            else:
                transaction.transfer_info = "Transferência (parceiro não encontrado)"
    
    # Adicionar informações para grupos múltiplos
    for group_data in multiple_groups.values():
        # Calcular total: somar créditos e subtrair débitos
        total_value = 0
        for transaction in group_data['transactions']:
            if transaction.transaction_type == 'CR':
                total_value += transaction.value
            elif transaction.transaction_type == 'DB':
                total_value -= transaction.value
        group_data['total_value'] = total_value
        group_data['count'] = len(group_data['transactions'])
    
    # Ordenar grupos múltiplos por data de transação decrescente
    multiple_groups_list = list(multiple_groups.values())
    multiple_groups_list.sort(
        key=lambda x: (
            x['representative'].transaction_date or 
            x['representative'].due_date or 
            x['representative'].created_at or 
            date.min
        ),
        reverse=True
    )
    
    # Calcular subtotal da página
    from decimal import Decimal
    subtotal = Decimal('0')
    
    # Somar transações simples
    for transaction in single_transactions:
        if transaction.transaction_type == 'CR':
            subtotal += transaction.value
        elif transaction.transaction_type == 'DB':
            subtotal -= transaction.value
    
    # Somar grupos múltiplos
    for group_data in multiple_groups_list:
        subtotal += Decimal(str(group_data['total_value']))
    
    return render(request, 'finance/transaction_list.html', {
        'transactions': single_transactions,
        'multiple_groups': multiple_groups_list,
        'filter_form': filter_form,
        'page_obj': page_obj,
        'subtotal': subtotal
    })


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
    
    # Se a transação faz parte de uma transação múltipla, redirecionar para o formulário de transação múltipla
    if transaction.is_multiple and transaction.multiple_transaction_group_id:
        return redirect('finance:multiple_transaction_update', group_id=transaction.multiple_transaction_group_id)
    
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
    """Lista de agendamentos (normais e múltiplos)"""
    schedulers = Scheduler.objects.all().select_related('account', 'beneficiary', 'subcategory', 'destination_account')
    
    # Agrupar agendamentos múltiplos
    multiple_groups = {}
    single_schedulers = []
    
    for scheduler in schedulers:
        if scheduler.is_multiple and scheduler.multiple_scheduler_group_id:
            group_id = str(scheduler.multiple_scheduler_group_id)
            if group_id not in multiple_groups:
                multiple_groups[group_id] = {
                    'group_id': scheduler.multiple_scheduler_group_id,
                    'schedulers': [],
                    'representative': scheduler  # Primeiro agendamento do grupo
                }
            multiple_groups[group_id]['schedulers'].append(scheduler)
        else:
            single_schedulers.append(scheduler)
    
    # Adicionar informações para grupos múltiplos
    for group_data in multiple_groups.values():
        # Calcular total: somar créditos e subtrair débitos
        total_value = 0
        for scheduler in group_data['schedulers']:
            if scheduler.transaction_type == 'CR':
                total_value += scheduler.value
            elif scheduler.transaction_type == 'DB':
                total_value -= scheduler.value
        group_data['total_value'] = total_value
        group_data['count'] = len(group_data['schedulers'])
        # Ordenar por ID para manter ordem
        group_data['schedulers'].sort(key=lambda x: x.id)
    
    return render(request, 'finance/scheduler_list.html', {
        'schedulers': single_schedulers,
        'multiple_groups': list(multiple_groups.values())
    })


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


# Multiple Transaction Views
def multiple_transaction_create(request):
    """Criar nova transação múltipla"""
    if request.method == 'POST':
        form = MultipleTransactionForm(request.POST)
        formset = MultipleTransactionItemFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            # Gerar UUID para vincular todas as transações
            multiple_group_id = uuid.uuid4()
            
            # Campos compartilhados do cabeçalho
            account = form.cleaned_data['account']
            beneficiary = form.cleaned_data['beneficiary']
            due_date = form.cleaned_data.get('due_date')
            transaction_date = form.cleaned_data.get('transaction_date')
            purchase_date = form.cleaned_data.get('purchase_date')
            notes = form.cleaned_data.get('notes', '')
            
            created_transactions = []
            
            with db_transaction.atomic():
                for item_form in formset:
                    # Verificar se o form tem dados
                    if not item_form.cleaned_data:
                        continue  # Pular forms sem dados
                    
                    # Verificar se está marcado para deletar
                    # O campo DELETE pode estar como True, 'on', ou presente no POST
                    if item_form.cleaned_data.get('DELETE', False):
                        continue  # Pular este item marcado para deletar
                    
                    item_data = item_form.cleaned_data
                    is_transfer = item_data.get('is_transfer', False)
                    value = item_data.get('value')
                    
                    # Verificar se tem valor (form não está vazio)
                    if not value:
                        continue  # Pular forms vazios
                    
                    if is_transfer:
                        # Criar transferência (2 transações)
                        # Conta de origem vem do cabeçalho
                        source_account = account
                        destination_account = item_data['destination_account']
                        
                        # Validar que destino é diferente da origem
                        if source_account == destination_account:
                            messages.error(request, 'A conta de destino deve ser diferente da conta de origem.')
                            return render(request, 'finance/multiple_transaction_form.html', {
                                'form': form,
                                'formset': formset
                            })
                        
                        transfer_group_id = uuid.uuid4()
                        
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
                            is_transfer=True,
                            multiple_transaction_group_id=multiple_group_id,
                            is_multiple=True
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
                            is_transfer=True,
                            multiple_transaction_group_id=multiple_group_id,
                            is_multiple=True
                        )
                        
                        created_transactions.extend([debit_transaction, credit_transaction])
                    else:
                        # Criar transação normal
                        transaction = Transaction.objects.create(
                            account=account,
                            beneficiary=beneficiary,
                            subcategory=item_data['subcategory'],
                            transaction_type=item_data['transaction_type'],
                            value=value,
                            due_date=due_date,
                            transaction_date=transaction_date,
                            purchase_date=purchase_date,
                            notes=notes,
                            multiple_transaction_group_id=multiple_group_id,
                            is_multiple=True
                        )
                        created_transactions.append(transaction)
            
            messages.success(request, f'Transação múltipla criada com sucesso! {len(created_transactions)} transação(ões) criada(s).')
            return redirect('finance:transaction_list')
        else:
            messages.error(request, 'Por favor, corrija os erros abaixo.')
    else:
        form = MultipleTransactionForm()
        formset = MultipleTransactionItemFormSet()
    
    return render(request, 'finance/multiple_transaction_form.html', {
        'form': form,
        'formset': formset
    })


def multiple_transaction_update(request, group_id):
    """Editar transação múltipla existente"""
    # Buscar todas as transações do grupo
    transactions = Transaction.objects.filter(
        multiple_transaction_group_id=group_id,
        is_multiple=True
    ).order_by('id')
    
    if not transactions.exists():
        messages.error(request, 'Transação múltipla não encontrada.')
        return redirect('finance:transaction_list')
    
    # Separar transações normais e transferências
    normal_transactions = []
    transfer_pairs = {}
    
    for transaction in transactions:
        if transaction.is_transfer:
            transfer_group_id = transaction.transfer_group_id
            if transfer_group_id not in transfer_pairs:
                transfer_pairs[transfer_group_id] = []
            transfer_pairs[transfer_group_id].append(transaction)
        else:
            normal_transactions.append(transaction)
    
    # Pegar primeira transação para campos compartilhados
    first_transaction = transactions.first()
    
    if request.method == 'POST':
        form = MultipleTransactionForm(request.POST)
        # Usar formset com extra=0 quando editando para evitar item vazio
        from django.forms import formset_factory
        MultipleTransactionItemFormSetEdit = formset_factory(
            MultipleTransactionItemForm,
            extra=0,
            can_delete=True,
            min_num=1,
            validate_min=True
        )
        formset = MultipleTransactionItemFormSetEdit(request.POST)
        
        if form.is_valid() and formset.is_valid():
            # Campos compartilhados do cabeçalho
            account = form.cleaned_data['account']
            beneficiary = form.cleaned_data['beneficiary']
            due_date = form.cleaned_data.get('due_date')
            transaction_date = form.cleaned_data.get('transaction_date')
            purchase_date = form.cleaned_data.get('purchase_date')
            notes = form.cleaned_data.get('notes', '')
            
            # Deletar transações antigas
            with db_transaction.atomic():
                transactions.delete()
                
                # Criar novas transações
                for item_form in formset:
                    # Verificar se o form tem dados
                    if not item_form.cleaned_data:
                        continue  # Pular forms sem dados
                    
                    # Verificar se está marcado para deletar
                    # O campo DELETE pode estar como True, 'on', ou presente no POST
                    if item_form.cleaned_data.get('DELETE', False):
                        continue  # Pular este item marcado para deletar
                    
                    item_data = item_form.cleaned_data
                    is_transfer = item_data.get('is_transfer', False)
                    value = item_data.get('value')
                    
                    # Verificar se tem valor (form não está vazio)
                    if not value:
                        continue  # Pular forms vazios
                    
                    if is_transfer:
                        # Criar transferência (2 transações)
                        # Conta de origem vem do cabeçalho
                        source_account = account
                        destination_account = item_data['destination_account']
                        
                        # Validar que destino é diferente da origem
                        if source_account == destination_account:
                            messages.error(request, 'A conta de destino deve ser diferente da conta de origem.')
                            return render(request, 'finance/multiple_transaction_form.html', {
                                'form': form,
                                'formset': formset,
                                'group_id': group_id
                            })
                        
                        transfer_group_id = uuid.uuid4()
                        
                        # Transação de débito (conta origem)
                        Transaction.objects.create(
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
                            is_transfer=True,
                            multiple_transaction_group_id=group_id,
                            is_multiple=True
                        )
                        
                        # Transação de crédito (conta destino)
                        Transaction.objects.create(
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
                            is_transfer=True,
                            multiple_transaction_group_id=group_id,
                            is_multiple=True
                        )
                    else:
                        # Criar transação normal
                        Transaction.objects.create(
                            account=account,
                            beneficiary=beneficiary,
                            subcategory=item_data['subcategory'],
                            transaction_type=item_data['transaction_type'],
                            value=value,
                            due_date=due_date,
                            transaction_date=transaction_date,
                            purchase_date=purchase_date,
                            notes=notes,
                            multiple_transaction_group_id=group_id,
                            is_multiple=True
                        )
            
            messages.success(request, 'Transação múltipla atualizada com sucesso!')
            return redirect('finance:transaction_list')
        else:
            messages.error(request, 'Por favor, corrija os erros abaixo.')
    else:
        # Preencher formulário com dados existentes
        # Pegar account e beneficiary da primeira transação normal, ou da primeira transferência
        header_account = None
        header_beneficiary = None
        if normal_transactions:
            header_account = normal_transactions[0].account
            header_beneficiary = normal_transactions[0].beneficiary
        elif transfer_pairs:
            # Se só tem transferências, usar a conta de origem da primeira
            first_pair = list(transfer_pairs.values())[0]
            if first_pair:
                debit_t = next((t for t in first_pair if t.transaction_type == 'DB'), None)
                if debit_t:
                    header_account = debit_t.account
        
        initial_data = {
            'account': header_account,
            'beneficiary': header_beneficiary,
            'due_date': first_transaction.due_date,
            'transaction_date': first_transaction.transaction_date,
            'purchase_date': first_transaction.purchase_date,
            'notes': first_transaction.notes,
        }
        form = MultipleTransactionForm(initial=initial_data)
        
        # Preparar dados do formset
        formset_data = []
        for transaction in normal_transactions:
            formset_data.append({
                'transaction_type': transaction.transaction_type,
                'subcategory': transaction.subcategory,
                'value': transaction.value,
                'is_transfer': False,
            })
        
        # Adicionar transferências
        for transfer_group_id, pair in transfer_pairs.items():
            if len(pair) == 2:
                debit_t = next((t for t in pair if t.transaction_type == 'DB'), None)
                credit_t = next((t for t in pair if t.transaction_type == 'CR'), None)
                if debit_t and credit_t:
                    formset_data.append({
                        'transaction_type': 'DB',
                        'destination_account': credit_t.account,
                        'value': debit_t.value,
                        'is_transfer': True,
                    })
        
        # Criar formset sem extra quando editando (já temos os dados)
        from django.forms import formset_factory
        MultipleTransactionItemFormSetEdit = formset_factory(
            MultipleTransactionItemForm,
            extra=0,  # Sem formulários extras quando editando
            can_delete=True,
            min_num=1,
            validate_min=True
        )
        formset = MultipleTransactionItemFormSetEdit(initial=formset_data)
    
    return render(request, 'finance/multiple_transaction_form.html', {
        'form': form,
        'formset': formset,
        'group_id': group_id
    })


def multiple_transaction_delete(request, group_id):
    """Deletar transação múltipla"""
    transactions = Transaction.objects.filter(
        multiple_transaction_group_id=group_id,
        is_multiple=True
    )
    
    if not transactions.exists():
        messages.error(request, 'Transação múltipla não encontrada.')
        return redirect('finance:transaction_list')
    
    if request.method == 'POST':
        count = transactions.count()
        transactions.delete()
        messages.success(request, f'Transação múltipla deletada com sucesso! {count} transação(ões) removida(s).')
        return redirect('finance:transaction_list')
    
    return render(request, 'finance/multiple_transaction_confirm_delete.html', {
        'transactions': transactions,
        'group_id': group_id
    })


# Multiple Scheduler Views
def multiple_scheduler_list(request):
    """Lista de agendamentos múltiplos - redireciona para scheduler_list unificado"""
    return redirect('finance:scheduler_list')


def multiple_scheduler_create(request):
    """Criar novo agendamento múltiplo"""
    if request.method == 'POST':
        form = MultipleSchedulerForm(request.POST)
        formset = MultipleSchedulerItemFormSet(request.POST)
        
        # Verificar erros de validação
        if not form.is_valid():
            messages.error(request, 'Por favor, corrija os erros no formulário principal.')
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
        
        if not formset.is_valid():
            messages.error(request, 'Por favor, corrija os erros nos itens do agendamento.')
            for form_index, item_form in enumerate(formset):
                if item_form.errors:
                    for field, errors in item_form.errors.items():
                        for error in errors:
                            messages.error(request, f'Item {form_index + 1} - {field}: {error}')
                if item_form.non_field_errors():
                    for error in item_form.non_field_errors():
                        messages.error(request, f'Item {form_index + 1}: {error}')
        
        if form.is_valid() and formset.is_valid():
            # Gerar UUID para o grupo
            group_id = uuid.uuid4()
            
            # Obter dados compartilhados do formulário
            account = form.cleaned_data['account']
            beneficiary = form.cleaned_data['beneficiary']
            due_date = form.cleaned_data.get('due_date')
            purchase_date = form.cleaned_data.get('purchase_date')
            notes = form.cleaned_data.get('notes', '')
            recurrence_type = form.cleaned_data['recurrence_type']
            recurrence_interval = form.cleaned_data['recurrence_interval']
            termination_type = form.cleaned_data['termination_type']
            remaining_installments = form.cleaned_data.get('remaining_installments')
            final_date = form.cleaned_data.get('final_date')
            status = form.cleaned_data['status']
            
            # Validar transferências: destino deve ser diferente da origem
            for item_form in formset:
                if item_form.cleaned_data:
                    # Verificar se está marcado para deletar
                    if item_form.cleaned_data.get('DELETE'):
                        continue  # Pular este item
                    
                    item_data = item_form.cleaned_data
                    value = item_data.get('value')
                    
                    if not value:  # Skip empty forms
                        continue
                    
                    if item_data.get('is_transfer'):
                        destination_account = item_data.get('destination_account')
                        if destination_account and destination_account == account:
                            messages.error(request, 'A conta de destino deve ser diferente da conta de origem para transferências.')
                            return render(request, 'finance/multiple_scheduler_form.html', {
                                'form': form,
                                'formset': formset
                            })
            
            # Criar Scheduler para cada item válido
            with db_transaction.atomic():
                created_schedulers = []
                for item_form in formset:
                    if item_form.cleaned_data:
                        # Verificar se está marcado para deletar
                        if item_form.cleaned_data.get('DELETE'):
                            continue  # Pular este item
                        
                        item_data = item_form.cleaned_data
                        value = item_data.get('value')
                        
                        if not value:  # Skip empty forms
                            continue
                        
                        is_transfer = item_data.get('is_transfer', False)
                        
                        if is_transfer:
                            # Criar transferência (2 schedulers: débito e crédito)
                            destination_account = item_data.get('destination_account')
                            
                            # Scheduler de débito (conta origem)
                            debit_scheduler = Scheduler(
                                account=account,
                                beneficiary=beneficiary,
                                subcategory=None,
                                transaction_type='DB',
                                value=value,
                                due_date=due_date,
                                purchase_date=purchase_date,
                                notes=notes,
                                recurrence_type=recurrence_type,
                                recurrence_interval=recurrence_interval,
                                termination_type=termination_type,
                                remaining_installments=remaining_installments,
                                final_date=final_date,
                                status=status,
                                multiple_scheduler_group_id=group_id,
                                is_multiple=True,
                                is_transfer=True,
                                destination_account=destination_account,
                            )
                            
                            # Scheduler de crédito (conta destino)
                            credit_scheduler = Scheduler(
                                account=destination_account,
                                beneficiary=beneficiary,
                                subcategory=None,
                                transaction_type='CR',
                                value=value,
                                due_date=due_date,
                                purchase_date=purchase_date,
                                notes=notes,
                                recurrence_type=recurrence_type,
                                recurrence_interval=recurrence_interval,
                                termination_type=termination_type,
                                remaining_installments=remaining_installments,
                                final_date=final_date,
                                status=status,
                                multiple_scheduler_group_id=group_id,
                                is_multiple=True,
                                is_transfer=True,
                                destination_account=None,  # O scheduler de crédito não precisa de destination_account
                            )
                            
                            # Definir original_due_date se não estiver definido
                            if debit_scheduler.due_date and not debit_scheduler.original_due_date:
                                debit_scheduler.original_due_date = debit_scheduler.due_date
                            if credit_scheduler.due_date and not credit_scheduler.original_due_date:
                                credit_scheduler.original_due_date = credit_scheduler.due_date
                            
                            debit_scheduler.save()
                            credit_scheduler.save()
                            created_schedulers.extend([debit_scheduler, credit_scheduler])
                        else:
                            # Criar Scheduler normal para este item
                            scheduler = Scheduler(
                                account=account,
                                beneficiary=beneficiary,
                                subcategory=item_data.get('subcategory'),
                                transaction_type=item_data['transaction_type'],
                                value=value,
                                due_date=due_date,
                                purchase_date=purchase_date,
                                notes=notes,
                                recurrence_type=recurrence_type,
                                recurrence_interval=recurrence_interval,
                                termination_type=termination_type,
                                remaining_installments=remaining_installments,
                                final_date=final_date,
                                status=status,
                                multiple_scheduler_group_id=group_id,
                                is_multiple=True,
                                is_transfer=False,
                                destination_account=None,
                            )
                            
                            # Definir original_due_date se não estiver definido
                            if scheduler.due_date and not scheduler.original_due_date:
                                scheduler.original_due_date = scheduler.due_date
                            
                            scheduler.save()
                            created_schedulers.append(scheduler)
                
                if not created_schedulers:
                    messages.error(request, 'É necessário pelo menos um item válido para criar o agendamento múltiplo.')
                    return render(request, 'finance/multiple_scheduler_form.html', {
                        'form': form,
                        'formset': formset
                    })
            
            messages.success(request, f'Agendamento múltiplo criado com sucesso! {len(created_schedulers)} item(ns) criado(s).')
            return redirect('finance:scheduler_list')
        else:
            messages.error(request, 'Por favor, corrija os erros abaixo.')
    else:
        form = MultipleSchedulerForm()
        formset = MultipleSchedulerItemFormSet()
    
    return render(request, 'finance/multiple_scheduler_form.html', {
        'form': form,
        'formset': formset
    })


def multiple_scheduler_update(request, group_id):
    """Editar agendamento múltiplo existente"""
    # Buscar todos os schedulers do grupo
    schedulers = Scheduler.objects.filter(
        multiple_scheduler_group_id=group_id,
        is_multiple=True
    ).order_by('id')
    
    if not schedulers.exists():
        messages.error(request, 'Agendamento múltiplo não encontrado.')
        return redirect('finance:scheduler_list')
    
    # Usar o primeiro scheduler como referência para dados compartilhados
    first_scheduler = schedulers.first()
    
    if request.method == 'POST':
        form = MultipleSchedulerForm(request.POST)
        formset = MultipleSchedulerItemFormSet(request.POST)
        
        # Verificar erros de validação
        if not form.is_valid():
            messages.error(request, 'Por favor, corrija os erros no formulário principal.')
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
        
        if not formset.is_valid():
            messages.error(request, 'Por favor, corrija os erros nos itens do agendamento.')
            for form_index, item_form in enumerate(formset):
                if item_form.errors:
                    for field, errors in item_form.errors.items():
                        for error in errors:
                            messages.error(request, f'Item {form_index + 1} - {field}: {error}')
                if item_form.non_field_errors():
                    for error in item_form.non_field_errors():
                        messages.error(request, f'Item {form_index + 1}: {error}')
        
        if form.is_valid() and formset.is_valid():
            # Obter dados compartilhados do formulário
            account = form.cleaned_data['account']
            beneficiary = form.cleaned_data['beneficiary']
            due_date = form.cleaned_data.get('due_date')
            purchase_date = form.cleaned_data.get('purchase_date')
            notes = form.cleaned_data.get('notes', '')
            recurrence_type = form.cleaned_data['recurrence_type']
            recurrence_interval = form.cleaned_data['recurrence_interval']
            termination_type = form.cleaned_data['termination_type']
            remaining_installments = form.cleaned_data.get('remaining_installments')
            final_date = form.cleaned_data.get('final_date')
            status = form.cleaned_data['status']
            
            # Validar transferências: destino deve ser diferente da origem
            for item_form in formset:
                if item_form.cleaned_data:
                    # Verificar se está marcado para deletar
                    if item_form.cleaned_data.get('DELETE'):
                        continue  # Pular este item
                    
                    item_data = item_form.cleaned_data
                    value = item_data.get('value')
                    
                    if not value:  # Skip empty forms
                        continue
                    
                    if item_data.get('is_transfer'):
                        destination_account = item_data.get('destination_account')
                        if destination_account and destination_account == account:
                            messages.error(request, 'A conta de destino deve ser diferente da conta de origem para transferências.')
                            return render(request, 'finance/multiple_scheduler_form.html', {
                                'form': form,
                                'formset': formset,
                                'group_id': group_id
                            })
            
            # Deletar schedulers antigos e criar novos
            with db_transaction.atomic():
                # Deletar todos os schedulers do grupo
                schedulers.delete()
                
                # Criar novos schedulers para cada item válido
                created_schedulers = []
                for item_form in formset:
                    if item_form.cleaned_data:
                        # Verificar se está marcado para deletar
                        if item_form.cleaned_data.get('DELETE'):
                            continue  # Pular este item
                        
                        item_data = item_form.cleaned_data
                        value = item_data.get('value')
                        
                        if not value:  # Skip empty forms
                            continue
                        
                        is_transfer = item_data.get('is_transfer', False)
                        
                        if is_transfer:
                            # Criar transferência (2 schedulers: débito e crédito)
                            destination_account = item_data.get('destination_account')
                            
                            # Scheduler de débito (conta origem)
                            debit_scheduler = Scheduler(
                                account=account,
                                beneficiary=beneficiary,
                                subcategory=None,
                                transaction_type='DB',
                                value=value,
                                due_date=due_date,
                                purchase_date=purchase_date,
                                notes=notes,
                                recurrence_type=recurrence_type,
                                recurrence_interval=recurrence_interval,
                                termination_type=termination_type,
                                remaining_installments=remaining_installments,
                                final_date=final_date,
                                status=status,
                                multiple_scheduler_group_id=group_id,
                                is_multiple=True,
                                is_transfer=True,
                                destination_account=destination_account,
                            )
                            
                            # Scheduler de crédito (conta destino)
                            credit_scheduler = Scheduler(
                                account=destination_account,
                                beneficiary=beneficiary,
                                subcategory=None,
                                transaction_type='CR',
                                value=value,
                                due_date=due_date,
                                purchase_date=purchase_date,
                                notes=notes,
                                recurrence_type=recurrence_type,
                                recurrence_interval=recurrence_interval,
                                termination_type=termination_type,
                                remaining_installments=remaining_installments,
                                final_date=final_date,
                                status=status,
                                multiple_scheduler_group_id=group_id,
                                is_multiple=True,
                                is_transfer=True,
                                destination_account=None,  # O scheduler de crédito não precisa de destination_account
                            )
                            
                            # Definir original_due_date se não estiver definido
                            if debit_scheduler.due_date and not debit_scheduler.original_due_date:
                                debit_scheduler.original_due_date = debit_scheduler.due_date
                            if credit_scheduler.due_date and not credit_scheduler.original_due_date:
                                credit_scheduler.original_due_date = credit_scheduler.due_date
                            
                            debit_scheduler.save()
                            credit_scheduler.save()
                            created_schedulers.extend([debit_scheduler, credit_scheduler])
                        else:
                            # Criar Scheduler normal para este item
                            scheduler = Scheduler(
                                account=account,
                                beneficiary=beneficiary,
                                subcategory=item_data.get('subcategory'),
                                transaction_type=item_data['transaction_type'],
                                value=value,
                                due_date=due_date,
                                purchase_date=purchase_date,
                                notes=notes,
                                recurrence_type=recurrence_type,
                                recurrence_interval=recurrence_interval,
                                termination_type=termination_type,
                                remaining_installments=remaining_installments,
                                final_date=final_date,
                                status=status,
                                multiple_scheduler_group_id=group_id,
                                is_multiple=True,
                                is_transfer=False,
                                destination_account=None,
                            )
                            
                            # Definir original_due_date se não estiver definido
                            if scheduler.due_date and not scheduler.original_due_date:
                                scheduler.original_due_date = scheduler.due_date
                            
                            scheduler.save()
                            created_schedulers.append(scheduler)
                
                if not created_schedulers:
                    messages.error(request, 'É necessário pelo menos um item válido para atualizar o agendamento múltiplo.')
                    return render(request, 'finance/multiple_scheduler_form.html', {
                        'form': form,
                        'formset': formset,
                        'group_id': group_id
                    })
            
            messages.success(request, f'Agendamento múltiplo atualizado com sucesso! {len(created_schedulers)} item(ns) atualizado(s).')
            return redirect('finance:scheduler_list')
        else:
            messages.error(request, 'Por favor, corrija os erros abaixo.')
    else:
        # Preparar dados iniciais do formulário
        initial_data = {
            'account': first_scheduler.account,
            'beneficiary': first_scheduler.beneficiary,
            'due_date': first_scheduler.due_date,
            'purchase_date': first_scheduler.purchase_date,
            'notes': first_scheduler.notes,
            'recurrence_type': first_scheduler.recurrence_type,
            'recurrence_interval': first_scheduler.recurrence_interval,
            'termination_type': first_scheduler.termination_type,
            'remaining_installments': first_scheduler.remaining_installments,
            'final_date': first_scheduler.final_date,
            'status': first_scheduler.status,
        }
        form = MultipleSchedulerForm(initial=initial_data)
        
        # Preparar dados iniciais do formset
        # Separar schedulers normais e transferências
        # Para transferências, o scheduler de débito tem destination_account preenchido
        # O scheduler de crédito tem destination_account=None e account = destination_account do débito
        formset_data = []
        
        for scheduler in schedulers:
            if scheduler.is_transfer:
                if scheduler.destination_account:
                    # É o scheduler de débito - adicionar ao formset
                    formset_data.append({
                        'subcategory': None,
                        'transaction_type': None,  # Não usado para transferências
                        'value': scheduler.value,
                        'is_transfer': True,
                        'destination_account': scheduler.destination_account,
                    })
                # Scheduler de crédito não precisa ser adicionado (já representado pelo par)
            else:
                # Scheduler normal
                formset_data.append({
                    'subcategory': scheduler.subcategory,
                    'transaction_type': scheduler.transaction_type,
                    'value': scheduler.value,
                    'is_transfer': False,
                    'destination_account': None,
                })
        
        # Criar formset com extra=0 quando editando para evitar item vazio
        from django.forms import formset_factory
        MultipleSchedulerItemFormSetEdit = formset_factory(
            MultipleSchedulerItemForm,
            extra=0,
            can_delete=True,
            min_num=1,
            validate_min=True
        )
        formset = MultipleSchedulerItemFormSetEdit(initial=formset_data)
    
    return render(request, 'finance/multiple_scheduler_form.html', {
        'form': form,
        'formset': formset,
        'group_id': group_id
    })


def multiple_scheduler_delete(request, group_id):
    """Deletar agendamento múltiplo"""
    # Buscar todos os schedulers do grupo
    schedulers = Scheduler.objects.filter(
        multiple_scheduler_group_id=group_id,
        is_multiple=True
    ).order_by('id')
    
    if not schedulers.exists():
        messages.error(request, 'Agendamento múltiplo não encontrado.')
        return redirect('finance:scheduler_list')
    
    # Usar o primeiro scheduler como referência
    first_scheduler = schedulers.first()
    
    if request.method == 'POST':
        count = schedulers.count()
        schedulers.delete()
        messages.success(request, f'Agendamento múltiplo deletado com sucesso! {count} item(ns) removido(s).')
        return redirect('finance:scheduler_list')
    
    return render(request, 'finance/multiple_scheduler_confirm_delete.html', {
        'schedulers': schedulers,
        'group_id': group_id,
        'first_scheduler': first_scheduler
    })


def multiple_scheduler_register(request, group_id):
    """Registrar transações do agendamento múltiplo"""
    # Buscar todos os schedulers do grupo
    schedulers = Scheduler.objects.filter(
        multiple_scheduler_group_id=group_id,
        is_multiple=True
    ).order_by('id')
    
    if not schedulers.exists():
        messages.error(request, 'Agendamento múltiplo não encontrado.')
        return redirect('finance:scheduler_list')
    
    # Usar o primeiro scheduler como referência para dados compartilhados
    first_scheduler = schedulers.first()
    
    if request.method == 'POST':
        formset = MultipleSchedulerRegisterItemFormSet(request.POST)
        
        if formset.is_valid():
            try:
                # Validar transferências: destino deve ser diferente da origem
                for item_form in formset:
                    item_data = item_form.cleaned_data
                    if item_data.get('is_transfer'):
                        destination_account = item_data.get('destination_account')
                        if destination_account and destination_account == first_scheduler.account:
                            messages.error(request, 'A conta de destino deve ser diferente da conta de origem para transferências.')
                            next_due_date = first_scheduler.get_next_due_date_after_registration()
                            return render(request, 'finance/multiple_scheduler_register.html', {
                                'schedulers': schedulers,
                                'formset': formset,
                                'next_due_date': next_due_date,
                                'group_id': group_id
                            })
                
                # Agrupar schedulers na mesma ordem que foi usado no GET
                # Ordem: schedulers normais primeiro, depois transferências (apenas débito)
                grouped_schedulers = []
                processed_credit_ids = set()
                
                # Primeiro, adicionar schedulers normais
                for scheduler in schedulers:
                    if not scheduler.is_transfer:
                        grouped_schedulers.append(scheduler)
                
                # Depois, adicionar schedulers de transferência (apenas débito)
                for scheduler in schedulers:
                    if scheduler.is_transfer and scheduler.destination_account:
                        # É o scheduler de débito - adicionar ao grupo
                        grouped_schedulers.append(scheduler)
                        # Encontrar e marcar o scheduler de crédito correspondente
                        credit_scheduler = schedulers.filter(
                            is_transfer=True,
                            destination_account=None,
                            account=scheduler.destination_account,
                            value=scheduler.value,
                            due_date=scheduler.due_date
                        ).exclude(id__in=processed_credit_ids).first()
                        if credit_scheduler:
                            processed_credit_ids.add(credit_scheduler.id)
                
                # Registrar transações para cada item do formset
                created_transactions = []
                updated_schedulers = set()  # IDs dos schedulers já atualizados pelo método register()
                
                # Gerar UUID para o grupo de transações múltiplas
                multiple_transaction_group_id = uuid.uuid4()
                
                with db_transaction.atomic():
                    # Garantir que temos o mesmo número de itens no formset e nos schedulers agrupados
                    if len(formset) != len(grouped_schedulers):
                        messages.error(request, f'Erro: número de itens no formulário ({len(formset)}) não corresponde ao número de schedulers ({len(grouped_schedulers)}).')
                        next_due_date = first_scheduler.get_next_due_date_after_registration()
                        return render(request, 'finance/multiple_scheduler_register.html', {
                            'schedulers': schedulers,
                            'formset': formset,
                            'next_due_date': next_due_date,
                            'group_id': group_id
                        })
                    
                    for i, item_form in enumerate(formset):
                        if i >= len(grouped_schedulers):
                            break
                        
                        scheduler = grouped_schedulers[i]
                        scheduler.refresh_from_db()
                        
                        if not scheduler.is_valid():
                            messages.warning(request, f'Scheduler {scheduler.id} não é válido e será pulado.')
                            continue  # Pular schedulers inválidos
                        
                        item_data = item_form.cleaned_data
                        
                        if scheduler.is_transfer and scheduler.destination_account:
                            # Transferência: criar par de transações
                            destination_account = item_data.get('destination_account', scheduler.destination_account)
                            source_account = scheduler.account
                            
                            if source_account == destination_account:
                                messages.error(request, 'A conta de destino deve ser diferente da conta de origem para transferências.')
                                next_due_date = first_scheduler.get_next_due_date_after_registration()
                                return render(request, 'finance/multiple_scheduler_register.html', {
                                    'schedulers': schedulers,
                                    'formset': formset,
                                    'next_due_date': next_due_date,
                                    'group_id': group_id
                                })
                            
                            value = item_data.get('value', scheduler.value)
                            
                            # Criar débito na conta de origem
                            transfer_group_id = uuid.uuid4()
                            debit_transaction = Transaction.objects.create(
                                account=source_account,
                                beneficiary=scheduler.beneficiary,
                                subcategory=None,  # Transferências não têm subcategoria
                                transaction_type='DB',
                                value=value,
                                due_date=scheduler.due_date,
                                transaction_date=scheduler.due_date,
                                purchase_date=scheduler.purchase_date,
                                notes=scheduler.notes,
                                is_transfer=True,
                                transfer_group_id=transfer_group_id,
                                is_multiple=True,
                                multiple_transaction_group_id=multiple_transaction_group_id,
                            )
                            
                            # Criar crédito na conta de destino
                            credit_transaction = Transaction.objects.create(
                                account=destination_account,
                                beneficiary=scheduler.beneficiary,
                                subcategory=None,
                                transaction_type='CR',
                                value=value,
                                due_date=scheduler.due_date,
                                transaction_date=scheduler.due_date,
                                purchase_date=scheduler.purchase_date,
                                notes=scheduler.notes,
                                is_transfer=True,
                                transfer_group_id=transfer_group_id,
                                is_multiple=True,
                                multiple_transaction_group_id=multiple_transaction_group_id,
                            )
                            
                            created_transactions.extend([debit_transaction, credit_transaction])
                            
                            # Marcar schedulers de transferência para atualização manual
                            # (não usar register() porque criamos as transações manualmente)
                            updated_schedulers.add(scheduler.id)
                            # Encontrar e marcar o scheduler de crédito correspondente
                            credit_scheduler = schedulers.filter(
                                is_transfer=True,
                                destination_account=None,
                                account=scheduler.destination_account,
                                value=scheduler.value,
                                due_date=scheduler.due_date
                            ).first()
                            if credit_scheduler:
                                updated_schedulers.add(credit_scheduler.id)
                        else:
                            # Transação normal - usar register() que já atualiza o scheduler
                            transaction_data = {
                                'subcategory': item_data.get('subcategory', scheduler.subcategory),
                                'transaction_type': item_data.get('transaction_type', scheduler.transaction_type),
                                'value': item_data.get('value', scheduler.value),
                                'is_multiple': True,
                                'multiple_transaction_group_id': multiple_transaction_group_id,
                                'is_transfer': False,
                                'transfer_group_id': None,
                            }
                            transaction = scheduler.register(transaction_data=transaction_data)
                            created_transactions.append(transaction)
                            # Marcar como já atualizado pelo método register()
                            updated_schedulers.add(scheduler.id)
                    
                    # Atualizar schedulers de transferência manualmente (não foram atualizados pelo register())
                    all_group_schedulers = Scheduler.objects.filter(
                        multiple_scheduler_group_id=group_id,
                        is_multiple=True
                    )
                    
                    for group_scheduler in all_group_schedulers:
                        if group_scheduler.id not in updated_schedulers:
                            # Este scheduler não foi atualizado ainda (pode ser um scheduler de crédito de transferência)
                            continue
                        
                        # Atualizar apenas os schedulers de transferência que criamos manualmente
                        if group_scheduler.is_transfer:
                            group_scheduler.refresh_from_db()
                            group_scheduler.registered_count += 1
                            
                            # Decrementar parcelas restantes se aplicável
                            if group_scheduler.termination_type == 'INSTALLMENTS' and group_scheduler.remaining_installments is not None:
                                group_scheduler.remaining_installments -= 1
                            
                            # Calcular próxima data baseada na due_date atual + intervalo
                            next_due_date_for_scheduler = group_scheduler.calculate_next_due_date_from_current()
                            if next_due_date_for_scheduler:
                                group_scheduler.due_date = next_due_date_for_scheduler
                            
                            # Verificar se deve marcar como concluído
                            if group_scheduler.termination_type == 'INSTALLMENTS':
                                if group_scheduler.remaining_installments is not None and group_scheduler.remaining_installments <= 0:
                                    group_scheduler.mark_completed()
                                else:
                                    group_scheduler.save()
                            elif group_scheduler.termination_type == 'FINAL_DATE':
                                if group_scheduler.final_date and next_due_date_for_scheduler and next_due_date_for_scheduler > group_scheduler.final_date:
                                    group_scheduler.mark_completed()
                                else:
                                    group_scheduler.save()
                            else:
                                group_scheduler.save()
                
                # Calcular próxima data (usar a do primeiro scheduler)
                first_scheduler.refresh_from_db()
                next_due_date = first_scheduler.due_date
                
                messages.success(request, f'Transações registradas com sucesso! {len(created_transactions)} transação(ões) criada(s). Próxima data: {next_due_date}')
                return redirect('finance:scheduler_list')
            except ValueError as e:
                messages.error(request, str(e))
        else:
            messages.error(request, 'Por favor, corrija os erros abaixo.')
    else:
        # Criar formset com dados dos schedulers do grupo
        # Agrupar schedulers na mesma ordem: normais primeiro, depois transferências (apenas débito)
        initial_data = []
        
        # Primeiro, adicionar schedulers normais
        for scheduler in schedulers:
            if not scheduler.is_transfer:
                initial_data.append({
                    'subcategory': scheduler.subcategory,
                    'transaction_type': scheduler.transaction_type,
                    'value': scheduler.value,
                    'is_transfer': False,
                    'destination_account': None,
                })
        
        # Depois, adicionar schedulers de transferência (apenas débito)
        for scheduler in schedulers:
            if scheduler.is_transfer and scheduler.destination_account:
                # É o scheduler de débito - adicionar ao formset
                initial_data.append({
                    'subcategory': None,
                    'transaction_type': None,  # Não usado para transferências
                    'value': scheduler.value,
                    'is_transfer': True,
                    'destination_account': scheduler.destination_account,
                })
                # Scheduler de crédito não precisa ser adicionado (já representado pelo par)
        
        formset = MultipleSchedulerRegisterItemFormSet(initial=initial_data)
    
    next_due_date = first_scheduler.get_next_due_date_after_registration()
    return render(request, 'finance/multiple_scheduler_register.html', {
        'schedulers': schedulers,
        'formset': formset,
        'next_due_date': next_due_date,
        'group_id': group_id
    })


# Asset Views
def asset_list(request):
    """Lista de ativos"""
    assets = Asset.objects.all()
    return render(request, 'finance/asset_list.html', {'assets': assets})


def asset_create(request):
    """Criar novo ativo"""
    if request.method == 'POST':
        form = AssetForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Ativo criado com sucesso!')
            return redirect('finance:asset_list')
    else:
        form = AssetForm()
    return render(request, 'finance/asset_form.html', {'form': form})


def asset_update(request, pk):
    """Editar ativo existente"""
    asset = get_object_or_404(Asset, pk=pk)
    if request.method == 'POST':
        form = AssetForm(request.POST, instance=asset)
        if form.is_valid():
            form.save()
            messages.success(request, 'Ativo atualizado com sucesso!')
            return redirect('finance:asset_list')
    else:
        form = AssetForm(instance=asset)
    return render(request, 'finance/asset_form.html', {'form': form, 'asset': asset})


def asset_delete(request, pk):
    """Deletar ativo"""
    asset = get_object_or_404(Asset, pk=pk)
    if request.method == 'POST':
        asset.delete()
        messages.success(request, 'Ativo deletado com sucesso!')
        return redirect('finance:asset_list')
    return render(request, 'finance/asset_confirm_delete.html', {'asset': asset})


# AssetTransaction Views
def asset_transaction_list(request):
    """Lista de transações de ativos"""
    transactions = AssetTransaction.objects.all().select_related('asset', 'account')
    return render(request, 'finance/asset_transaction_list.html', {'transactions': transactions})


def asset_transaction_create(request):
    """Criar nova transação de ativo"""
    if request.method == 'POST':
        form = AssetTransactionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Transação de ativo criada com sucesso!')
            return redirect('finance:asset_transaction_list')
    else:
        form = AssetTransactionForm()
    return render(request, 'finance/asset_transaction_form.html', {'form': form})


def asset_transaction_update(request, pk):
    """Editar transação de ativo existente"""
    transaction = get_object_or_404(AssetTransaction, pk=pk)
    if request.method == 'POST':
        form = AssetTransactionForm(request.POST, instance=transaction)
        if form.is_valid():
            form.save()
            messages.success(request, 'Transação de ativo atualizada com sucesso!')
            return redirect('finance:asset_transaction_list')
    else:
        form = AssetTransactionForm(instance=transaction)
    return render(request, 'finance/asset_transaction_form.html', {'form': form, 'transaction': transaction})


def asset_transaction_delete(request, pk):
    """Deletar transação de ativo"""
    transaction = get_object_or_404(AssetTransaction, pk=pk)
    if request.method == 'POST':
        transaction.delete()
        messages.success(request, 'Transação de ativo deletada com sucesso!')
        return redirect('finance:asset_transaction_list')
    return render(request, 'finance/asset_transaction_confirm_delete.html', {'transaction': transaction})


# AssetPosition Views
def asset_position_create(request):
    """Criar nova posição de ativo"""
    if request.method == 'POST':
        form = AssetPositionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Posição de ativo criada com sucesso!')
            return redirect('finance:asset_list')
    else:
        form = AssetPositionForm()
    return render(request, 'finance/asset_position_form.html', {'form': form})


def asset_position_update(request, pk):
    """Editar posição de ativo existente"""
    position = get_object_or_404(AssetPosition, pk=pk)
    if request.method == 'POST':
        form = AssetPositionForm(request.POST, instance=position)
        if form.is_valid():
            form.save()
            messages.success(request, 'Posição de ativo atualizada com sucesso!')
            return redirect('finance:asset_list')
    else:
        form = AssetPositionForm(instance=position)
    return render(request, 'finance/asset_position_form.html', {'form': form, 'position': position})


def asset_position_delete(request, pk):
    """Deletar posição de ativo"""
    position = get_object_or_404(AssetPosition, pk=pk)
    if request.method == 'POST':
        position.delete()
        messages.success(request, 'Posição de ativo deletada com sucesso!')
        return redirect('finance:asset_list')
    return render(request, 'finance/asset_position_confirm_delete.html', {'position': position})


# Reports Views
def reports_index(request):
    """Página inicial de relatórios"""
    return render(request, 'finance/reports_index.html')


def account_statement(request):
    """Exibe o extrato bancário da conta"""
    accounts = Account.objects.all()
    
    # Valores padrão: início do mês atual e data de hoje
    today = date.today()
    first_day_of_month = date(today.year, today.month, 1)
    
    # Obter parâmetros do GET
    account_id = request.GET.get('account')
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    account = None
    # Usar valores padrão se não fornecidos
    start_date = first_day_of_month
    end_date = today
    movements = []
    previous_balance = None
    final_balance = None
    
    # Processar data inicial
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, 'Data inicial inválida.')
            start_date = first_day_of_month
    else:
        # Se não foi fornecida, usar padrão
        start_date = first_day_of_month
    
    # Processar data final
    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, 'Data final inválida.')
            end_date = today
    else:
        # Se não foi fornecida, usar padrão
        end_date = today
    
    if account_id:
        account = get_object_or_404(Account, pk=account_id)
        
        if account and start_date and end_date:
            if start_date > end_date:
                messages.error(request, 'Data inicial deve ser anterior à data final.')
            else:
                movements = account.get_statement(start_date, end_date)
                previous_balance = account.get_previous_balance(start_date)
                if movements:
                    final_balance = movements[-1]['balance']
                else:
                    final_balance = previous_balance
    
    return render(request, 'finance/account_statement.html', {
        'accounts': accounts,
        'selected_account': account,
        'start_date': start_date,
        'end_date': end_date,
        'movements': movements,
        'previous_balance': previous_balance,
        'final_balance': final_balance,
    })


def asset_stock_position_report(request):
    """Relatório de posição de estoque de ativos"""
    from decimal import Decimal
    
    # Buscar todos os ativos que têm transações
    assets = Asset.objects.filter(
        transactions__isnull=False
    ).distinct().order_by('code')
    
    report_data = []
    
    for asset in assets:
        # Buscar todas as transações ordenadas por data
        transactions = AssetTransaction.objects.filter(
            asset=asset
        ).order_by('date', 'created_at')
        
        # Inicializar variáveis
        valor_total_acumulado = Decimal('0')
        quantidade_atual = Decimal('0')
        
        # Iterar sobre transações seguindo a regra de preço médio
        for trans in transactions:
            if trans.operation_type in ['BUY', 'SUB']:
                # Compras: adicionam ao valor total acumulado e quantidade
                custo_operacao = (trans.quantity * trans.price) + trans.fees
                valor_total_acumulado += custo_operacao
                quantidade_atual += trans.quantity
            elif trans.operation_type == 'SELL':
                # Vendas: apenas reduzem quantidade (mantém valor total acumulado)
                quantidade_atual -= trans.quantity
            elif trans.operation_type in ['SPLIT', 'BONUS', 'CAPITAL_INCREASE', 'RIGHTS_EXERCISE']:
                # Operações que aumentam quantidade sem custo
                quantidade_atual += trans.quantity
            elif trans.operation_type == 'GROUP':
                # Grupamento: reduz quantidade sem alterar valor total
                quantidade_atual -= trans.quantity
        
        # Filtrar apenas ativos com quantidade > 0
        if quantidade_atual > 0:
            # Calcular preço médio
            preco_medio = valor_total_acumulado / quantidade_atual if quantidade_atual > 0 else Decimal('0')
            
            # Calcular valor total
            valor_total = quantidade_atual * preco_medio
            
            report_data.append({
                'asset': asset,
                'code': asset.code,
                'description': asset.name,
                'currency': asset.currency,
                'quantity': quantidade_atual,
                'unit_value': preco_medio,
                'total_value': valor_total,
            })
    
    # Calcular totais
    total_value_all = sum(item['total_value'] for item in report_data)
    
    return render(request, 'finance/asset_stock_position_report.html', {
        'report_data': report_data,
        'total_value_all': total_value_all,
    })


def budget_manage(request):
    """View para gerenciar orçamento em formato de tabela dinâmica"""
    from decimal import Decimal, InvalidOperation
    
    # Obter ano selecionado (query param ou ano atual)
    selected_year = int(request.GET.get('year', date.today().year))
    
    # Obter todas as subcategorias ordenadas por categoria/subcategoria
    subcategories = Subcategory.objects.all().select_related('category').order_by('category', 'subcategory')
    
    # Buscar orçamentos do ano selecionado
    budgets = Budget.objects.filter(
        budget_date__year=selected_year
    ).select_related('subcategory', 'subcategory__category')
    
    # Criar dicionário para acesso rápido: key = (subcategory_id, month) -> amount
    budgets_dict = {}
    for budget in budgets:
        key = (budget.subcategory_id, budget.month)
        budgets_dict[key] = budget.amount
    
    # Preparar dados para o template
    budget_data = []
    for subcategory in subcategories:
        # Calcular média do ano anterior
        avg_previous = Budget.get_average_previous_year(subcategory, selected_year)
        
        # Obter valores dos 12 meses
        months_data = []
        total_year = Decimal('0.00')
        for month in range(1, 13):
            key = (subcategory.id, month)
            amount = budgets_dict.get(key, Decimal('0.00'))
            months_data.append({
                'month': month,
                'amount': amount
            })
            total_year += amount
        
        budget_data.append({
            'subcategory': subcategory,
            'default_transaction_type': subcategory.default_transaction_type,
            'avg_previous_year': avg_previous,
            'months': months_data,
            'total_year': total_year
        })
    
    # Calcular totais separados por tipo
    totals_by_type = Budget.get_totals_by_type(selected_year)
    
    # Processar POST (salvar orçamento)
    if request.method == 'POST':
        year = int(request.POST.get('year', selected_year))
        
        with db_transaction.atomic():
            # Processar cada subcategoria
            for subcategory in subcategories:
                for month in range(1, 13):
                    field_name = f"budget_{subcategory.id}_{month}"
                    value = request.POST.get(field_name, '').strip()
                    
                    if value:
                        try:
                            # Converter valor (tratar vírgula/ponto decimal)
                            value = value.replace(',', '.')
                            amount = Decimal(value)
                            
                            # Criar budget_date usando date(year, month, 1) (sempre dia 1)
                            budget_date = date(year, month, 1)
                            
                            # Usar update_or_create com subcategory e budget_date
                            Budget.objects.update_or_create(
                                subcategory=subcategory,
                                budget_date=budget_date,
                                defaults={'amount': amount}
                            )
                        except (ValueError, InvalidOperation):
                            pass  # Ignorar valores inválidos
                    else:
                        # Se o campo estiver vazio, remover o orçamento se existir
                        budget_date = date(year, month, 1)
                        Budget.objects.filter(
                            subcategory=subcategory,
                            budget_date=budget_date
                        ).delete()
            
            messages.success(request, f'Orçamento de {year} salvo com sucesso!')
            return redirect(f"{reverse('finance:budget_manage')}?year={year}")
    
    # Anos disponíveis (últimos 5 anos + próximos 2)
    current_year = date.today().year
    years = list(range(current_year - 5, current_year + 3))
    
    # Nomes dos meses
    months = [
        (1, 'Janeiro'), (2, 'Fevereiro'), (3, 'Março'),
        (4, 'Abril'), (5, 'Maio'), (6, 'Junho'),
        (7, 'Julho'), (8, 'Agosto'), (9, 'Setembro'),
        (10, 'Outubro'), (11, 'Novembro'), (12, 'Dezembro'),
    ]
    
    context = {
        'budget_data': budget_data,
        'selected_year': selected_year,
        'years': years,
        'months': months,
        'totals_by_type': totals_by_type,
    }
    
    return render(request, 'finance/budget_manage.html', context)


# Inventory Views
def inventory_list(request):
    """Lista de itens do inventário"""
    inventories = Inventory.objects.all()
    return render(request, 'finance/inventory_list.html', {'inventories': inventories})


def inventory_create(request):
    """Criar novo item do inventário"""
    if request.method == 'POST':
        form = InventoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Item do inventário criado com sucesso!')
            return redirect('finance:inventory_list')
    else:
        form = InventoryForm()
    return render(request, 'finance/inventory_form.html', {'form': form})


def inventory_update(request, pk):
    """Editar item do inventário existente"""
    inventory = get_object_or_404(Inventory, pk=pk)
    if request.method == 'POST':
        form = InventoryForm(request.POST, instance=inventory)
        if form.is_valid():
            form.save()
            messages.success(request, 'Item do inventário atualizado com sucesso!')
            return redirect('finance:inventory_list')
    else:
        form = InventoryForm(instance=inventory)
    return render(request, 'finance/inventory_form.html', {'form': form, 'inventory': inventory})


def inventory_delete(request, pk):
    """Deletar item do inventário"""
    inventory = get_object_or_404(Inventory, pk=pk)
    if request.method == 'POST':
        inventory.delete()
        messages.success(request, 'Item do inventário deletado com sucesso!')
        return redirect('finance:inventory_list')
    return render(request, 'finance/inventory_confirm_delete.html', {'inventory': inventory})


# Cash Flow Item Views
def cash_flow_item_list(request):
    """Lista de itens do fluxo de caixa"""
    all_items = CashFlowItem.objects.all().order_by('order', 'code')
    
    # Construir estrutura hierárquica com informações de nível
    items_data = []
    for item in all_items:
        # Determinar nível hierárquico
        level = item.code.count('.')
        
        # Verificar se tem filhos para mostrar botão expandir/recolher
        has_children = item.get_children().exists()
        parent_code = item.get_parent_code()
        
        items_data.append({
            'item': item,
            'level': level,
            'parent_code': parent_code,
            'has_children': has_children,
        })
    
    return render(request, 'finance/cash_flow_item_list.html', {'items': items_data})


def cash_flow_item_create(request):
    """Criar novo item do fluxo de caixa"""
    if request.method == 'POST':
        form = CashFlowItemForm(request.POST)
        rules_formset = CashFlowCalculationRuleFormSet(request.POST, prefix='rules')
        
        # Validar form primeiro
        if form.is_valid():
            calculation_type = form.cleaned_data.get('calculation_type')
            new_code = form.cleaned_data.get('code')
            
            # Verificar se código já existe e renumerar se necessário
            if CashFlowItem.objects.filter(code=new_code).exists():
                # Encontrar próximo código disponível
                next_available_code = CashFlowItem.find_next_available_code(new_code)
                # Renumerar item existente e seus descendentes
                CashFlowItem.renumber_code_and_descendants(new_code, next_available_code)
            
            # Se for SUBTOTAL, não precisa validar formset (pode estar vazio)
            if calculation_type == 'SUBTOTAL':
                form.rules_formset = rules_formset
                new_item = form.save()
                
                # Reorganizar ordens após criar novo item
                CashFlowItem.reorganize_orders()
                
                messages.success(request, 'Item do fluxo de caixa criado com sucesso!')
                return redirect('finance:cash_flow_item_list')
            
            # Se for RULES, validar formset
            elif calculation_type == 'RULES':
                if rules_formset.is_valid():
                    # Verificar se há pelo menos uma regra válida
                    has_valid_rule = False
                    for rule_form in rules_formset:
                        if rule_form.cleaned_data and not rule_form.cleaned_data.get('DELETE', False):
                            has_valid_rule = True
                            break
                    
                    if not has_valid_rule:
                        messages.error(request, 'Itens com tipo "Calcula por regras" devem ter pelo menos uma regra configurada.')
                        return render(request, 'finance/cash_flow_item_form.html', {
                            'form': form,
                            'rules_formset': rules_formset,
                        })
                    
                    form.rules_formset = rules_formset
                    new_item = form.save()
                    
                    # Reorganizar ordens após criar novo item
                    CashFlowItem.reorganize_orders()
                    
                    messages.success(request, 'Item do fluxo de caixa criado com sucesso!')
                    return redirect('finance:cash_flow_item_list')
    else:
        # Verificar se há parâmetros para pré-preencher
        parent_id = request.GET.get('parent_id')
        action = request.GET.get('action')  # 'sibling' ou 'child'
        
        initial_data = {}
        if parent_id and action:
            try:
                parent_item = CashFlowItem.objects.get(pk=parent_id)
                
                if action == 'sibling':
                    # Criar irmão: usar get_next_sibling_code()
                    next_code = parent_item.get_next_sibling_code()
                    initial_data['code'] = next_code
                    # Irmão acumula no mesmo lugar que o irmão existente
                    if parent_item.accumulates_in:
                        initial_data['accumulates_in'] = parent_item.accumulates_in
                elif action == 'child':
                    # Criar filho: usar get_next_child_code()
                    next_code = parent_item.get_next_child_code()
                    initial_data['code'] = next_code
                    # Filho acumula no pai
                    initial_data['accumulates_in'] = parent_item
                
                # Calcular ordem apropriada
                initial_data['order'] = CashFlowItem.get_next_order_for_code(initial_data['code'])
                
            except CashFlowItem.DoesNotExist:
                pass
        
        form = CashFlowItemForm(initial=initial_data)
        rules_formset = CashFlowCalculationRuleFormSet(prefix='rules')
    
    return render(request, 'finance/cash_flow_item_form.html', {
        'form': form,
        'rules_formset': rules_formset,
    })


def cash_flow_item_update(request, pk):
    """Editar item do fluxo de caixa existente"""
    item = get_object_or_404(CashFlowItem, pk=pk)
    
    if request.method == 'POST':
        form = CashFlowItemForm(request.POST, instance=item)
        rules_formset = CashFlowCalculationRuleFormSet(request.POST, prefix='rules')
        
        # Validar form primeiro
        if form.is_valid():
            calculation_type = form.cleaned_data.get('calculation_type')
            
            # Se for SUBTOTAL, não precisa validar formset (pode estar vazio)
            if calculation_type == 'SUBTOTAL':
                form.rules_formset = rules_formset
                form.save()
                messages.success(request, 'Item do fluxo de caixa atualizado com sucesso!')
                return redirect('finance:cash_flow_item_list')
            
            # Se for RULES, validar formset
            elif calculation_type == 'RULES':
                if rules_formset.is_valid():
                    # Verificar se há pelo menos uma regra válida
                    has_valid_rule = False
                    for rule_form in rules_formset:
                        if rule_form.cleaned_data and not rule_form.cleaned_data.get('DELETE', False):
                            has_valid_rule = True
                            break
                    
                    if not has_valid_rule:
                        messages.error(request, 'Itens com tipo "Calcula por regras" devem ter pelo menos uma regra configurada.')
                        return render(request, 'finance/cash_flow_item_form.html', {
                            'form': form,
                            'rules_formset': rules_formset,
                            'item': item,
                        })
                    
                    form.rules_formset = rules_formset
                    form.save()
                    messages.success(request, 'Item do fluxo de caixa atualizado com sucesso!')
                    return redirect('finance:cash_flow_item_list')
    else:
        form = CashFlowItemForm(instance=item)
        
        # Popular formset com regras existentes
        initial_data = []
        for rule in item.calculation_rules:
            rule_data = {'rule_type': rule.get('type')}
            if rule.get('type') == 'subcategory':
                rule_data['subcategory'] = rule.get('subcategory_id')
            elif rule.get('type') == 'asset_operation':
                rule_data['asset_operation_type'] = rule.get('operation_type')
                rule_data['asset_type'] = rule.get('asset_type', '')
            initial_data.append(rule_data)
        
        rules_formset = CashFlowCalculationRuleFormSet(prefix='rules', initial=initial_data)
    
    return render(request, 'finance/cash_flow_item_form.html', {
        'form': form,
        'rules_formset': rules_formset,
        'item': item,
    })


def cash_flow_item_delete(request, pk):
    """Deletar item do fluxo de caixa"""
    item = get_object_or_404(CashFlowItem, pk=pk)
    if request.method == 'POST':
        item.delete()
        messages.success(request, 'Item do fluxo de caixa deletado com sucesso!')
        return redirect('finance:cash_flow_item_list')
    return render(request, 'finance/cash_flow_item_confirm_delete.html', {'item': item})


def cash_flow_report(request):
    """Relatório de fluxo de caixa"""
    from decimal import Decimal
    
    # Filtros
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    account_id = request.GET.get('account')
    
    # Valores padrão
    if not start_date:
        today = date.today()
        start_date = date(today.year, today.month, 1).isoformat()
    if not end_date:
        end_date = date.today().isoformat()
    
    # Converter para date objects
    try:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        start_date = date.today().replace(day=1)
        end_date = date.today()
    
    account = None
    if account_id and account_id != 'all':
        try:
            account = Account.objects.get(pk=account_id)
        except Account.DoesNotExist:
            account = None
    
    # Buscar todos os itens ordenados por código
    all_items = CashFlowItem.objects.all().order_by('order', 'code')
    
    # Construir estrutura hierárquica com valores calculados
    report_data = []
    for item in all_items:
        value = item.calculate_value(start_date, end_date, account)
        
        # Se acumula em outro item, marcar
        accumulates_in_code = None
        if item.accumulates_in:
            accumulates_in_code = item.accumulates_in.code
        
        # Determinar nível hierárquico
        level = item.code.count('.')
        
        # Verificar se tem filhos para mostrar botão expandir/recolher
        has_children = item.get_children().exists()
        parent_code = item.get_parent_code()
        
        report_data.append({
            'item': item,
            'code': item.code,
            'description': item.description,
            'value': value,
            'accumulates_in_code': accumulates_in_code,
            'level': level,
            'has_children': has_children,
            'parent_code': parent_code,
        })
    
    # Adicionar valores acumulados aos dados
    # Para itens SUBTOTAL que acumulam valores de outros itens, o valor já foi calculado
    # Para itens que acumulam em outros, precisamos adicionar ao item de destino
    for data in report_data:
        # O valor calculado já inclui a lógica de SUBTOTAL (soma filhos ou itens que acumulam)
        data['accumulated_value'] = data['value']
    
    # Total geral (último item de nível raiz, geralmente o "Caixa Líquido")
    total_general = Decimal('0')
    root_items = [d for d in report_data if d['level'] == 0]
    if root_items:
        # Pegar o último item de nível raiz (geralmente o "Caixa Líquido")
        total_general = root_items[-1]['accumulated_value']
    else:
        # Fallback: somar todos os valores
        for data in report_data:
            total_general += data['value']
    
    accounts = Account.objects.all()
    
    return render(request, 'finance/cash_flow_report.html', {
        'report_data': report_data,
        'start_date': start_date,
        'end_date': end_date,
        'selected_account': account,
        'accounts': accounts,
        'total_general': total_general,
    })
