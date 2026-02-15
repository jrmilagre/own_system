from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction as db_transaction
from django.core.paginator import Paginator
from django.db.models import Q, Avg
from django.db import close_old_connections
from django.forms import formset_factory
from django.views.generic import CreateView, UpdateView, DeleteView
from datetime import datetime, date, timedelta
from collections import defaultdict
import traceback
import uuid
import json as json_module
import time
import hashlib
from .models import Account, Beneficiary, Category, Subcategory, Transaction, Scheduler, Asset, AssetTransaction, AssetPosition, Budget, Inventory, CashFlowItem, AssetTransactionCategoryConfig
from .forms import (
    AccountForm, BeneficiaryForm, CategoryForm, SubcategoryForm, TransactionForm, SchedulerForm,
    MultipleTransactionForm, MultipleTransactionItemForm, MultipleTransactionItemFormSet,
    MultipleSchedulerForm, MultipleSchedulerItemForm, MultipleSchedulerItemFormSet,
    MultipleSchedulerRegisterItemFormSet, AssetForm, AssetTransactionForm, AssetPositionForm, InventoryForm, AssetTransactionCategoryConfigForm,
    CashFlowItemForm, CashFlowCalculationRuleFormSet, TransactionFilterForm, SchedulerFilterForm, AccountStatementFilterForm, BudgetForm,
    TransactionsImportForm, TransactionsStagingFilterForm, SubcategoryMoveForm,
    AssetTransactionsImportForm, AssetTransactionsStagingFilterForm, AccountFilterForm, AssetFilterForm, AssetTransactionFilterForm,
    MultipleAssetTransactionForm, MultipleAssetTransactionItemForm, MultipleAssetTransactionItemFormSet
)
from .transactions_parser import TransactionsParser
from .asset_transactions_parser import AssetTransactionsParser
from .chatbot_service import get_chatbot_response
from .services.budget_service import (
    calculate_spent_by_subcategory,
    calculate_spent_by_category,
    calculate_budget_by_subcategory,
    calculate_budget_by_category,
    calculate_budget_by_subcategory_year,
    calculate_budget_by_category_year,
    calculate_budget_accumulated_by_subcategory,
    calculate_budget_accumulated_by_category,
)
from .constants import (
    TRANSACTIONS_PER_PAGE,
    ACCOUNTS_PER_PAGE,
    SCHEDULERS_PER_PAGE,
    ASSETS_PER_PAGE,
    ASSET_TRANSACTIONS_PER_PAGE,
    BUDGETS_PER_PAGE,
    IMPORT_STAGING_TRANSACTIONS_PER_PAGE,
    IMPORT_STAGING_ASSET_TRANSACTIONS_PER_PAGE,
    CHAT_HISTORY_MAX_MESSAGES,
    TRANSACTION_TYPE_CR,
    TRANSACTION_TYPE_DB,
    TRANSACTIONS_IMPORT_BATCH_SIZE,
    TRANSACTIONS_IMPORT_PROGRESS_LOG_INTERVAL,
)
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode
import json
import logging
import os

from apps.finance.views.common import prepare_transactions_for_session

logger = logging.getLogger(__name__)

# Autenticação: quando LOGIN_URL e autenticação estiverem configurados, adicionar
# LoginRequiredMixin como primeiro mixin nas CBVs e @login_required nas FBVs
# (incluindo APIs: get_budget_info, quick_create_*, chatbot_api).


# Class-based views for simple CRUD (optional: add LoginRequiredMixin when auth is enabled)
class AccountCreateView(CreateView):
    model = Account
    form_class = AccountForm
    template_name = 'finance/account_form.html'
    success_url = reverse_lazy('finance:account_list')


class AccountUpdateView(UpdateView):
    model = Account
    form_class = AccountForm
    template_name = 'finance/account_form.html'
    success_url = reverse_lazy('finance:account_list')
    context_object_name = 'account'


class AccountDeleteView(DeleteView):
    model = Account
    template_name = 'finance/account_confirm_delete.html'
    success_url = reverse_lazy('finance:account_list')
    context_object_name = 'account'


class BeneficiaryCreateView(CreateView):
    model = Beneficiary
    form_class = BeneficiaryForm
    template_name = 'finance/beneficiary_form.html'
    success_url = reverse_lazy('finance:beneficiary_list')


class BeneficiaryUpdateView(UpdateView):
    model = Beneficiary
    form_class = BeneficiaryForm
    template_name = 'finance/beneficiary_form.html'
    success_url = reverse_lazy('finance:beneficiary_list')
    context_object_name = 'beneficiary'


class BeneficiaryDeleteView(DeleteView):
    model = Beneficiary
    template_name = 'finance/beneficiary_confirm_delete.html'
    success_url = reverse_lazy('finance:beneficiary_list')
    context_object_name = 'beneficiary'


class CategoryCreateView(CreateView):
    model = Category
    form_class = CategoryForm
    template_name = 'finance/category_form.html'
    success_url = reverse_lazy('finance:category_list')


class CategoryUpdateView(UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = 'finance/category_form.html'
    success_url = reverse_lazy('finance:category_list')
    context_object_name = 'category'


class CategoryDeleteView(DeleteView):
    model = Category
    template_name = 'finance/category_confirm_delete.html'
    success_url = reverse_lazy('finance:category_list')
    context_object_name = 'category'


class SubcategoryCreateView(CreateView):
    model = Subcategory
    form_class = SubcategoryForm
    template_name = 'finance/subcategory_form.html'

    def get_success_url(self):
        return reverse('finance:subcategory_list', kwargs={'category_pk': self.object.category_id})

    def form_valid(self, form):
        form.instance.category = get_object_or_404(Category, pk=self.kwargs['category_pk'])
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        kwargs.setdefault('category', get_object_or_404(Category, pk=self.kwargs['category_pk']))
        return super().get_context_data(**kwargs)


class SubcategoryUpdateView(UpdateView):
    model = Subcategory
    form_class = SubcategoryForm
    template_name = 'finance/subcategory_form.html'
    context_object_name = 'subcategory'

    def get_queryset(self):
        return super().get_queryset().filter(category_id=self.kwargs['category_pk'])

    def get_success_url(self):
        return reverse('finance:subcategory_list', kwargs={'category_pk': self.object.category_id})

    def get_context_data(self, **kwargs):
        kwargs.setdefault('category', self.object.category)
        return super().get_context_data(**kwargs)


class SubcategoryDeleteView(DeleteView):
    model = Subcategory
    template_name = 'finance/subcategory_confirm_delete.html'
    context_object_name = 'subcategory'

    def get_queryset(self):
        return super().get_queryset().filter(category_id=self.kwargs['category_pk'])

    def get_success_url(self):
        return reverse('finance:subcategory_list', kwargs={'category_pk': self.object.category_id})

    def get_context_data(self, **kwargs):
        kwargs.setdefault('category', self.object.category)
        return super().get_context_data(**kwargs)


def index(request):
    """Página inicial da aplicação finance"""
    return render(request, 'finance/index.html')


def conectividade_index(request):
    """Página índice do menu Conectividade"""
    return render(request, 'finance/conectividade_index.html')


def get_subcategory_default_transaction_type(request, subcategory_id):
    """Retorna o default_transaction_type de uma subcategoria (para JavaScript)"""
    subcategory = get_object_or_404(Subcategory, pk=subcategory_id)
    return JsonResponse({
        'default_transaction_type': subcategory.default_transaction_type
    })


# AJAX Views para criação rápida
def _quick_create_json(request, form_class, build_response):
    """Helper: cria um objeto via POST e retorna JSON. build_response(obj) retorna dict com success=True, id, name e opcionais."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    form = form_class(request.POST)
    if form.is_valid():
        obj = form.save()
        return JsonResponse({**build_response(obj), 'success': True})
    return JsonResponse({'success': False, 'errors': form.errors}, status=400)


def quick_create_account(request):
    """Cria uma conta rapidamente via AJAX"""
    return _quick_create_json(request, AccountForm, lambda o: {'id': o.id, 'name': o.name})


def quick_create_beneficiary(request):
    """Cria um beneficiário rapidamente via AJAX"""
    return _quick_create_json(request, BeneficiaryForm, lambda o: {'id': o.id, 'name': o.full_name})


def quick_create_subcategory(request):
    """Cria uma subcategoria rapidamente via AJAX"""
    return _quick_create_json(
        request, SubcategoryForm,
        lambda o: {'id': o.id, 'name': str(o), 'category_id': o.category.id}
    )


def quick_create_asset(request):
    """Cria um ativo rapidamente via AJAX"""
    return _quick_create_json(
        request, AssetForm,
        lambda o: {'id': o.id, 'name': f"{o.code} - {o.name}"}
    )


# Account Views
def account_list(request):
    """Lista de contas com filtros e paginação"""
    # Inicializar formulário de filtros
    filter_form = AccountFilterForm(request.GET)
    
    # Query base
    accounts = Account.objects.all()
    
    # Aplicar filtros
    if filter_form.is_valid():
        account_types = filter_form.cleaned_data.get('account_type')
        name_search = filter_form.cleaned_data.get('name_search')
        
        if account_types:
            accounts = accounts.filter(account_type__in=account_types)
        
        if name_search:
            accounts = accounts.filter(name__icontains=name_search)
    
    # Anotar saldo (1 query agregada) para ordenação e totais sem N queries
    accounts = accounts.annotate(
        balance_delta=Account.get_balance_delta_annotation()
    )
    
    # Ordenar - suporte para múltiplas colunas
    sort_fields_str = request.GET.get('sort', '')
    sort_orders_str = request.GET.get('order', 'desc')
    
    # Mapeamento de campos de ordenação
    sort_mapping = {
        'account_type': 'account_type',
        'name': 'name',
        'balance': None,  # Será tratado separadamente
    }
    
    # Processar múltiplos campos de ordenação (separados por vírgula)
    sort_fields = [f.strip() for f in sort_fields_str.split(',') if f.strip()] if sort_fields_str else []
    sort_orders = [o.strip() for o in sort_orders_str.split(',')] if sort_orders_str else []
    
    # Converter para lista para poder ordenar (necessário para ordenação por saldo)
    accounts_list = list(accounts)
    
    # Aplicar ordenação
    valid_sorts = []
    valid_orders = []
    
    # Se não houver ordenação especificada, usar ordenação padrão por nome
    if not sort_fields:
        sort_fields = ['name']
        sort_orders = ['asc']
    
    # Validar campos de ordenação
    for i, sort_field in enumerate(sort_fields):
        if sort_field in sort_mapping:
            sort_order = sort_orders[i] if i < len(sort_orders) else 'asc'
            if sort_order not in ['asc', 'desc']:
                sort_order = 'asc'
            
            valid_sorts.append(sort_field)
            valid_orders.append(sort_order)
    
    # Aplicar ordenações múltiplas (Python sort é estável, então aplicamos da menos para a mais significativa)
    # Ou seja, aplicamos na ordem inversa: última ordenação primeiro, primeira por último
    for i in range(len(valid_sorts) - 1, -1, -1):
        sort_field = valid_sorts[i]
        sort_order = valid_orders[i]
        reverse_order = (sort_order == 'desc')
        
        if sort_field == 'balance':
            # Ordenar por saldo (usa balance_delta anotado, sem nova query)
            accounts_list.sort(
                key=lambda a: a.get_balance_from_annotation(), reverse=reverse_order
            )
        elif sort_field == 'account_type':
            # Ordenar por tipo de conta
            accounts_list.sort(key=lambda a: a.account_type, reverse=reverse_order)
        elif sort_field == 'name':
            # Ordenar por nome
            accounts_list.sort(key=lambda a: a.name.lower(), reverse=reverse_order)
    
    # Paginação
    paginator = Paginator(accounts_list, ACCOUNTS_PER_PAGE)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Calcular total de saldos apenas para a página atual (usa anotação)
    total_balance = sum(
        account.get_balance_from_annotation() for account in page_obj
    )
    
    # Calcular datas padrão para o botão de extrato
    today = date.today()
    first_day_of_month = date(today.year, today.month, 1)
    
    # Criar dicionário com prioridade de cada campo ordenado
    sort_info = {}
    for idx, sort_field in enumerate(valid_sorts):
        sort_info[sort_field] = {
            'priority': idx + 1,
            'order': valid_orders[idx] if idx < len(valid_orders) else 'asc'
        }
    
    return render(request, 'finance/account_list.html', {
        'accounts': page_obj,
        'filter_form': filter_form,
        'page_obj': page_obj,
        'sort_info': sort_info,
        'default_start_date': first_day_of_month,
        'default_end_date': today,
        'total_balance': total_balance,
    })


account_create = AccountCreateView.as_view()
account_update = AccountUpdateView.as_view()
account_delete = AccountDeleteView.as_view()


# Beneficiary Views
def beneficiary_list(request):
    """Lista de beneficiários"""
    beneficiaries = Beneficiary.objects.all()
    return render(request, 'finance/beneficiary_list.html', {'beneficiaries': beneficiaries})


beneficiary_create = BeneficiaryCreateView.as_view()
beneficiary_update = BeneficiaryUpdateView.as_view()
beneficiary_delete = BeneficiaryDeleteView.as_view()


# Category Views
def category_list(request):
    """Lista de categorias"""
    # Uma query para categorias + prefetch de subcategorias; uma para contagem de mapeamentos
    categories = Category.objects.prefetch_related('subcategory_set').all()
    mapping_count = CashFlowItem.get_subcategory_mapping_count()
    
    for category in categories:
        subcategories = list(category.subcategory_set.all())
        category.subcategory_count = len(subcategories)
        category.mapped_count = 0
        category.not_mapped_count = 0
        category.duplicate_count = 0
        for subcategory in subcategories:
            count = mapping_count.get(subcategory.id, 0)
            if count == 0:
                category.not_mapped_count += 1
            elif count == 1:
                category.mapped_count += 1
            else:
                category.duplicate_count += 1
    
    return render(request, 'finance/category_list.html', {'categories': categories})


category_create = CategoryCreateView.as_view()
category_update = CategoryUpdateView.as_view()
category_delete = CategoryDeleteView.as_view()


# Subcategory Views
def subcategory_list(request, category_pk):
    """Lista de subcategorias de uma categoria"""
    category = get_object_or_404(Category, pk=category_pk)
    subcategories = Subcategory.objects.filter(category=category)
    # Uma única chamada para contagem de mapeamentos (evita N+1)
    mapping_count_dict = CashFlowItem.get_subcategory_mapping_count()
    for subcategory in subcategories:
        count = mapping_count_dict.get(subcategory.id, 0)
        subcategory.mapping_count = count
        subcategory.is_mapped = count > 0
        subcategory.has_duplicate = count > 1
    return render(request, 'finance/subcategory_list.html', {
        'category': category,
        'subcategories': subcategories
    })


subcategory_create = SubcategoryCreateView.as_view()
subcategory_update = SubcategoryUpdateView.as_view()
subcategory_delete = SubcategoryDeleteView.as_view()


def subcategory_move(request, category_pk, pk):
    """Exibir formulário para mover subcategoria"""
    category = get_object_or_404(Category, pk=category_pk)
    subcategory = get_object_or_404(Subcategory, pk=pk, category=category)
    
    # Contar registros que serão afetados
    transaction_count = Transaction.objects.filter(subcategory=subcategory).count()
    scheduler_count = Scheduler.objects.filter(subcategory=subcategory).count()
    budget_count = Budget.objects.filter(subcategory=subcategory).count()
    
    # Contar referências no CashFlowItem
    cash_flow_count = 0
    cash_flow_items = CashFlowItem.objects.filter(calculation_type='RULES')
    for item in cash_flow_items:
        if item.calculation_rules:
            for rule in item.calculation_rules:
                if rule.get('type') == 'subcategory' and rule.get('subcategory_id') == subcategory.id:
                    cash_flow_count += 1
                    break  # Contar apenas uma vez por item
    
    if request.method == 'POST':
        form = SubcategoryMoveForm(request.POST, source_subcategory=subcategory)
        if form.is_valid():
            # Executar a movimentação diretamente
            destination_subcategory = form.cleaned_data['destination_subcategory']
            
            try:
                with db_transaction.atomic():
                    # 1. Atualizar Transactions
                    transactions_updated = Transaction.objects.filter(
                        subcategory=subcategory
                    ).update(subcategory=destination_subcategory)
                    
                    # 2. Atualizar Schedulers
                    schedulers_updated = Scheduler.objects.filter(
                        subcategory=subcategory
                    ).update(subcategory=destination_subcategory)
                    
                    # 3. Atualizar Budgets (com tratamento de unique_together)
                    budgets_updated = 0
                    budgets_merged = 0
                    source_budgets = Budget.objects.filter(subcategory=subcategory)
                    
                    for budget in source_budgets:
                        # Verificar se já existe um budget na subcategoria destino com a mesma data
                        existing_budget = Budget.objects.filter(
                            subcategory=destination_subcategory,
                            budget_date=budget.budget_date
                        ).first()
                        
                        if existing_budget:
                            # Mesclar: somar os valores
                            existing_budget.amount += budget.amount
                            existing_budget.save()
                            budget.delete()
                            budgets_merged += 1
                        else:
                            # Mover o budget
                            budget.subcategory = destination_subcategory
                            budget.save()
                            budgets_updated += 1
                    
                    # 4. Atualizar CashFlowItem calculation_rules
                    cash_flow_items_updated = 0
                    cash_flow_rules_updated = 0
                    cash_flow_items = CashFlowItem.objects.filter(calculation_type='RULES')
                    
                    for item in cash_flow_items:
                        if item.calculation_rules:
                            updated = False
                            for rule in item.calculation_rules:
                                if rule.get('type') == 'subcategory' and rule.get('subcategory_id') == subcategory.id:
                                    rule['subcategory_id'] = destination_subcategory.id
                                    updated = True
                                    cash_flow_rules_updated += 1
                            
                            if updated:
                                item.save(update_fields=['calculation_rules'])
                                cash_flow_items_updated += 1
                    
                    # 5. Deletar a subcategoria origem após mover todos os registros
                    subcategory_name = str(subcategory)
                    subcategory.delete()
                    
                    messages.success(request, 
                        f'Movimentação concluída com sucesso! '
                        f'{transactions_updated} transações, {schedulers_updated} agendamentos, '
                        f'{budgets_updated + budgets_merged} orçamentos ({budgets_merged} mesclados), '
                        f'e {cash_flow_rules_updated} regras de fluxo de caixa atualizadas. '
                        f'A subcategoria "{subcategory_name}" foi deletada.')
                    
                    return redirect('finance:subcategory_list', category_pk=category_pk)
                    
            except Exception as e:
                messages.error(request, f'Erro ao mover subcategoria: {str(e)}')
    else:
        form = SubcategoryMoveForm(source_subcategory=subcategory)
    
    return render(request, 'finance/subcategory_move.html', {
        'form': form,
        'category': category,
        'subcategory': subcategory,
        'transaction_count': transaction_count,
        'scheduler_count': scheduler_count,
        'budget_count': budget_count,
        'cash_flow_count': cash_flow_count,
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
        accounts = filter_form.cleaned_data.get('account')
        beneficiaries = filter_form.cleaned_data.get('beneficiary')
        categories = filter_form.cleaned_data.get('category')
        subcategories = filter_form.cleaned_data.get('subcategory')
        date_start = filter_form.cleaned_data.get('date_start')
        date_end = filter_form.cleaned_data.get('date_end')
        
        if accounts:
            transactions = transactions.filter(account__in=accounts)
        
        if beneficiaries:
            transactions = transactions.filter(beneficiary__in=beneficiaries)
        
        if categories:
            transactions = transactions.filter(subcategory__category__in=categories)
        
        if subcategories:
            transactions = transactions.filter(subcategory__in=subcategories)
        
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
    
    # Ordenar - suporte para múltiplas colunas
    sort_fields_str = request.GET.get('sort', '')
    sort_orders_str = request.GET.get('order', 'desc')
    
    # Mapeamento de campos de ordenação
    sort_mapping = {
        'beneficiary': 'beneficiary__full_name',
        'account': 'account__name',
        'subcategory': 'subcategory__subcategory',
        'transaction_type': 'transaction_type',
        'value': 'value',
        'date': 'transaction_date',  # Para data, usamos transaction_date como principal
    }
    
    # Processar múltiplos campos de ordenação (separados por vírgula)
    sort_fields = [f.strip() for f in sort_fields_str.split(',') if f.strip()] if sort_fields_str else []
    sort_orders = [o.strip() for o in sort_orders_str.split(',')] if sort_orders_str else []
    
    # Validar e aplicar ordenações
    order_fields = []
    valid_sorts = []
    valid_orders = []
    
    for i, sort_field in enumerate(sort_fields):
        if sort_field in sort_mapping:
            sort_order = sort_orders[i] if i < len(sort_orders) else 'desc'
            if sort_order not in ['asc', 'desc']:
                sort_order = 'desc'
            
            # Para data, precisamos de uma ordenação especial
            if sort_field == 'date':
                if sort_order == 'asc':
                    order_fields.extend(['transaction_date', 'due_date', 'created_at'])
                else:
                    order_fields.extend(['-transaction_date', '-due_date', '-created_at'])
            else:
                order_prefix = '' if sort_order == 'asc' else '-'
                order_fields.append(f"{order_prefix}{sort_mapping[sort_field]}")
            
            valid_sorts.append(sort_field)
            valid_orders.append(sort_order)
    
    if order_fields:
        # Adicionar ordenação padrão por data como fallback
        if 'date' not in valid_sorts:
            order_fields.extend(['-transaction_date', '-due_date', '-created_at'])
        transactions = transactions.order_by(*order_fields)
    else:
        # Ordenação padrão
        transactions = transactions.order_by('-transaction_date', '-due_date', '-created_at')
    
    # Paginação
    paginator = Paginator(transactions, TRANSACTIONS_PER_PAGE)
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
                if transaction.transaction_type == TRANSACTION_TYPE_DB:
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
            if transaction.transaction_type == TRANSACTION_TYPE_CR:
                total_value += transaction.value
            elif transaction.transaction_type == TRANSACTION_TYPE_DB:
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
    subtotal = Decimal('0')
    
    # Somar transações simples
    for transaction in single_transactions:
        if transaction.transaction_type == TRANSACTION_TYPE_CR:
            subtotal += transaction.value
        elif transaction.transaction_type == TRANSACTION_TYPE_DB:
            subtotal -= transaction.value
    
    # Somar grupos múltiplos
    for group_data in multiple_groups_list:
        subtotal += Decimal(str(group_data['total_value']))
    
    # Passar informações de ordenação para o template
    # Criar dicionário com prioridade de cada campo ordenado
    sort_info = {}
    for idx, sort_field in enumerate(valid_sorts):
        sort_info[sort_field] = {
            'priority': idx + 1,
            'order': valid_orders[idx] if idx < len(valid_orders) else 'desc'
        }
    
    return render(request, 'finance/transaction_list.html', {
        'transactions': single_transactions,
        'multiple_groups': multiple_groups_list,
        'filter_form': filter_form,
        'page_obj': page_obj,
        'subtotal': subtotal,
        'sort_info': sort_info,  # Dicionário com informações de ordenação por campo
    })


def transaction_create(request):
    """Criar nova transação"""
    categories = Category.objects.all().order_by('category')
    
    def calculate_budget_info(subcategory, transaction_value, transaction_type, transaction_date):
        """Calcula informações de orçamento e gastos"""
        if not subcategory:
            return {
                'subcategory': {
                    'accumulated': {'spent_before': Decimal('0'), 'spent_after': Decimal('0'), 'budgeted': Decimal('0')},
                    'year': {'spent_before': Decimal('0'), 'spent_after': Decimal('0'), 'projection': Decimal('0'), 'budgeted': Decimal('0')}
                },
                'category': {
                    'accumulated': {'spent_before': Decimal('0'), 'spent_after': Decimal('0'), 'budgeted': Decimal('0')},
                    'year': {'spent_before': Decimal('0'), 'spent_after': Decimal('0'), 'projection': Decimal('0'), 'budgeted': Decimal('0')}
                }
            }
        
        category = subcategory.category
        transaction_value = Decimal(str(transaction_value)) if transaction_value else Decimal('0')
        
        # Determinar data da transação
        if transaction_date:
            trans_date = transaction_date
        else:
            trans_date = date.today()
        
        # Calcular períodos
        # Acumulado: desde o início do ano até o último dia do mês da transação
        year_start = date(trans_date.year, 1, 1)
        if trans_date.month == 12:
            accumulated_end = date(trans_date.year, 12, 31)
        else:
            accumulated_end = date(trans_date.year, trans_date.month + 1, 1) - timedelta(days=1)
        
        year_end = date(trans_date.year, 12, 31)
        
        # Calcular gastos acumulados antes do registro (desde início do ano até o mês da transação)
        subcategory_spent_accumulated_before = calculate_spent_by_subcategory(subcategory, year_start, accumulated_end)
        subcategory_spent_year_before = calculate_spent_by_subcategory(subcategory, year_start, year_end)
        category_spent_accumulated_before = calculate_spent_by_category(category, year_start, accumulated_end)
        category_spent_year_before = calculate_spent_by_category(category, year_start, year_end)
        
        # Calcular gastos depois do registro (adicionar valor da transação)
        transaction_impact = transaction_value if transaction_type == TRANSACTION_TYPE_CR else -transaction_value
        subcategory_spent_accumulated_after = subcategory_spent_accumulated_before + transaction_impact
        subcategory_spent_year_after = subcategory_spent_year_before + transaction_impact
        category_spent_accumulated_after = category_spent_accumulated_before + transaction_impact
        category_spent_year_after = category_spent_year_before + transaction_impact
        
        # Calcular orçamentos acumulados (desde início do ano até o mês da transação)
        subcategory_budget_accumulated = calculate_budget_accumulated_by_subcategory(subcategory, trans_date.year, trans_date.month)
        subcategory_budget_year = calculate_budget_by_subcategory_year(subcategory, trans_date.year)
        category_budget_accumulated = calculate_budget_accumulated_by_category(category, trans_date.year, trans_date.month)
        category_budget_year = calculate_budget_by_category_year(category, trans_date.year)
        
        # Calcular projeção anual (média mensal × 12)
        current_month = trans_date.month
        if current_month > 0:
            subcategory_projection = (subcategory_spent_accumulated_after / current_month) * 12
            category_projection = (category_spent_accumulated_after / current_month) * 12
        else:
            subcategory_projection = Decimal('0')
            category_projection = Decimal('0')
        
        return {
            'subcategory': {
                'accumulated': {
                    'spent_before': subcategory_spent_accumulated_before,
                    'spent_after': subcategory_spent_accumulated_after,
                    'budgeted': subcategory_budget_accumulated
                },
                'year': {
                    'spent_before': subcategory_spent_year_before,
                    'spent_after': subcategory_spent_year_after,
                    'projection': subcategory_projection,
                    'budgeted': subcategory_budget_year
                }
            },
            'category': {
                'accumulated': {
                    'spent_before': category_spent_accumulated_before,
                    'spent_after': category_spent_accumulated_after,
                    'budgeted': category_budget_accumulated
                },
                'year': {
                    'spent_before': category_spent_year_before,
                    'spent_after': category_spent_year_after,
                    'projection': category_projection,
                    'budgeted': category_budget_year
                }
            }
        }
    
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
                        transaction_type=TRANSACTION_TYPE_DB,
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
                        transaction_type=TRANSACTION_TYPE_CR,
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
                transaction = form.save(commit=False)
                # Garantir que asset_transaction nunca seja definido manualmente
                transaction.asset_transaction = None
                transaction.save()
                messages.success(request, 'Transação criada com sucesso!')
            
            return redirect('finance:transaction_list')
        else:
            # Formulário inválido - mostrar erros
            # Calcular budget_info mesmo com formulário inválido para mostrar informações
            subcategory = form.cleaned_data.get('subcategory') if form.cleaned_data else None
            value = form.cleaned_data.get('value') if form.cleaned_data else None
            transaction_type = form.cleaned_data.get('transaction_type') if form.cleaned_data else None
            transaction_date = form.cleaned_data.get('transaction_date') if form.cleaned_data else None
            
            budget_info = calculate_budget_info(subcategory, value, transaction_type, transaction_date) if subcategory else None
            return render(request, 'finance/transaction_form.html', {
                'form': form, 
                'categories': categories,
                'budget_info': budget_info
            })
    else:
        # Pré-preencher data de transação com data de hoje
        form = TransactionForm(initial={'transaction_date': date.today()})
        # Calcular budget_info inicial (vazio)
        budget_info = calculate_budget_info(None, None, None, None)
    return render(request, 'finance/transaction_form.html', {
        'form': form, 
        'categories': categories,
        'budget_info': budget_info
    })


def transaction_update(request, pk):
    """Editar transação existente"""
    transaction = get_object_or_404(Transaction, pk=pk)
    
    # Bloquear edição de transações oriundas de transações de ativos
    if transaction.asset_transaction:
        messages.error(request, 'Esta transação foi gerada automaticamente a partir de uma transação de ativo. Para editá-la, edite a transação de ativo correspondente.')
        return redirect('finance:transaction_list')
    
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
            is_transfer_in_form = form.cleaned_data.get('is_transfer', False)
            
            # Detectar conversão: verificar se o estado mudou
            is_converting_to_transfer = not transaction.is_transfer and is_transfer_in_form
            is_converting_to_normal = transaction.is_transfer and not is_transfer_in_form
            
            if is_converting_to_transfer:
                # Converter transação normal para transferência
                source_account = form.cleaned_data['source_account']
                destination_account = form.cleaned_data['destination_account']
                value = form.cleaned_data['value']
                due_date = form.cleaned_data.get('due_date')
                transaction_date = form.cleaned_data.get('transaction_date')
                purchase_date = form.cleaned_data.get('purchase_date')
                notes = form.cleaned_data.get('notes', '')
                
                # Gerar UUID para vincular as duas transações
                transfer_group_id = uuid.uuid4()
                
                with db_transaction.atomic():
                    # Converter a transação existente em transação de débito (conta origem)
                    transaction.account = source_account
                    transaction.beneficiary = None
                    transaction.subcategory = None
                    transaction.transaction_type = TRANSACTION_TYPE_DB
                    transaction.value = value
                    transaction.due_date = due_date
                    transaction.transaction_date = transaction_date
                    transaction.purchase_date = purchase_date
                    transaction.notes = notes
                    transaction.transfer_group_id = transfer_group_id
                    transaction.is_transfer = True
                    transaction.save()
                    
                    # Criar transação de crédito (conta destino)
                    credit_transaction = Transaction.objects.create(
                        account=destination_account,
                        beneficiary=None,
                        subcategory=None,
                        transaction_type=TRANSACTION_TYPE_CR,
                        value=value,
                        due_date=due_date,
                        transaction_date=transaction_date,
                        purchase_date=purchase_date,
                        notes=notes,
                        transfer_group_id=transfer_group_id,
                        is_transfer=True
                    )
                
                messages.success(request, 'Transação convertida em transferência com sucesso!')
                # Verificar se há parâmetro 'next' para redirecionar de volta ao extrato (GET ou POST)
                next_url = request.POST.get('next') or request.GET.get('next')
                if next_url:
                    return redirect(next_url)
                return redirect('finance:transaction_list')
            elif is_converting_to_normal:
                # Converter transferência para transação normal
                transfer_pair = transaction.get_transfer_pair()
                
                # Obter dados do formulário para a nova transação normal
                account = form.cleaned_data['account']
                beneficiary = form.cleaned_data['beneficiary']
                subcategory = form.cleaned_data['subcategory']
                transaction_type = form.cleaned_data['transaction_type']
                value = form.cleaned_data['value']
                due_date = form.cleaned_data.get('due_date')
                transaction_date = form.cleaned_data.get('transaction_date')
                purchase_date = form.cleaned_data.get('purchase_date')
                notes = form.cleaned_data.get('notes', '')
                
                with db_transaction.atomic():
                    # Deletar ambas as transações da transferência
                    if transfer_pair:
                        transfer_pair.delete()
                    transaction.delete()
                    
                    # Criar nova transação normal
                    new_transaction = Transaction.objects.create(
                        account=account,
                        beneficiary=beneficiary,
                        subcategory=subcategory,
                        transaction_type=transaction_type,
                        value=value,
                        due_date=due_date,
                        transaction_date=transaction_date,
                        purchase_date=purchase_date,
                        notes=notes,
                        is_transfer=False,
                        transfer_group_id=None
                    )
                
                messages.success(request, 'Transferência convertida em transação normal com sucesso!')
                # Verificar se há parâmetro 'next' para redirecionar de volta ao extrato (GET ou POST)
                next_url = request.POST.get('next') or request.GET.get('next')
                if next_url:
                    return redirect(next_url)
                return redirect('finance:transaction_list')
            elif transaction.is_transfer:
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
                        if transaction.transaction_type == TRANSACTION_TYPE_DB:
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
                    # Verificar se há parâmetro 'next' para redirecionar de volta ao extrato (GET ou POST)
                    next_url = request.POST.get('next') or request.GET.get('next')
                    if next_url:
                        return redirect(next_url)
                    return redirect('finance:transaction_list')
                else:
                    messages.error(request, 'Transação vinculada não encontrada.')
            else:
                # Atualizar transação normal
                transaction = form.save(commit=False)
                # Garantir que asset_transaction nunca seja alterado manualmente
                # (preservar o valor original se existir, mas não permitir criar novo)
                original_asset_transaction = transaction.asset_transaction
                transaction.asset_transaction = original_asset_transaction  # Manter o valor original
                transaction.save()
                messages.success(request, 'Transação atualizada com sucesso!')
            
            # Verificar se há parâmetro 'next' para redirecionar de volta ao extrato (GET ou POST)
            next_url = request.POST.get('next') or request.GET.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('finance:transaction_list')
        else:
            # Formulário inválido - mostrar erros
            messages.error(request, 'Por favor, corrija os erros abaixo.')
    else:
        # Se for transferência, criar formulário sem instance para evitar conflito com campo account
        if transaction.is_transfer:
            transfer_pair = transaction.get_transfer_pair()
            if transfer_pair:
                if transaction.transaction_type == TRANSACTION_TYPE_DB:
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
    
    categories = Category.objects.all().order_by('category')
    next_url = request.GET.get('next', '')
    return render(request, 'finance/transaction_form.html', {'form': form, 'transaction': transaction, 'categories': categories, 'next_url': next_url})


def transaction_delete(request, pk):
    """Deletar transação"""
    transaction = get_object_or_404(Transaction, pk=pk)
    
    # Bloquear deleção de transações oriundas de transações de ativos
    if transaction.asset_transaction:
        messages.error(request, 'Esta transação foi gerada automaticamente a partir de uma transação de ativo. Para deletá-la, delete a transação de ativo correspondente.')
        return redirect('finance:transaction_list')
    
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
    """Lista de agendamentos com filtros e paginação"""
    # Inicializar formulário de filtros
    filter_form = SchedulerFilterForm(request.GET)
    
    # Query base
    schedulers = Scheduler.objects.all().select_related('account', 'beneficiary', 'subcategory', 'destination_account')
    
    # Aplicar filtros (múltipla escolha)
    if filter_form.is_valid():
        accounts = filter_form.cleaned_data.get('account')
        beneficiaries = filter_form.cleaned_data.get('beneficiary')
        categories = filter_form.cleaned_data.get('category')
        subcategories = filter_form.cleaned_data.get('subcategory')
        statuses = filter_form.cleaned_data.get('status')
        date_start = filter_form.cleaned_data.get('date_start')
        date_end = filter_form.cleaned_data.get('date_end')
        
        if accounts:
            schedulers = schedulers.filter(account__in=accounts)
        if beneficiaries:
            schedulers = schedulers.filter(beneficiary__in=beneficiaries)
        if categories:
            schedulers = schedulers.filter(subcategory__category__in=categories)
        if subcategories:
            schedulers = schedulers.filter(subcategory__in=subcategories)
        if statuses:
            schedulers = schedulers.filter(status__in=statuses)
        if date_start or date_end:
            date_filter = Q()
            if date_start and date_end:
                date_filter = Q(due_date__gte=date_start) & Q(due_date__lte=date_end)
            elif date_start:
                date_filter = Q(due_date__gte=date_start)
            elif date_end:
                date_filter = Q(due_date__lte=date_end)
            schedulers = schedulers.filter(date_filter)
    
    # Ordenação múltipla (sort e order na query string)
    sort_fields_str = request.GET.get('sort', '')
    sort_orders_str = request.GET.get('order', 'asc')
    sort_mapping = {
        'beneficiary': 'beneficiary__full_name',
        'account': 'account__name',
        'transaction_type': 'transaction_type',
        'value': 'value',
        'due_date': 'due_date',
        'recurrence_type': 'recurrence_type',
        'status': 'status',
        'remaining_installments': 'remaining_installments',
    }
    sort_fields = [f.strip() for f in sort_fields_str.split(',') if f.strip()] if sort_fields_str else []
    sort_orders = [o.strip() for o in sort_orders_str.split(',')] if sort_orders_str else []
    order_fields = []
    valid_sorts = []
    valid_orders = []
    for i, sort_field in enumerate(sort_fields):
        if sort_field in sort_mapping:
            sort_order = sort_orders[i] if i < len(sort_orders) else 'asc'
            if sort_order not in ('asc', 'desc'):
                sort_order = 'asc'
            prefix = '' if sort_order == 'asc' else '-'
            order_fields.append(f"{prefix}{sort_mapping[sort_field]}")
            valid_sorts.append(sort_field)
            valid_orders.append(sort_order)
    if order_fields:
        if 'due_date' not in valid_sorts:
            order_fields.extend(['due_date', 'created_at'])
        schedulers = schedulers.order_by(*order_fields)
    else:
        schedulers = schedulers.order_by('due_date', 'created_at')
    
    # sort_info para o template (cabeçalhos ordenáveis)
    sort_info = {}
    for idx, sort_field in enumerate(valid_sorts):
        sort_info[sort_field] = {
            'priority': idx + 1,
            'order': valid_orders[idx] if idx < len(valid_orders) else 'asc',
        }
    
    # Paginação
    paginator = Paginator(schedulers, SCHEDULERS_PER_PAGE)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Agrupar agendamentos múltiplos
    multiple_groups = {}
    single_schedulers = []
    
    for scheduler in page_obj:
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
            if scheduler.transaction_type == TRANSACTION_TYPE_CR:
                total_value += scheduler.value
            elif scheduler.transaction_type == TRANSACTION_TYPE_DB:
                total_value -= scheduler.value
        group_data['total_value'] = total_value
        group_data['count'] = len(group_data['schedulers'])
        # Ordenar por ID para manter ordem
        group_data['schedulers'].sort(key=lambda x: x.id)
    
    # Ordenar grupos múltiplos por próxima data crescente
    multiple_groups_list = list(multiple_groups.values())
    multiple_groups_list.sort(
        key=lambda x: (
            x['representative'].due_date or 
            x['representative'].created_at or 
            date.min
        ),
        reverse=False
    )
    
    # Lista única ordenada por próxima data (crescente): intercala grupos e agendamentos simples
    def _due_sort_key(obj):
        if obj['type'] == 'group':
            rep = obj['group']['representative']
            return (rep.due_date or rep.created_at or date.min, 0)
        return (obj['scheduler'].due_date or obj['scheduler'].created_at or date.min, 1)
    scheduler_rows = []
    for g in multiple_groups_list:
        scheduler_rows.append({'type': 'group', 'group': g})
    for s in single_schedulers:
        scheduler_rows.append({'type': 'single', 'scheduler': s})
    scheduler_rows.sort(key=_due_sort_key)
    
    # Calcular subtotal da página
    subtotal = Decimal('0')
    for scheduler in single_schedulers:
        if scheduler.transaction_type == TRANSACTION_TYPE_CR:
            subtotal += scheduler.value
        elif scheduler.transaction_type == TRANSACTION_TYPE_DB:
            subtotal -= scheduler.value
    for group_data in multiple_groups_list:
        subtotal += Decimal(str(group_data['total_value']))
    
    # Query string para paginação preservando múltiplos valores (filtros multi-select)
    pagination_query = urlencode(
        [(k, v) for k in request.GET for v in request.GET.getlist(k) if k != 'page']
    )
    return render(request, 'finance/scheduler_list.html', {
        'scheduler_rows': scheduler_rows,
        'filter_form': filter_form,
        'page_obj': page_obj,
        'subtotal': subtotal,
        'sort_info': sort_info,
        'pagination_query': pagination_query,
    })


def scheduler_create(request):
    """Criar novo agendamento"""
    categories = Category.objects.all().order_by('category')
    if request.method == 'POST':
        form = SchedulerForm(request.POST)
        if form.is_valid():
            scheduler = form.save(commit=False)
            # Se não for recorrente (toggle desligado), definir como 'NONE'
            is_recurring = request.POST.get('is_recurring') == 'on'
            if not is_recurring:
                scheduler.recurrence_type = 'NONE'
                scheduler.recurrence_interval = 1
                scheduler.termination_type = 'INFINITE'
                scheduler.remaining_installments = None
                scheduler.final_date = None
            # Garantir que original_due_date seja definido
            if scheduler.due_date and not scheduler.original_due_date:
                scheduler.original_due_date = scheduler.due_date
            scheduler.save()
            return redirect('finance:scheduler_list')
        else:
            return render(request, 'finance/scheduler_form.html', {'form': form, 'categories': categories})
    else:
        form = SchedulerForm()
    return render(request, 'finance/scheduler_form.html', {'form': form, 'categories': categories})


def scheduler_update(request, pk):
    """Editar agendamento existente"""
    scheduler = get_object_or_404(Scheduler, pk=pk)
    categories = Category.objects.all().order_by('category')
    if request.method == 'POST':
        form = SchedulerForm(request.POST, instance=scheduler)
        if form.is_valid():
            scheduler = form.save(commit=False)
            # Se não for recorrente (toggle desligado), definir como 'NONE'
            is_recurring = request.POST.get('is_recurring') == 'on'
            if not is_recurring:
                scheduler.recurrence_type = 'NONE'
                scheduler.recurrence_interval = 1
                scheduler.termination_type = 'INFINITE'
                scheduler.remaining_installments = None
                scheduler.final_date = None
            # Atualizar original_due_date se due_date mudou e original_due_date não está definido
            if scheduler.due_date and not scheduler.original_due_date:
                scheduler.original_due_date = scheduler.due_date
            scheduler.save()
            return redirect('finance:scheduler_list')
        else:
            return render(request, 'finance/scheduler_form.html', {'form': form, 'scheduler': scheduler, 'categories': categories})
    else:
        form = SchedulerForm(instance=scheduler)
    return render(request, 'finance/scheduler_form.html', {'form': form, 'scheduler': scheduler, 'categories': categories})


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
    
    def calculate_budget_info(subcategory, transaction_value, transaction_type, transaction_date):
        """Calcula informações de orçamento e gastos"""
        if not subcategory:
            return {
                'subcategory': {
                    'accumulated': {'spent_before': Decimal('0'), 'spent_after': Decimal('0'), 'budgeted': Decimal('0')},
                    'year': {'spent_before': Decimal('0'), 'spent_after': Decimal('0'), 'projection': Decimal('0'), 'budgeted': Decimal('0')}
                },
                'category': {
                    'accumulated': {'spent_before': Decimal('0'), 'spent_after': Decimal('0'), 'budgeted': Decimal('0')},
                    'year': {'spent_before': Decimal('0'), 'spent_after': Decimal('0'), 'projection': Decimal('0'), 'budgeted': Decimal('0')}
                }
            }
        
        category = subcategory.category
        transaction_value = Decimal(str(transaction_value)) if transaction_value else Decimal('0')
        
        # Determinar data da transação
        if transaction_date:
            trans_date = transaction_date
        else:
            trans_date = date.today()
        
        # Calcular períodos
        # Acumulado: desde o início do ano até o último dia do mês da transação
        year_start = date(trans_date.year, 1, 1)
        if trans_date.month == 12:
            accumulated_end = date(trans_date.year, 12, 31)
        else:
            accumulated_end = date(trans_date.year, trans_date.month + 1, 1) - timedelta(days=1)
        
        year_end = date(trans_date.year, 12, 31)
        
        # Calcular gastos acumulados antes do registro (desde início do ano até o mês da transação)
        subcategory_spent_accumulated_before = calculate_spent_by_subcategory(subcategory, year_start, accumulated_end)
        subcategory_spent_year_before = calculate_spent_by_subcategory(subcategory, year_start, year_end)
        category_spent_accumulated_before = calculate_spent_by_category(category, year_start, accumulated_end)
        category_spent_year_before = calculate_spent_by_category(category, year_start, year_end)
        
        # Calcular gastos depois do registro (adicionar valor da transação)
        transaction_impact = transaction_value if transaction_type == TRANSACTION_TYPE_CR else -transaction_value
        subcategory_spent_accumulated_after = subcategory_spent_accumulated_before + transaction_impact
        subcategory_spent_year_after = subcategory_spent_year_before + transaction_impact
        category_spent_accumulated_after = category_spent_accumulated_before + transaction_impact
        category_spent_year_after = category_spent_year_before + transaction_impact
        
        # Calcular orçamentos acumulados (desde início do ano até o mês da transação)
        subcategory_budget_accumulated = calculate_budget_accumulated_by_subcategory(subcategory, trans_date.year, trans_date.month)
        subcategory_budget_year = calculate_budget_by_subcategory_year(subcategory, trans_date.year)
        category_budget_accumulated = calculate_budget_accumulated_by_category(category, trans_date.year, trans_date.month)
        category_budget_year = calculate_budget_by_category_year(category, trans_date.year)
        
        # Calcular projeção anual (média mensal × 12)
        current_month = trans_date.month
        if current_month > 0:
            subcategory_projection = (subcategory_spent_accumulated_after / current_month) * 12
            category_projection = (category_spent_accumulated_after / current_month) * 12
        else:
            subcategory_projection = Decimal('0')
            category_projection = Decimal('0')
        
        return {
            'subcategory': {
                'accumulated': {
                    'spent_before': subcategory_spent_accumulated_before,
                    'spent_after': subcategory_spent_accumulated_after,
                    'budgeted': subcategory_budget_accumulated
                },
                'year': {
                    'spent_before': subcategory_spent_year_before,
                    'spent_after': subcategory_spent_year_after,
                    'projection': subcategory_projection,
                    'budgeted': subcategory_budget_year
                }
            },
            'category': {
                'accumulated': {
                    'spent_before': category_spent_accumulated_before,
                    'spent_after': category_spent_accumulated_after,
                    'budgeted': category_budget_accumulated
                },
                'year': {
                    'spent_before': category_spent_year_before,
                    'spent_after': category_spent_year_after,
                    'projection': category_projection,
                    'budgeted': category_budget_year
                }
            }
        }
    
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
        
        # Se o formulário não for válido, mostrar erros
        next_due_date = scheduler.get_next_due_date_after_registration()
        categories = Category.objects.all().order_by('category')
        
        # Calcular informações de orçamento
        subcategory = form.cleaned_data.get('subcategory') if form.is_valid() else form.initial.get('subcategory', scheduler.subcategory)
        transaction_value = form.cleaned_data.get('value') if form.is_valid() else form.initial.get('value', scheduler.value)
        transaction_type = form.cleaned_data.get('transaction_type') if form.is_valid() else form.initial.get('transaction_type', scheduler.transaction_type)
        transaction_date = form.cleaned_data.get('transaction_date') if form.is_valid() else form.initial.get('transaction_date', scheduler.due_date or date.today())
        
        budget_info = calculate_budget_info(subcategory, transaction_value, transaction_type, transaction_date)
        
        return render(request, 'finance/scheduler_register.html', {
            'scheduler': scheduler,
            'form': form,
            'next_due_date': next_due_date,
            'categories': categories,
            'budget_info': budget_info
        })
    else:
        # Criar formulário com valores iniciais do agendamento
        notes_initial = scheduler.notes or ''
        # Pré-preencher anotações com "Parcelas restantes: XXX/XXX" quando for recorrente
        installment_info = scheduler.get_installment_info()
        if installment_info:
            parcelas_text = f"Parcelas restantes: {installment_info['current']:03d}/{installment_info['total']:03d}"
            notes_initial = f"{notes_initial.strip()}\n{parcelas_text}".strip() if notes_initial.strip() else parcelas_text
        initial_data = {
            'account': scheduler.account,
            'beneficiary': scheduler.beneficiary,
            'subcategory': scheduler.subcategory,
            'transaction_type': scheduler.transaction_type,
            'value': scheduler.value,
            'due_date': scheduler.due_date,
            'transaction_date': scheduler.due_date,  # Padrão é due_date
            'purchase_date': scheduler.purchase_date,
            'notes': notes_initial,
        }
        form = TransactionForm(initial=initial_data)
        next_due_date = scheduler.get_next_due_date_after_registration()
        categories = Category.objects.all().order_by('category')
        
        # Calcular informações de orçamento
        budget_info = calculate_budget_info(
            scheduler.subcategory,
            scheduler.value,
            scheduler.transaction_type,
            scheduler.due_date or date.today()
        )
        
        return render(request, 'finance/scheduler_register.html', {
            'scheduler': scheduler,
            'form': form,
            'next_due_date': next_due_date,
            'categories': categories,
            'budget_info': budget_info
        })


def _calculate_multiple_budget_info(items_data, transaction_date):
    """
    Calcula informações de orçamento e gastos para múltiplas subcategorias.
    
    items_data: lista de dicionários com 'subcategory', 'value', 'transaction_type', 'is_transfer'
    transaction_date: data da transação
    
    Retorna estrutura com:
    - by_category: agregado por categoria
    - by_subcategory: detalhado por subcategoria
    """
    if not items_data:
        return {
            'by_category': {},
            'by_subcategory': []
        }
    
    if not transaction_date:
        transaction_date = date.today()
    
    # Calcular períodos
    year_start = date(transaction_date.year, 1, 1)
    if transaction_date.month == 12:
        accumulated_end = date(transaction_date.year, 12, 31)
    else:
        accumulated_end = date(transaction_date.year, transaction_date.month + 1, 1) - timedelta(days=1)
    
    year_end = date(transaction_date.year, 12, 31)
    
    # Agrupar por categoria e subcategoria
    category_totals = defaultdict(lambda: {
        'accumulated': {'spent_before': Decimal('0'), 'spent_after': Decimal('0'), 'budgeted': Decimal('0')},
        'year': {'spent_before': Decimal('0'), 'spent_after': Decimal('0'), 'budgeted': Decimal('0')}
    })
    
    subcategory_details = {}
    subcategory_items = defaultdict(list)  # Agrupar itens por subcategoria
    
    # Agrupar itens por subcategoria primeiro
    for item in items_data:
        if item.get('is_transfer') or not item.get('subcategory'):
            continue  # Ignorar transferências
        
        subcategory = item['subcategory']
        subcategory_items[subcategory.id].append(item)
    
    # Processar cada subcategoria única
    for subcategory_id, items_list in subcategory_items.items():
        subcategory = items_list[0]['subcategory']
        category = subcategory.category
        
        # Calcular gastos antes do registro (uma vez por subcategoria)
        subcategory_spent_accumulated_before = calculate_spent_by_subcategory(subcategory, year_start, accumulated_end)
        subcategory_spent_year_before = calculate_spent_by_subcategory(subcategory, year_start, year_end)
        
        # Calcular orçamentos (uma vez por subcategoria)
        subcategory_budget_accumulated = calculate_budget_accumulated_by_subcategory(subcategory, transaction_date.year, transaction_date.month)
        subcategory_budget_year = calculate_budget_by_subcategory_year(subcategory, transaction_date.year)
        
        # Somar impactos de todos os itens desta subcategoria
        total_transaction_impact = Decimal('0')
        total_value = Decimal('0')
        
        for item in items_list:
            value = Decimal(str(item.get('value', 0)))
            transaction_type = item.get('transaction_type', TRANSACTION_TYPE_DB)
            transaction_impact = value if transaction_type == TRANSACTION_TYPE_CR else -value
            total_transaction_impact += transaction_impact
            total_value += value
        
        # Calcular gastos depois do registro
        subcategory_spent_accumulated_after = subcategory_spent_accumulated_before + total_transaction_impact
        subcategory_spent_year_after = subcategory_spent_year_before + total_transaction_impact
        
        # Calcular projeção anual (média mensal × 12)
        current_month = transaction_date.month
        if current_month > 0:
            subcategory_projection = (subcategory_spent_accumulated_after / current_month) * 12
        else:
            subcategory_projection = Decimal('0')
        
        # Adicionar aos totais da categoria
        category_totals[category.id]['accumulated']['spent_before'] += subcategory_spent_accumulated_before
        category_totals[category.id]['accumulated']['spent_after'] += subcategory_spent_accumulated_after
        category_totals[category.id]['accumulated']['budgeted'] += subcategory_budget_accumulated
        category_totals[category.id]['year']['spent_before'] += subcategory_spent_year_before
        category_totals[category.id]['year']['spent_after'] += subcategory_spent_year_after
        category_totals[category.id]['year']['budgeted'] += subcategory_budget_year
        
        # Detalhes por subcategoria
        subcategory_details[subcategory_id] = {
            'subcategory': subcategory,
            'category': category,
            'accumulated': {
                'spent_before': subcategory_spent_accumulated_before,
                'spent_after': subcategory_spent_accumulated_after,
                'budgeted': subcategory_budget_accumulated
            },
            'year': {
                'spent_before': subcategory_spent_year_before,
                'spent_after': subcategory_spent_year_after,
                'projection': subcategory_projection,
                'budgeted': subcategory_budget_year
            },
            'items_count': len(items_list),
            'total_value': total_value
        }
    
    # Converter para estrutura final
    by_category = {}
    current_month = transaction_date.month
    for cat_id, totals in category_totals.items():
        category = Category.objects.get(pk=cat_id)
        # Calcular projeção da categoria (média mensal × 12)
        if current_month > 0:
            category_projection = (totals['accumulated']['spent_after'] / current_month) * 12
        else:
            category_projection = Decimal('0')
        totals['year']['projection'] = category_projection
        
        by_category[cat_id] = {
            'category': category,
            'accumulated': totals['accumulated'],
            'year': totals['year']
        }
    
    by_subcategory = list(subcategory_details.values())
    
    return {
        'by_category': by_category,
        'by_subcategory': by_subcategory
    }


def get_budget_info(request):
    """Endpoint AJAX para obter informações de orçamento e gastos"""
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    subcategory_id = request.GET.get('subcategory_id')
    value = request.GET.get('value', '0')
    transaction_type = request.GET.get('transaction_type', TRANSACTION_TYPE_DB)
    transaction_date_str = request.GET.get('transaction_date')
    
    try:
        value = Decimal(str(value))
    except (ValueError, InvalidOperation):
        value = Decimal('0')
    
    if transaction_date_str:
        try:
            transaction_date = datetime.strptime(transaction_date_str, '%Y-%m-%d').date()
        except ValueError:
            transaction_date = date.today()
    else:
        transaction_date = date.today()
    
    if not subcategory_id:
        return JsonResponse({
            'subcategory': {
                'accumulated': {'spent_before': '0.00', 'spent_after': '0.00', 'budgeted': '0.00'},
                'year': {'spent_before': '0.00', 'spent_after': '0.00', 'projection': '0.00', 'budgeted': '0.00'}
            },
            'category': {
                'accumulated': {'spent_before': '0.00', 'spent_after': '0.00', 'budgeted': '0.00'},
                'year': {'spent_before': '0.00', 'spent_after': '0.00', 'projection': '0.00', 'budgeted': '0.00'}
            }
        })
    
    try:
        subcategory = Subcategory.objects.get(pk=subcategory_id)
    except Subcategory.DoesNotExist:
        return JsonResponse({'error': 'Subcategoria não encontrada'}, status=404)
    
    category = subcategory.category
    
    # Calcular períodos
    # Acumulado: desde o início do ano até o último dia do mês da transação
    year_start = date(transaction_date.year, 1, 1)
    if transaction_date.month == 12:
        accumulated_end = date(transaction_date.year, 12, 31)
    else:
        accumulated_end = date(transaction_date.year, transaction_date.month + 1, 1) - timedelta(days=1)
    
    year_end = date(transaction_date.year, 12, 31)
    
    # Calcular gastos acumulados antes do registro (desde início do ano até o mês da transação)
    subcategory_spent_accumulated_before = calculate_spent_by_subcategory(subcategory, year_start, accumulated_end)
    subcategory_spent_year_before = calculate_spent_by_subcategory(subcategory, year_start, year_end)
    category_spent_accumulated_before = calculate_spent_by_category(category, year_start, accumulated_end)
    category_spent_year_before = calculate_spent_by_category(category, year_start, year_end)
    
    # Calcular gastos depois do registro
    transaction_impact = value if transaction_type == TRANSACTION_TYPE_CR else -value
    subcategory_spent_accumulated_after = subcategory_spent_accumulated_before + transaction_impact
    subcategory_spent_year_after = subcategory_spent_year_before + transaction_impact
    category_spent_accumulated_after = category_spent_accumulated_before + transaction_impact
    category_spent_year_after = category_spent_year_before + transaction_impact
    
    # Calcular projeção anual (média mensal × 12)
    current_month = transaction_date.month
    if current_month > 0:
        subcategory_projection = (subcategory_spent_accumulated_after / current_month) * 12
        category_projection = (category_spent_accumulated_after / current_month) * 12
    else:
        subcategory_projection = Decimal('0')
        category_projection = Decimal('0')
    
    # Calcular orçamentos acumulados (desde início do ano até o mês da transação)
    subcategory_budget_accumulated = calculate_budget_accumulated_by_subcategory(subcategory, transaction_date.year, transaction_date.month)
    subcategory_budget_year = calculate_budget_by_subcategory_year(subcategory, transaction_date.year)
    category_budget_accumulated = calculate_budget_accumulated_by_category(category, transaction_date.year, transaction_date.month)
    category_budget_year = calculate_budget_by_category_year(category, transaction_date.year)
    
    return JsonResponse({
        'subcategory': {
            'accumulated': {
                'spent_before': str(subcategory_spent_accumulated_before.quantize(Decimal('0.01'))),
                'spent_after': str(subcategory_spent_accumulated_after.quantize(Decimal('0.01'))),
                'budgeted': str(subcategory_budget_accumulated.quantize(Decimal('0.01')))
            },
            'year': {
                'spent_before': str(subcategory_spent_year_before.quantize(Decimal('0.01'))),
                'spent_after': str(subcategory_spent_year_after.quantize(Decimal('0.01'))),
                'projection': str(subcategory_projection.quantize(Decimal('0.01'))),
                'budgeted': str(subcategory_budget_year.quantize(Decimal('0.01')))
            }
        },
        'category': {
            'accumulated': {
                'spent_before': str(category_spent_accumulated_before.quantize(Decimal('0.01'))),
                'spent_after': str(category_spent_accumulated_after.quantize(Decimal('0.01'))),
                'budgeted': str(category_budget_accumulated.quantize(Decimal('0.01')))
            },
            'year': {
                'spent_before': str(category_spent_year_before.quantize(Decimal('0.01'))),
                'spent_after': str(category_spent_year_after.quantize(Decimal('0.01'))),
                'projection': str(category_projection.quantize(Decimal('0.01'))),
                'budgeted': str(category_budget_year.quantize(Decimal('0.01')))
            }
        }
    })


def get_multiple_budget_info(request):
    """Endpoint AJAX para obter informações de orçamento e gastos para múltiplas subcategorias"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        items = data.get('items', [])
        transaction_date_str = data.get('transaction_date')
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({'error': 'Invalid request data'}, status=400)
    
    if transaction_date_str:
        try:
            transaction_date = datetime.strptime(transaction_date_str, '%Y-%m-%d').date()
        except ValueError:
            transaction_date = date.today()
    else:
        transaction_date = date.today()
    
    # Converter items para formato esperado
    items_data = []
    for item in items:
        if item.get('is_transfer'):
            continue  # Ignorar transferências
        
        subcategory_id = item.get('subcategory_id')
        if not subcategory_id:
            continue
        
        try:
            subcategory = Subcategory.objects.get(pk=subcategory_id)
        except Subcategory.DoesNotExist:
            continue
        
        items_data.append({
            'subcategory': subcategory,
            'value': Decimal(str(item.get('value', 0))),
            'transaction_type': item.get('transaction_type', TRANSACTION_TYPE_DB),
            'is_transfer': False
        })
    
    budget_info = _calculate_multiple_budget_info(items_data, transaction_date)
    
    # Converter para formato JSON
    result = {
        'by_category': {},
        'by_subcategory': []
    }
    
    for cat_id, cat_data in budget_info['by_category'].items():
        result['by_category'][str(cat_id)] = {
            'category_name': cat_data['category'].category,
            'accumulated': {
                'spent_before': str(cat_data['accumulated']['spent_before'].quantize(Decimal('0.01'))),
                'spent_after': str(cat_data['accumulated']['spent_after'].quantize(Decimal('0.01'))),
                'budgeted': str(cat_data['accumulated']['budgeted'].quantize(Decimal('0.01')))
            },
            'year': {
                'spent_before': str(cat_data['year']['spent_before'].quantize(Decimal('0.01'))),
                'spent_after': str(cat_data['year']['spent_after'].quantize(Decimal('0.01'))),
                'projection': str(cat_data['year'].get('projection', Decimal('0')).quantize(Decimal('0.01'))),
                'budgeted': str(cat_data['year']['budgeted'].quantize(Decimal('0.01')))
            }
        }
    
    for subcat_data in budget_info['by_subcategory']:
        subcategory = subcat_data['subcategory']
        result['by_subcategory'].append({
            'subcategory_id': subcategory.id,
            'subcategory_name': str(subcategory),
            'category_name': subcategory.category.category,
            'accumulated': {
                'spent_before': str(subcat_data['accumulated']['spent_before'].quantize(Decimal('0.01'))),
                'spent_after': str(subcat_data['accumulated']['spent_after'].quantize(Decimal('0.01'))),
                'budgeted': str(subcat_data['accumulated']['budgeted'].quantize(Decimal('0.01')))
            },
            'year': {
                'spent_before': str(subcat_data['year']['spent_before'].quantize(Decimal('0.01'))),
                'spent_after': str(subcat_data['year']['spent_after'].quantize(Decimal('0.01'))),
                'projection': str(subcat_data['year'].get('projection', Decimal('0')).quantize(Decimal('0.01'))),
                'budgeted': str(subcat_data['year']['budgeted'].quantize(Decimal('0.01')))
            },
            'items_count': subcat_data['items_count'],
            'total_value': str(subcat_data['total_value'].quantize(Decimal('0.01')))
        })
    
    return JsonResponse(result)


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
                            categories = Category.objects.all().order_by('category')
                            return render(request, 'finance/multiple_transaction_form.html', {
                                'form': form,
                                'formset': formset,
                                'categories': categories
                            })
                        
                        transfer_group_id = uuid.uuid4()
                        
                        # Transação de débito (conta origem)
                        debit_transaction = Transaction.objects.create(
                            account=source_account,
                            beneficiary=None,
                            subcategory=None,
                            transaction_type=TRANSACTION_TYPE_DB,
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
                            transaction_type=TRANSACTION_TYPE_CR,
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
    
    categories = Category.objects.all().order_by('category')
    return render(request, 'finance/multiple_transaction_form.html', {
        'form': form,
        'formset': formset,
        'categories': categories
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
                            categories = Category.objects.all().order_by('category')
                            return render(request, 'finance/multiple_transaction_form.html', {
                                'form': form,
                                'formset': formset,
                                'group_id': group_id,
                                'categories': categories
                            })
                        
                        transfer_group_id = uuid.uuid4()
                        
                        # Transação de débito (conta origem)
                        Transaction.objects.create(
                            account=source_account,
                            beneficiary=None,
                            subcategory=None,
                            transaction_type=TRANSACTION_TYPE_DB,
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
                            transaction_type=TRANSACTION_TYPE_CR,
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
                debit_t = next((t for t in first_pair if t.transaction_type == TRANSACTION_TYPE_DB), None)
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
                debit_t = next((t for t in pair if t.transaction_type == TRANSACTION_TYPE_DB), None)
                credit_t = next((t for t in pair if t.transaction_type == TRANSACTION_TYPE_CR), None)
                if debit_t and credit_t:
                    formset_data.append({
                        'transaction_type': TRANSACTION_TYPE_DB,
                        'destination_account': credit_t.account,
                        'value': debit_t.value,
                        'is_transfer': True,
                    })
        
        # Criar formset sem extra quando editando (já temos os dados)
        MultipleTransactionItemFormSetEdit = formset_factory(
            MultipleTransactionItemForm,
            extra=0,  # Sem formulários extras quando editando
            can_delete=True,
            min_num=1,
            validate_min=True
        )
        formset = MultipleTransactionItemFormSetEdit(initial=formset_data)
    
    categories = Category.objects.all().order_by('category')
    return render(request, 'finance/multiple_transaction_form.html', {
        'form': form,
        'formset': formset,
        'group_id': group_id,
        'categories': categories
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
                            categories = Category.objects.all().order_by('category')
                            return render(request, 'finance/multiple_scheduler_form.html', {
                                'form': form,
                                'formset': formset,
                                'categories': categories
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
                        item_notes = item_data.get('notes', '')
                        
                        if is_transfer:
                            # Criar transferência (2 schedulers: débito e crédito)
                            destination_account = item_data.get('destination_account')
                            
                            # Scheduler de débito (conta origem)
                            debit_scheduler = Scheduler(
                                account=account,
                                beneficiary=beneficiary,
                                subcategory=None,
                                transaction_type=TRANSACTION_TYPE_DB,
                                value=value,
                                due_date=due_date,
                                purchase_date=purchase_date,
                                notes=item_notes,
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
                                transaction_type=TRANSACTION_TYPE_CR,
                                value=value,
                                due_date=due_date,
                                purchase_date=purchase_date,
                                notes=item_notes,
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
                                notes=item_notes,
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
                    categories = Category.objects.all().order_by('category')
                    return render(request, 'finance/multiple_scheduler_form.html', {
                        'form': form,
                        'formset': formset,
                        'categories': categories
                    })
            
            messages.success(request, f'Agendamento múltiplo criado com sucesso! {len(created_schedulers)} item(ns) criado(s).')
            return redirect('finance:scheduler_list')
        else:
            messages.error(request, 'Por favor, corrija os erros abaixo.')
    else:
        form = MultipleSchedulerForm()
        formset = MultipleSchedulerItemFormSet()
    
    categories = Category.objects.all().order_by('category')
    return render(request, 'finance/multiple_scheduler_form.html', {
        'form': form,
        'formset': formset,
        'categories': categories
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
                            categories = Category.objects.all().order_by('category')
                            return render(request, 'finance/multiple_scheduler_form.html', {
                                'form': form,
                                'formset': formset,
                                'group_id': group_id,
                                'categories': categories
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
                        item_notes = item_data.get('notes', '')
                        
                        if is_transfer:
                            # Criar transferência (2 schedulers: débito e crédito)
                            destination_account = item_data.get('destination_account')
                            
                            # Scheduler de débito (conta origem)
                            debit_scheduler = Scheduler(
                                account=account,
                                beneficiary=beneficiary,
                                subcategory=None,
                                transaction_type=TRANSACTION_TYPE_DB,
                                value=value,
                                due_date=due_date,
                                purchase_date=purchase_date,
                                notes=item_notes,
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
                                transaction_type=TRANSACTION_TYPE_CR,
                                value=value,
                                due_date=due_date,
                                purchase_date=purchase_date,
                                notes=item_notes,
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
                                notes=item_notes,
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
                    categories = Category.objects.all().order_by('category')
                    return render(request, 'finance/multiple_scheduler_form.html', {
                        'form': form,
                        'formset': formset,
                        'group_id': group_id,
                        'categories': categories
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
                        'notes': scheduler.notes,
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
                    'notes': scheduler.notes,
                })
        
        # Criar formset com extra=0 quando editando para evitar item vazio
        MultipleSchedulerItemFormSetEdit = formset_factory(
            MultipleSchedulerItemForm,
            extra=0,
            can_delete=True,
            min_num=1,
            validate_min=True
        )
        formset = MultipleSchedulerItemFormSetEdit(initial=formset_data)
    
    categories = Category.objects.all().order_by('category')
    return render(request, 'finance/multiple_scheduler_form.html', {
        'form': form,
        'formset': formset,
        'group_id': group_id,
        'categories': categories
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
    
    def calculate_multiple_budget_info_from_formset(formset, transaction_date):
        """Extrai dados do formset e calcula informações de orçamento"""
        items_data = []
        for form in formset:
            if form.is_valid() and not form.cleaned_data.get('DELETE', False):
                items_data.append({
                    'subcategory': form.cleaned_data.get('subcategory'),
                    'value': form.cleaned_data.get('value', 0),
                    'transaction_type': form.cleaned_data.get('transaction_type', TRANSACTION_TYPE_DB),
                    'is_transfer': form.cleaned_data.get('is_transfer', False)
                })
        return _calculate_multiple_budget_info(items_data, transaction_date)
    
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
                            
                            # Calcular informações de orçamento
                            transaction_date = first_scheduler.due_date or date.today()
                            budget_info = calculate_multiple_budget_info_from_formset(formset, transaction_date)
                            
                            return render(request, 'finance/multiple_scheduler_register.html', {
                                'schedulers': schedulers,
                                'formset': formset,
                                'next_due_date': next_due_date,
                                'group_id': group_id,
                                'budget_info': budget_info
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
                        # Calcular informações de orçamento
                        transaction_date = first_scheduler.due_date or date.today()
                        budget_info = calculate_multiple_budget_info_from_formset(formset, transaction_date)
                        
                        return render(request, 'finance/multiple_scheduler_register.html', {
                            'schedulers': schedulers,
                            'formset': formset,
                            'next_due_date': next_due_date,
                            'group_id': group_id,
                            'budget_info': budget_info
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
                                
                                # Calcular informações de orçamento
                                transaction_date = first_scheduler.due_date or date.today()
                                budget_info = calculate_multiple_budget_info_from_formset(formset, transaction_date)
                                
                                return render(request, 'finance/multiple_scheduler_register.html', {
                                    'schedulers': schedulers,
                                    'formset': formset,
                                    'next_due_date': next_due_date,
                                    'group_id': group_id,
                                    'budget_info': budget_info
                                })
                            
                            value = item_data.get('value', scheduler.value)
                            transfer_notes = item_data.get('notes', scheduler.notes) or ''
                            # Criar débito na conta de origem
                            transfer_group_id = uuid.uuid4()
                            debit_transaction = Transaction.objects.create(
                                account=source_account,
                                beneficiary=scheduler.beneficiary,
                                subcategory=None,  # Transferências não têm subcategoria
                                transaction_type=TRANSACTION_TYPE_DB,
                                value=value,
                                due_date=scheduler.due_date,
                                transaction_date=scheduler.due_date,
                                purchase_date=scheduler.purchase_date,
                                notes=transfer_notes,
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
                                transaction_type=TRANSACTION_TYPE_CR,
                                value=value,
                                due_date=scheduler.due_date,
                                transaction_date=scheduler.due_date,
                                purchase_date=scheduler.purchase_date,
                                notes=transfer_notes,
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
                                'notes': item_data.get('notes', ''),
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
        
        def _notes_initial(scheduler):
            """Pré-preenche anotações com 'Parcelas restantes: XXX/XXX' quando for recorrente."""
            notes_initial = scheduler.notes or ''
            inst_info = scheduler.get_installment_info()
            if inst_info:
                parcelas_text = f"Parcelas restantes: {inst_info['current']:03d}/{inst_info['total']:03d}"
                notes_initial = f"{notes_initial.strip()}\n{parcelas_text}".strip() if notes_initial.strip() else parcelas_text
            return notes_initial

        # Primeiro, adicionar schedulers normais
        for scheduler in schedulers:
            if not scheduler.is_transfer:
                initial_data.append({
                    'subcategory': scheduler.subcategory,
                    'transaction_type': scheduler.transaction_type,
                    'value': scheduler.value,
                    'is_transfer': False,
                    'destination_account': None,
                    'notes': _notes_initial(scheduler),
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
                    'notes': _notes_initial(scheduler),
                })
                # Scheduler de crédito não precisa ser adicionado (já representado pelo par)
        
        formset = MultipleSchedulerRegisterItemFormSet(initial=initial_data)
    
    next_due_date = first_scheduler.get_next_due_date_after_registration()
    
    # Calcular informações de orçamento
    transaction_date = first_scheduler.due_date or date.today()
    items_data = []
    for item in initial_data:
        items_data.append({
            'subcategory': item.get('subcategory'),
            'value': item.get('value', 0),
            'transaction_type': item.get('transaction_type', TRANSACTION_TYPE_DB),
            'is_transfer': item.get('is_transfer', False)
        })
    budget_info = _calculate_multiple_budget_info(items_data, transaction_date)
    
    return render(request, 'finance/multiple_scheduler_register.html', {
        'schedulers': schedulers,
        'formset': formset,
        'next_due_date': next_due_date,
        'group_id': group_id,
        'budget_info': budget_info
    })


# Asset Views
def asset_list(request):
    """Lista de ativos com filtros e paginação"""
    # Inicializar formulário de filtros
    filter_form = AssetFilterForm(request.GET)
    
    # Query base
    assets = Asset.objects.all()
    
    # Aplicar filtros
    if filter_form.is_valid():
        asset_types = filter_form.cleaned_data.get('asset_type')
        currencies = filter_form.cleaned_data.get('currency')
        sector = filter_form.cleaned_data.get('sector')
        code_search = filter_form.cleaned_data.get('code_search')
        name_search = filter_form.cleaned_data.get('name_search')
        
        if asset_types:
            assets = assets.filter(asset_type__in=asset_types)
        
        if currencies:
            assets = assets.filter(currency__in=currencies)
        
        if sector:
            assets = assets.filter(sector__icontains=sector)
        
        if code_search:
            assets = assets.filter(code__icontains=code_search)
        
        if name_search:
            assets = assets.filter(name__icontains=name_search)
    
    # Ordenar - suporte para múltiplas colunas
    sort_fields_str = request.GET.get('sort', '')
    sort_orders_str = request.GET.get('order', 'asc')
    
    # Mapeamento de campos de ordenação
    sort_mapping = {
        'code': 'code',
        'name': 'name',
        'asset_type': 'asset_type',
        'sector': 'sector',
        'currency': 'currency',
    }
    
    # Processar múltiplos campos de ordenação (separados por vírgula)
    sort_fields = [f.strip() for f in sort_fields_str.split(',') if f.strip()] if sort_fields_str else []
    sort_orders = [o.strip() for o in sort_orders_str.split(',')] if sort_fields_str else []
    
    # Validar e aplicar ordenações
    order_fields = []
    valid_sorts = []
    valid_orders = []
    
    # Se não houver ordenação especificada, usar ordenação padrão por código
    if not sort_fields:
        sort_fields = ['code']
        sort_orders = ['asc']
    
    for i, sort_field in enumerate(sort_fields):
        if sort_field in sort_mapping:
            sort_order = sort_orders[i] if i < len(sort_orders) else 'asc'
            if sort_order not in ['asc', 'desc']:
                sort_order = 'asc'
            
            order_prefix = '' if sort_order == 'asc' else '-'
            order_fields.append(f"{order_prefix}{sort_mapping[sort_field]}")
            
            valid_sorts.append(sort_field)
            valid_orders.append(sort_order)
    
    if order_fields:
        assets = assets.order_by(*order_fields)
    else:
        # Ordenação padrão
        assets = assets.order_by('code')
    
    # Paginação
    paginator = Paginator(assets, ASSETS_PER_PAGE)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Passar informações de ordenação para o template
    sort_info = {}
    for idx, sort_field in enumerate(valid_sorts):
        sort_info[sort_field] = {
            'priority': idx + 1,
            'order': valid_orders[idx] if idx < len(valid_orders) else 'asc'
        }
    
    return render(request, 'finance/asset_list.html', {
        'assets': page_obj,
        'filter_form': filter_form,
        'page_obj': page_obj,
        'sort_info': sort_info,
    })


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
    """Lista de transações de ativos com filtros e paginação"""
    # Inicializar formulário de filtros
    filter_form = AssetTransactionFilterForm(request.GET)
    
    # Query base
    transactions = AssetTransaction.objects.all().select_related('asset', 'account')
    
    # Aplicar filtros
    if filter_form.is_valid():
        assets = filter_form.cleaned_data.get('asset')
        accounts = filter_form.cleaned_data.get('account')
        operation_types = filter_form.cleaned_data.get('operation_type')
        date_start = filter_form.cleaned_data.get('date_start')
        date_end = filter_form.cleaned_data.get('date_end')
        
        if assets:
            transactions = transactions.filter(asset__in=assets)
        
        if accounts:
            transactions = transactions.filter(account__in=accounts)
        
        if operation_types:
            transactions = transactions.filter(operation_type__in=operation_types)
        
        if date_start:
            transactions = transactions.filter(date__gte=date_start)
        
        if date_end:
            transactions = transactions.filter(date__lte=date_end)
    
    # Ordenar - suporte para múltiplas colunas
    sort_fields_str = request.GET.get('sort', '')
    sort_orders_str = request.GET.get('order', 'desc')
    
    # Mapeamento de campos de ordenação
    sort_mapping = {
        'asset': 'asset__code',
        'account': 'account__name',
        'operation_type': 'operation_type',
        'date': 'date',
        'quantity': 'quantity',
        'price': 'price',
        'total_value': 'total_value',
        'fees': 'fees',
        'income_value': 'income_value',
    }
    
    # Processar múltiplos campos de ordenação (separados por vírgula)
    sort_fields = [f.strip() for f in sort_fields_str.split(',') if f.strip()] if sort_fields_str else []
    sort_orders = [o.strip() for o in sort_orders_str.split(',')] if sort_orders_str else []
    
    # Validar e aplicar ordenações
    order_fields = []
    valid_sorts = []
    valid_orders = []
    
    for i, sort_field in enumerate(sort_fields):
        if sort_field in sort_mapping:
            sort_order = sort_orders[i] if i < len(sort_orders) else 'desc'
            if sort_order not in ['asc', 'desc']:
                sort_order = 'desc'
            
            order_prefix = '' if sort_order == 'asc' else '-'
            order_fields.append(f"{order_prefix}{sort_mapping[sort_field]}")
            
            valid_sorts.append(sort_field)
            valid_orders.append(sort_order)
    
    if order_fields:
        # Adicionar ordenação padrão por data como fallback
        if 'date' not in valid_sorts:
            order_fields.append('-date')
        transactions = transactions.order_by(*order_fields)
    else:
        # Ordenação padrão
        transactions = transactions.order_by('-date')
    
    # Paginação
    paginator = Paginator(transactions, ASSET_TRANSACTIONS_PER_PAGE)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Calcular subtotal da página
    subtotal = Decimal('0')
    total_fees = Decimal('0')
    total_income = Decimal('0')
    
    for transaction in page_obj:
        subtotal += transaction.total_value or Decimal('0')
        total_fees += transaction.fees or Decimal('0')
        total_income += transaction.income_value or Decimal('0')
    
    # Passar informações de ordenação para o template
    # Criar dicionário com prioridade de cada campo ordenado
    sort_info = {}
    for idx, sort_field in enumerate(valid_sorts):
        sort_info[sort_field] = {
            'priority': idx + 1,
            'order': valid_orders[idx] if idx < len(valid_orders) else 'desc'
        }
    
    return render(request, 'finance/asset_transaction_list.html', {
        'transactions': page_obj,
        'filter_form': filter_form,
        'page_obj': page_obj,
        'subtotal': subtotal,
        'total_fees': total_fees,
        'total_income': total_income,
        'sort_info': sort_info,
    })


def asset_transaction_create(request):
    """Criar nova transação de ativo"""
    if request.method == 'POST':
        form = AssetTransactionForm(request.POST)
        if form.is_valid():
            # Capturar cash_account do formulário
            cash_account = form.cleaned_data.get('cash_account')
            # Definir cash_account temporariamente para uso no save
            if cash_account:
                form.instance._cash_account = cash_account
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
            # Capturar cash_account do formulário
            cash_account = form.cleaned_data.get('cash_account')
            # Definir cash_account temporariamente para uso no save
            if cash_account:
                form.instance._cash_account = cash_account
            form.save()
            messages.success(request, 'Transação de ativo atualizada com sucesso!')
            # Verificar se há parâmetro 'next' para redirecionar de volta ao extrato (GET ou POST)
            next_url = request.POST.get('next') or request.GET.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('finance:asset_transaction_list')
    else:
        form = AssetTransactionForm(instance=transaction)
    next_url = request.GET.get('next', '')
    return render(request, 'finance/asset_transaction_form.html', {'form': form, 'transaction': transaction, 'next_url': next_url})


def asset_transaction_delete(request, pk):
    """Deletar transação de ativo"""
    transaction = get_object_or_404(AssetTransaction, pk=pk)
    if request.method == 'POST':
        transaction.delete()
        messages.success(request, 'Transação de ativo deletada com sucesso!')
        return redirect('finance:asset_transaction_list')
    return render(request, 'finance/asset_transaction_confirm_delete.html', {'transaction': transaction})


# Multiple Asset Transaction Views
def multiple_asset_transaction_create(request):
    """Criar nova transação múltipla de ativos"""
    if request.method == 'POST':
        form = MultipleAssetTransactionForm(request.POST)
        formset = MultipleAssetTransactionItemFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            # Gerar UUID para vincular todas as transações
            multiple_group_id = uuid.uuid4()
            
            # Campos compartilhados do cabeçalho
            account = form.cleaned_data['account']
            operation_type = form.cleaned_data['operation_type']
            date = form.cleaned_data['date']
            fees_total = form.cleaned_data['fees']
            cash_account = form.cleaned_data.get('cash_account')
            notes = form.cleaned_data.get('notes', '')
            assessoria = form.cleaned_data.get('assessoria', False)
            invoice = form.cleaned_data.get('invoice', '')
            
            # Coletar itens válidos
            valid_items = []
            for item_form in formset:
                if item_form.cleaned_data and not item_form.cleaned_data.get('DELETE', False):
                    asset = item_form.cleaned_data.get('asset')
                    quantity = item_form.cleaned_data.get('quantity')
                    price = item_form.cleaned_data.get('price')
                    total_value = item_form.cleaned_data.get('total_value')
                    
                    if asset and quantity and price:
                        # Calcular total_value se não foi fornecido
                        if not total_value or total_value == 0:
                            total_value = quantity * price
                        
                        valid_items.append({
                            'asset': asset,
                            'quantity': quantity,
                            'price': price,
                            'total_value': total_value
                        })
            
            if not valid_items:
                messages.error(request, 'É necessário adicionar pelo menos um ativo.')
                return render(request, 'finance/multiple_asset_transaction_form.html', {
                    'form': form,
                    'formset': formset
                })
            
            # Calcular total geral para rateio
            total_geral = sum(item['total_value'] for item in valid_items)
            
            if total_geral == 0:
                messages.error(request, 'O valor total dos ativos deve ser maior que zero.')
                return render(request, 'finance/multiple_asset_transaction_form.html', {
                    'form': form,
                    'formset': formset
                })
            
            # Criar todas as AssetTransactions em uma transação atômica
            try:
                with db_transaction.atomic():
                    created_transactions = []
                    for item in valid_items:
                        # Ratear taxas proporcionalmente
                        if total_geral > 0:
                            fees_item = (item['total_value'] / total_geral) * fees_total
                        else:
                            fees_item = Decimal('0')
                        
                        # Criar AssetTransaction
                        asset_transaction = AssetTransaction(
                            asset=item['asset'],
                            account=account,
                            operation_type=operation_type,
                            date=date,
                            quantity=item['quantity'],
                            price=item['price'],
                            fees=fees_item,
                            total_value=item['total_value'],
                            income_value=Decimal('0'),
                            notes=notes,
                            assessoria=assessoria,
                            invoice=invoice,
                            multiple_group_id=multiple_group_id
                        )
                        
                        # Definir cash_account temporariamente para uso no save
                        if cash_account:
                            asset_transaction._cash_account = cash_account
                        
                        # Salvar para criar Transactions relacionadas
                        asset_transaction.save()
                        created_transactions.append(asset_transaction)
                    
                    messages.success(
                        request, 
                        f'Transação múltipla criada com sucesso! {len(created_transactions)} transação(ões) de ativo criada(s).'
                    )
                    return redirect('finance:asset_transaction_list')
                    
            except Exception as e:
                messages.error(request, f'Erro ao criar transação múltipla: {str(e)}')
                return render(request, 'finance/multiple_asset_transaction_form.html', {
                    'form': form,
                    'formset': formset
                })
        else:
            # Formulário inválido
            return render(request, 'finance/multiple_asset_transaction_form.html', {
                'form': form,
                'formset': formset
            })
    else:
        form = MultipleAssetTransactionForm()
        formset = MultipleAssetTransactionItemFormSet()
    
    return render(request, 'finance/multiple_asset_transaction_form.html', {
        'form': form,
        'formset': formset
    })


def multiple_asset_transaction_update(request, group_id):
    """Editar transação múltipla de ativos existente"""
    # Buscar todas as transações do grupo
    transactions = AssetTransaction.objects.filter(multiple_group_id=group_id).order_by('id')
    
    if not transactions.exists():
        messages.error(request, 'Transação múltipla não encontrada.')
        return redirect('finance:asset_transaction_list')
    
    # Pegar dados da primeira transação para preencher o form
    first_transaction = transactions.first()
    
    if request.method == 'POST':
        form = MultipleAssetTransactionForm(request.POST)
        formset = MultipleAssetTransactionItemFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            # Campos compartilhados do cabeçalho
            account = form.cleaned_data['account']
            operation_type = form.cleaned_data['operation_type']
            date = form.cleaned_data['date']
            fees_total = form.cleaned_data['fees']
            cash_account = form.cleaned_data.get('cash_account')
            notes = form.cleaned_data.get('notes', '')
            assessoria = form.cleaned_data.get('assessoria', False)
            invoice = form.cleaned_data.get('invoice', '')
            
            # Coletar itens válidos
            valid_items = []
            for item_form in formset:
                if item_form.cleaned_data and not item_form.cleaned_data.get('DELETE', False):
                    asset = item_form.cleaned_data.get('asset')
                    quantity = item_form.cleaned_data.get('quantity')
                    price = item_form.cleaned_data.get('price')
                    total_value = item_form.cleaned_data.get('total_value')
                    
                    if asset and quantity and price:
                        if not total_value or total_value == 0:
                            total_value = quantity * price
                        
                        valid_items.append({
                            'asset': asset,
                            'quantity': quantity,
                            'price': price,
                            'total_value': total_value
                        })
            
            if not valid_items:
                messages.error(request, 'É necessário adicionar pelo menos um ativo.')
                return render(request, 'finance/multiple_asset_transaction_form.html', {
                    'form': form,
                    'formset': formset,
                    'group_id': group_id
                })
            
            # Calcular total geral para rateio
            total_geral = sum(item['total_value'] for item in valid_items)
            
            if total_geral == 0:
                messages.error(request, 'O valor total dos ativos deve ser maior que zero.')
                return render(request, 'finance/multiple_asset_transaction_form.html', {
                    'form': form,
                    'formset': formset,
                    'group_id': group_id
                })
            
            # Deletar transações antigas e criar novas
            try:
                with db_transaction.atomic():
                    # Deletar transações antigas
                    transactions.delete()
                    
                    # Criar novas transações
                    created_transactions = []
                    for item in valid_items:
                        # Ratear taxas proporcionalmente
                        if total_geral > 0:
                            fees_item = (item['total_value'] / total_geral) * fees_total
                        else:
                            fees_item = Decimal('0')
                        
                        # Criar AssetTransaction
                        asset_transaction = AssetTransaction(
                            asset=item['asset'],
                            account=account,
                            operation_type=operation_type,
                            date=date,
                            quantity=item['quantity'],
                            price=item['price'],
                            fees=fees_item,
                            total_value=item['total_value'],
                            income_value=Decimal('0'),
                            notes=notes,
                            assessoria=assessoria,
                            invoice=invoice,
                            multiple_group_id=group_id
                        )
                        
                        # Definir cash_account temporariamente para uso no save
                        if cash_account:
                            asset_transaction._cash_account = cash_account
                        
                        # Salvar para criar Transactions relacionadas
                        asset_transaction.save()
                        created_transactions.append(asset_transaction)
                    
                    messages.success(
                        request, 
                        f'Transação múltipla atualizada com sucesso! {len(created_transactions)} transação(ões) de ativo atualizada(s).'
                    )
                    return redirect('finance:asset_transaction_list')
                    
            except Exception as e:
                messages.error(request, f'Erro ao atualizar transação múltipla: {str(e)}')
                return render(request, 'finance/multiple_asset_transaction_form.html', {
                    'form': form,
                    'formset': formset,
                    'group_id': group_id
                })
        else:
            return render(request, 'finance/multiple_asset_transaction_form.html', {
                'form': form,
                'formset': formset,
                'group_id': group_id
            })
    else:
        # Tentar obter cash_account das Transactions relacionadas
        cash_account = None
        for trans in transactions:
            related_transactions = Transaction.objects.filter(
                asset_transaction=trans,
                is_transfer=True
            )
            if related_transactions.exists():
                # Pegar a primeira transaction de débito que não seja da conta de investimento
                for rel_trans in related_transactions.filter(transaction_type=TRANSACTION_TYPE_DB):
                    if rel_trans.account != trans.account:
                        cash_account = rel_trans.account
                        break
                if cash_account:
                    break
        
        # Preencher form com dados da primeira transação
        form = MultipleAssetTransactionForm(initial={
            'account': first_transaction.account,
            'operation_type': first_transaction.operation_type,
            'date': first_transaction.date,
            'fees': sum(t.fees for t in transactions),
            'cash_account': cash_account,
            'notes': first_transaction.notes,
            'assessoria': first_transaction.assessoria,
            'invoice': first_transaction.invoice
        })
        
        # Preencher formset com dados das transações
        formset_data = []
        for trans in transactions:
            formset_data.append({
                'asset': trans.asset,
                'quantity': trans.quantity,
                'price': trans.price,
                'total_value': trans.total_value
            })
        
        # Criar formset com dados iniciais
        formset = MultipleAssetTransactionItemFormSet(initial=formset_data)
    
    return render(request, 'finance/multiple_asset_transaction_form.html', {
        'form': form,
        'formset': formset,
        'group_id': group_id
    })


def multiple_asset_transaction_delete(request, group_id):
    """Deletar transação múltipla de ativos"""
    transactions = AssetTransaction.objects.filter(multiple_group_id=group_id)
    
    if not transactions.exists():
        messages.error(request, 'Transação múltipla não encontrada.')
        return redirect('finance:asset_transaction_list')
    
    if request.method == 'POST':
        count = transactions.count()
        transactions.delete()
        messages.success(request, f'Transação múltipla deletada com sucesso! {count} transação(ões) removida(s).')
        return redirect('finance:asset_transaction_list')
    
    return render(request, 'finance/multiple_asset_transaction_confirm_delete.html', {
        'transactions': transactions,
        'group_id': group_id
    })


# AssetTransactionCategoryConfig Views
def asset_transaction_category_config_list(request):
    """Lista de configurações de categoria para transações de ativos"""
    configs = AssetTransactionCategoryConfig.objects.all().select_related(
        'subcategory_principal', 'subcategory_principal__category',
        'subcategory_fees', 'subcategory_fees__category'
    ).order_by('operation_type', 'asset_type')
    return render(request, 'finance/asset_transaction_category_config_list.html', {'configs': configs})


def asset_transaction_category_config_create(request):
    """Criar nova configuração de categoria"""
    if request.method == 'POST':
        form = AssetTransactionCategoryConfigForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Configuração criada com sucesso!')
            return redirect('finance:asset_transaction_category_config_list')
    else:
        form = AssetTransactionCategoryConfigForm()
    return render(request, 'finance/asset_transaction_category_config_form.html', {'form': form})


def asset_transaction_category_config_update(request, pk):
    """Editar configuração existente"""
    config = get_object_or_404(AssetTransactionCategoryConfig, pk=pk)
    if request.method == 'POST':
        form = AssetTransactionCategoryConfigForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, 'Configuração atualizada com sucesso!')
            return redirect('finance:asset_transaction_category_config_list')
    else:
        form = AssetTransactionCategoryConfigForm(instance=config)
    return render(request, 'finance/asset_transaction_category_config_form.html', {'form': form, 'config': config})


def asset_transaction_category_config_delete(request, pk):
    """Deletar configuração"""
    config = get_object_or_404(AssetTransactionCategoryConfig, pk=pk)
    if request.method == 'POST':
        config.delete()
        messages.success(request, 'Configuração deletada com sucesso!')
        return redirect('finance:asset_transaction_category_config_list')
    return render(request, 'finance/asset_transaction_category_config_confirm_delete.html', {'config': config})


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
    """Página inicial de relatórios com atalhos"""
    return render(request, 'finance/reports_index.html')


def account_statement_report(request):
    """Página de extrato de contas"""
    accounts = Account.objects.all()
    today = date.today()
    first_day_of_month = date(today.year, today.month, 1)
    
    filter_form = AccountStatementFilterForm(
        request.GET,
        initial={'start_date': first_day_of_month, 'end_date': today}
    )
    
    selected_accounts = []
    start_date = first_day_of_month
    end_date = today
    include_future = False
    
    if filter_form.is_valid():
        accounts_qs = filter_form.cleaned_data.get('account')
        selected_accounts = list(accounts_qs) if accounts_qs else []
        start_date = filter_form.cleaned_data.get('start_date') or first_day_of_month
        end_date = filter_form.cleaned_data.get('end_date') or today
        include_future = filter_form.cleaned_data.get('include_future') or False
    
    selected_account_ids = [a.pk for a in selected_accounts]
    account = selected_accounts[0] if len(selected_accounts) == 1 else None
    
    movements = []
    transactions = []
    previous_balance = None
    final_balance = None
    has_scheduled = False
    
    if selected_accounts and start_date and end_date:
        if start_date > end_date:
            messages.error(request, 'Data inicial deve ser anterior à data final.')
            total_payments = Decimal('0')
            total_deposits = Decimal('0')
        else:
            # Saldo inicial agregado (soma dos saldos anteriores à data inicial de cada conta)
            previous_balance = sum(
                (acc.get_previous_balance(start_date) or Decimal('0')) for acc in selected_accounts
            )
            # Coletar movimentos de todas as contas e marcar cada um com a conta
            all_movements = []
            for acc in selected_accounts:
                movs, _ = acc.get_statement(start_date, end_date)
                for m in movs:
                    m = dict(m)
                    m['account'] = acc
                    all_movements.append(m)
                if include_future:
                    sched = acc.get_scheduled_movements(start_date, end_date)
                    has_scheduled = has_scheduled or len(sched) > 0
                    for m in sched:
                        m = dict(m)
                        m['account'] = acc
                        all_movements.append(m)
            
            def _statement_sort_key(m):
                is_sched = 1 if m.get('type') == 'SCHEDULED' else 0
                return (m['date'], is_sched, m['account'].pk)
            merged = sorted(all_movements, key=_statement_sort_key)
            
            # Saldo linha a linha (agregado)
            running = previous_balance
            for m in merged:
                running += (m.get('credit') or Decimal('0')) - (m.get('debit') or Decimal('0'))
                m['balance'] = running
            final_balance = merged[-1]['balance'] if merged else previous_balance
            movements = merged
            
            total_payments = Decimal('0')
            total_deposits = Decimal('0')
            for movement in movements:
                amount = 0
                if movement.get('debit'):
                    amount = -float(movement['debit'])
                    total_payments += Decimal(str(abs(amount)))
                elif movement.get('credit'):
                    amount = float(movement['credit'])
                    total_deposits += Decimal(str(amount))
                
                is_scheduled = movement.get('type') == 'SCHEDULED'
                trans_id = None
                if movement.get('transaction'):
                    trans_id = movement['transaction'].id
                elif movement.get('asset_transaction'):
                    trans_id = movement['asset_transaction'].id
                elif is_scheduled and movement.get('scheduler'):
                    trans_id = f"s-{movement['scheduler'].id}"
                
                transactions.append({
                    'id': trans_id,
                    'date': movement['date'],
                    'description': movement['description'],
                    'amount': amount,
                    'running_balance': float(movement.get('balance', 0)),
                    'transaction': movement.get('transaction'),
                    'is_scheduled': is_scheduled,
                    'scheduler': movement.get('scheduler'),
                    'account': movement['account'],
                })
    else:
        total_payments = Decimal('0')
        total_deposits = Decimal('0')
    
    categories = Subcategory.objects.all().select_related('category').order_by('category__category', 'subcategory')
    
    # Query string para o "next" dos links de edição (preserva contas, datas e include_future)
    base_path = reverse('finance:account_statement_report')
    next_parts = []
    for aid in selected_account_ids:
        next_parts.append(('account', str(aid)))
    next_parts.append(('start_date', str(start_date)))
    next_parts.append(('end_date', str(end_date)))
    if include_future:
        next_parts.append(('include_future', '1'))
    statement_next_url = base_path + '?' + urlencode(next_parts)
    
    return render(request, 'finance/account_statement_report.html', {
        'accounts': accounts,
        'account': account,
        'selected_account': account,
        'selected_accounts': selected_accounts,
        'selected_account_ids': selected_account_ids,
        'start_date': start_date,
        'end_date': end_date,
        'movements': movements,
        'transactions': transactions,
        'previous_balance': previous_balance,
        'final_balance': final_balance,
        'total_payments': total_payments,
        'total_deposits': total_deposits,
        'categories': categories,
        'today': today,
        'include_future': include_future,
        'has_scheduled': has_scheduled,
        'statement_next_url': statement_next_url,
        'filter_form': filter_form,
    })


def account_statement(request, account_id=None):
    """Exibe o extrato bancário da conta"""
    accounts = Account.objects.all()
    
    # Valores padrão: início do mês atual e data de hoje
    today = date.today()
    first_day_of_month = date(today.year, today.month, 1)
    
    # Obter account_id da URL path ou do GET
    if account_id is None:
        account_id = request.GET.get('account')
    
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    account = None
    # Usar valores padrão se não fornecidos
    start_date = first_day_of_month
    end_date = today
    movements = []
    transactions = []
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
                total_payments = Decimal('0')
                total_deposits = Decimal('0')
            else:
                movements, previous_balance = account.get_statement(start_date, end_date)
                if movements:
                    final_balance = movements[-1]['balance']
                else:
                    final_balance = previous_balance
                
                # Formatar transações para o template (com saldo acumulado)
                # O saldo já vem calculado no movement['balance'], então podemos usar diretamente
                total_payments = Decimal('0')
                total_deposits = Decimal('0')
                
                for movement in movements:
                    amount = 0
                    if movement.get('debit'):
                        amount = -float(movement['debit'])
                        total_payments += Decimal(str(abs(amount)))
                    elif movement.get('credit'):
                        amount = float(movement['credit'])
                        total_deposits += Decimal(str(amount))
                    
                    # ID da transação (pode ser Transaction ou AssetTransaction relacionado)
                    trans_id = None
                    if movement.get('transaction'):
                        trans_id = movement['transaction'].id
                    elif movement.get('asset_transaction'):
                        # Se houver asset_transaction, usar o ID dele (para compatibilidade)
                        trans_id = movement['asset_transaction'].id
                    
                    transactions.append({
                        'id': trans_id,
                        'date': movement['date'],
                        'description': movement['description'],
                        'amount': amount,
                        'running_balance': float(movement.get('balance', 0)),
                        'transaction': movement.get('transaction'),  # Incluir objeto transaction para acesso a is_transfer e get_transfer_pair
                    })
    else:
        # Se não há account_id, inicializar totais como zero
        total_payments = Decimal('0')
        total_deposits = Decimal('0')
    
    # Buscar categorias para o formulário
    categories = Subcategory.objects.all().select_related('category').order_by('category__category', 'subcategory')
    
    return render(request, 'finance/account_statement.html', {
        'accounts': accounts,
        'account': account,
        'selected_account': account,  # Para compatibilidade
        'start_date': start_date,
        'end_date': end_date,
        'movements': movements,
        'transactions': transactions,
        'previous_balance': previous_balance,
        'final_balance': final_balance,
        'total_payments': total_payments,
        'total_deposits': total_deposits,
        'categories': categories,
        'today': today,
    })


def asset_stock_position_report(request):
    """Relatório de posição de estoque de ativos"""
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
    # Obter ano selecionado (query param ou ano atual)
    selected_year = int(request.GET.get('year', date.today().year))
    
    # Obter categoria selecionada (query param)
    selected_category_id_str = request.GET.get('category', '')
    selected_category_id = None
    
    # Obter todas as categorias para o dropdown
    categories = Category.objects.all().order_by('category')
    
    # Obter todas as subcategorias ordenadas por categoria/subcategoria
    subcategories = Subcategory.objects.all().select_related('category').order_by('category', 'subcategory')
    
    # Filtrar por categoria se selecionada
    if selected_category_id_str:
        try:
            selected_category_id = int(selected_category_id_str)
            subcategories = subcategories.filter(category_id=selected_category_id)
        except (ValueError, TypeError):
            selected_category_id = None  # Se category_id for inválido, mostrar todas
    
    
    # Buscar orçamentos do ano selecionado
    budgets = Budget.objects.filter(
        budget_date__year=selected_year
    ).select_related('subcategory', 'subcategory__category').order_by('subcategory', 'notes', 'budget_date')
    
    # Agrupar orçamentos por (subcategory, notes) - permite múltiplas linhas por subcategoria
    # key = (subcategory_id, notes_hash) -> lista de budgets
    budgets_by_row = {}
    for budget in budgets:
        # Usar hash das notes como identificador único da linha (None ou '' vira '')
        notes_key = budget.notes or ''
        # Criar hash simples para usar como identificador no formulário
        notes_hash = hashlib.md5(notes_key.encode('utf-8')).hexdigest()[:8] if notes_key else 'default'
        row_key = (budget.subcategory_id, notes_hash, notes_key)
        
        if row_key not in budgets_by_row:
            budgets_by_row[row_key] = {
                'notes': notes_key,
                'notes_hash': notes_hash,
                'budgets': {}
            }
        # Armazenar budget por mês
        budgets_by_row[row_key]['budgets'][budget.month] = budget
    
    # Otimizar: Calcular médias do ano anterior em uma única query
    previous_year = selected_year - 1
    subcategory_ids = [s.id for s in subcategories]
    avg_previous_dict = {}
    if subcategory_ids:
        avg_results = Budget.objects.filter(
            subcategory_id__in=subcategory_ids,
            budget_date__year=previous_year
        ).values('subcategory_id').annotate(avg=Avg('amount'))
        for result in avg_results:
            avg_previous_dict[result['subcategory_id']] = result['avg'] or Decimal('0.00')
    
    # Preparar dados para o template - agrupar por subcategoria primeiro
    budget_data = []
    for subcategory in subcategories:
        # Usar média calculada em bulk (muito mais rápido)
        avg_previous = avg_previous_dict.get(subcategory.id, Decimal('0.00'))
        
        # Buscar todas as linhas (rows) para esta subcategoria
        subcategory_rows = []
        for row_key, row_data in budgets_by_row.items():
            subcategory_id, notes_hash, notes = row_key
            if subcategory_id == subcategory.id:
                # Obter valores dos 12 meses para esta linha
                months_data = []
                total_year = Decimal('0.00')
                for month in range(1, 13):
                    budget = row_data['budgets'].get(month)
                    amount = budget.amount if budget else Decimal('0.00')
                    months_data.append({
                        'month': month,
                        'amount': amount,
                        'budget_id': budget.id if budget else None
                    })
                    total_year += amount
                
                subcategory_rows.append({
                    'notes': row_data['notes'],
                    'notes_hash': row_data['notes_hash'],
                    'months': months_data,
                    'total_year': total_year
                })
        
        # Se não houver nenhuma linha para esta subcategoria, criar uma linha vazia
        if not subcategory_rows:
            months_data = []
            for month in range(1, 13):
                months_data.append({
                    'month': month,
                    'amount': Decimal('0.00'),
                    'budget_id': None
                })
            subcategory_rows.append({
                'notes': '',
                'notes_hash': 'default',
                'months': months_data,
                'total_year': Decimal('0.00')
            })
        
        budget_data.append({
            'subcategory': subcategory,
            'default_transaction_type': subcategory.default_transaction_type,
            'avg_previous_year': avg_previous,
            'rows': subcategory_rows  # Múltiplas linhas por subcategoria
        })
    
    # Calcular totais separados por tipo
    totals_by_type = Budget.get_totals_by_type(selected_year)
    
    # Processar POST (salvar orçamento)
    if request.method == 'POST':
        
        year = int(request.POST.get('year', selected_year))
        
        
        with db_transaction.atomic():
            # Coletar todas as linhas (rows) por subcategoria
            # Formato dos campos: budget_{subcategory_id}_{notes_hash}_{month} e notes_{subcategory_id}_{notes_hash}
            rows_by_subcategory = {}
            
            for subcategory in subcategories:
                rows_by_subcategory[subcategory.id] = {}
                
                # Buscar todos os campos de anotações para esta subcategoria
                for key in request.POST.keys():
                    if key.startswith(f'notes_{subcategory.id}_'):
                        notes_hash = key.replace(f'notes_{subcategory.id}_', '')
                        notes = request.POST.get(key, '').strip()
                        rows_by_subcategory[subcategory.id][notes_hash] = {
                            'notes': notes,
                            'months': {}
                        }
                
                # Buscar todos os campos de valores para esta subcategoria
                for key in request.POST.keys():
                    if key.startswith(f'budget_{subcategory.id}_'):
                        # Formato: budget_{subcategory_id}_{notes_hash}_{month}
                        parts = key.split('_')
                        if len(parts) >= 4:
                            notes_hash = parts[2]
                            month = int(parts[3])
                            value = request.POST.get(key, '').strip()
                            
                            if notes_hash not in rows_by_subcategory[subcategory.id]:
                                rows_by_subcategory[subcategory.id][notes_hash] = {
                                    'notes': '',
                                    'months': {}
                                }
                            
                            rows_by_subcategory[subcategory.id][notes_hash]['months'][month] = value
            
            # Buscar todos os orçamentos existentes para este ano (para comparar e deletar os removidos)
            existing_budgets = Budget.objects.filter(
                budget_date__year=year,
                subcategory__in=subcategories
            )
            
            # Criar conjunto de (subcategory_id, month, notes) que foram enviados no POST
            submitted_budgets = set()
            
            # Processar cada subcategoria e suas linhas
            for subcategory in subcategories:
                if subcategory.id not in rows_by_subcategory:
                    # Se não há linhas enviadas para esta subcategoria, deletar todos os orçamentos dela
                    Budget.objects.filter(
                        subcategory=subcategory,
                        budget_date__year=year
                    ).delete()
                    continue
                
                for notes_hash, row_data in rows_by_subcategory[subcategory.id].items():
                    notes = row_data['notes']
                    
                    # Processar cada mês desta linha
                    for month in range(1, 13):
                        value = row_data['months'].get(month, '').strip()
                        budget_date = date(year, month, 1)
                        
                        if value:
                            try:
                                # Converter valor (tratar vírgula/ponto decimal)
                                value = value.replace(',', '.')
                                amount = Decimal(value)
                                
                                # Adicionar ao conjunto de budgets enviados
                                submitted_budgets.add((subcategory.id, month, notes))
                                
                                # Usar update_or_create para evitar problemas de constraint
                                Budget.objects.update_or_create(
                                    subcategory=subcategory,
                                    budget_date=budget_date,
                                    notes=notes,
                                    defaults={'amount': amount}
                                )
                            except (ValueError, InvalidOperation):
                                pass  # Ignorar valores inválidos
                        else:
                            # Se o campo estiver vazio, remover o orçamento específico desta linha
                            Budget.objects.filter(
                                subcategory=subcategory,
                                budget_date=budget_date,
                                notes=notes
                            ).delete()
                    
                    # Se a linha não tem valores nem anotações, remover todos os budgets desta linha
                    has_values = any(row_data['months'].get(m, '').strip() for m in range(1, 13))
                    if not has_values and not notes:
                        # Remover todos os budgets desta linha (mesmo notes_hash)
                        Budget.objects.filter(
                            subcategory=subcategory,
                            budget_date__year=year,
                            notes=notes
                        ).delete()
            
            # Deletar orçamentos que existem no banco mas não foram enviados no POST (linhas removidas)
            for budget in existing_budgets:
                key = (budget.subcategory_id, budget.month, budget.notes or '')
                if key not in submitted_budgets:
                    # Este orçamento não foi enviado no POST, então foi removido
                    budget.delete()
            
            
            messages.success(request, f'Orçamento de {year} salvo com sucesso!')
            
            # Preservar filtro de categoria no redirect
            redirect_url = f"{reverse('finance:budget_manage')}?year={year}"
            selected_category_id_post = request.POST.get('category', '')
            if selected_category_id_post:
                redirect_url += f"&category={selected_category_id_post}"
            
            return redirect(redirect_url)
    
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
        'selected_category_id': selected_category_id,
        'categories': categories,
        'years': years,
        'months': months,
        'totals_by_type': totals_by_type,
    }
    
    return render(request, 'finance/budget_manage.html', context)


# Budget CRUD Views
def budget_list(request):
    """Lista de orçamentos"""
    budgets = Budget.objects.all().select_related('subcategory__category').order_by('-budget_date', 'subcategory__category__category', 'subcategory__subcategory')
    
    # Filtros opcionais
    year = request.GET.get('year')
    category_id = request.GET.get('category')
    subcategory_id = request.GET.get('subcategory')
    
    if year:
        try:
            year = int(year)
            budgets = budgets.filter(budget_date__year=year)
        except ValueError:
            pass
    
    if category_id:
        try:
            category_id = int(category_id)
            budgets = budgets.filter(subcategory__category_id=category_id)
        except ValueError:
            pass
    
    if subcategory_id:
        try:
            subcategory_id = int(subcategory_id)
            budgets = budgets.filter(subcategory_id=subcategory_id)
        except ValueError:
            pass
    
    # Paginação
    paginator = Paginator(budgets, BUDGETS_PER_PAGE)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Contexto para filtros
    categories = Category.objects.all().order_by('category')
    subcategories = Subcategory.objects.all().select_related('category').order_by('category__category', 'subcategory')
    
    return render(request, 'finance/budget_list.html', {
        'page_obj': page_obj,
        'categories': categories,
        'subcategories': subcategories,
        'selected_year': year,
        'selected_category_id': category_id,
        'selected_subcategory_id': subcategory_id,
    })


def budget_create(request):
    """Criar novo orçamento"""
    if request.method == 'POST':
        form = BudgetForm(request.POST)
        if form.is_valid():
            budget = form.save(commit=False)
            # Garantir que budget_date sempre tenha dia = 1
            if budget.budget_date:
                budget.budget_date = budget.budget_date.replace(day=1)
            budget.save()
            messages.success(request, 'Orçamento criado com sucesso!')
            return redirect('finance:budget_list')
    else:
        form = BudgetForm()
    return render(request, 'finance/budget_form.html', {'form': form})


def budget_update(request, pk):
    """Editar orçamento existente"""
    budget = get_object_or_404(Budget, pk=pk)
    if request.method == 'POST':
        form = BudgetForm(request.POST, instance=budget)
        if form.is_valid():
            budget = form.save(commit=False)
            # Garantir que budget_date sempre tenha dia = 1
            if budget.budget_date:
                budget.budget_date = budget.budget_date.replace(day=1)
            budget.save()
            messages.success(request, 'Orçamento atualizado com sucesso!')
            return redirect('finance:budget_list')
    else:
        form = BudgetForm(instance=budget)
    return render(request, 'finance/budget_form.html', {'form': form, 'budget': budget})


def budget_delete(request, pk):
    """Deletar orçamento"""
    budget = get_object_or_404(Budget, pk=pk)
    if request.method == 'POST':
        budget.delete()
        messages.success(request, 'Orçamento deletado com sucesso!')
        return redirect('finance:budget_list')
    return render(request, 'finance/budget_confirm_delete.html', {'budget': budget})


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
            rule_type = rule.get('type', 'subcategory')  # Default para 'subcategory' se não especificado (compatibilidade)
            if rule_type == 'subcategory':
                rule_data = {
                    'rule_type': 'subcategory',
                    'subcategory': rule.get('subcategory_id')
                }
                initial_data.append(rule_data)
            elif rule_type == 'transfer':
                # Compatibilidade com regras antigas que usam 'direction'
                value_type = rule.get('value_type')
                if not value_type and rule.get('direction'):
                    direction = rule.get('direction')
                    # Migrar: 'to' -> 'credit', 'from' -> 'debit'
                    value_type = 'credit' if direction == 'to' else 'debit'
                
                rule_data = {
                    'rule_type': 'transfer',
                    'destination_account': rule.get('destination_account_id'),
                    'value_type': value_type
                }
                initial_data.append(rule_data)
            elif rule_type == 'asset_transaction':
                rule_data = {
                    'rule_type': 'asset_transaction',
                    'operation_type': rule.get('operation_type', ''),
                    'asset_type': rule.get('asset_type', ''),
                    'asset_value_type': rule.get('asset_value_type', 'net_value')
                }
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
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    account_id = request.GET.get('account')
    include_future = request.GET.get('include_future') in ('1', 'on', 'true')

    if not start_date:
        today = date.today()
        start_date = date(today.year, today.month, 1).isoformat()
    if not end_date:
        end_date = date.today().isoformat()

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

    all_items = CashFlowItem.objects.all().order_by('order', 'code')
    report_data = []
    for item in all_items:
        value = item.calculate_value(start_date, end_date, account)
        budget_value = item.calculate_budget_value(start_date, end_date, account)
        accumulates_in_code = item.accumulates_in.code if item.accumulates_in else None
        level = item.code.count('.')
        has_children = item.get_children().exists()
        parent_code = item.get_parent_code()

        row = {
            'item': item,
            'code': item.code,
            'description': item.description,
            'value': value,
            'budget_value': budget_value,
            'accumulates_in_code': accumulates_in_code,
            'level': level,
            'has_children': has_children,
            'parent_code': parent_code,
        }
        if include_future:
            scheduled_value = item.calculate_scheduled_value(start_date, end_date, account)
            row['scheduled_value'] = scheduled_value
            row['scheduled_accumulated_value'] = scheduled_value
        report_data.append(row)

    for data in report_data:
        data['accumulated_value'] = data['value']
        data['budget_accumulated_value'] = data['budget_value']

    total_general = Decimal('0')
    total_budget_general = Decimal('0')
    total_scheduled_general = Decimal('0')
    root_items = [d for d in report_data if d['level'] == 0]
    if root_items:
        total_general = root_items[-1]['accumulated_value']
        total_budget_general = root_items[-1]['budget_accumulated_value']
        if include_future:
            total_scheduled_general = root_items[-1].get('scheduled_accumulated_value', Decimal('0'))
    else:
        for data in report_data:
            total_general += data['value']
            total_budget_general += data['budget_value']
            if include_future:
                total_scheduled_general += data.get('scheduled_value', Decimal('0'))

    if include_future:
        for data in report_data:
            data['projected_value'] = data['accumulated_value'] + data.get('scheduled_accumulated_value', Decimal('0'))
        total_projected_general = total_general + total_scheduled_general
    else:
        total_projected_general = total_general

    accounts = Account.objects.all()

    return render(request, 'finance/cash_flow_report.html', {
        'report_data': report_data,
        'start_date': start_date,
        'end_date': end_date,
        'selected_account': account,
        'accounts': accounts,
        'total_general': total_general,
        'total_budget_general': total_budget_general,
        'include_future': include_future,
        'total_scheduled_general': total_scheduled_general,
        'total_projected_general': total_projected_general,
    })


# Transactions Import Views
def transactions_import_upload(request):
    """View para upload e parsing inicial do arquivo de transações"""
    if request.method == 'POST':
        form = TransactionsImportForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = request.FILES['file']
            
            try:
                # Parsear arquivo
                transactions_data = TransactionsParser.parse_file(uploaded_file)
                
                if not transactions_data:
                    messages.error(request, 'Nenhuma transação válida encontrada no arquivo.')
                    return render(request, 'finance/transactions_import_upload.html', {'form': form})
                
                # Adicionar índice original e inicializar campo selected
                for idx, trans in enumerate(transactions_data):
                    trans['original_index'] = idx
                    # Inicializar campo selected como True por padrão
                    trans['selected'] = True
                
                # Converter objetos date e Decimal para strings antes de salvar na sessão
                # Armazenar na sessão
                request.session['transactions_staging_data'] = prepare_transactions_for_session(transactions_data)
                request.session['transactions_staging_count'] = len(transactions_data)
                request.session.modified = True  # Garantir que a sessão seja salva
                
                messages.success(request, f'{len(transactions_data)} transações parseadas com sucesso!')
                return redirect('finance:transactions_import_staging')
            except Exception as e:
                error_trace = traceback.format_exc()
                messages.error(request, f'Erro ao processar arquivo: {str(e)}')
                # Log do erro para debug
                print(f"Erro ao processar arquivo de transações: {error_trace}")
    else:
        form = TransactionsImportForm()
    
    return render(request, 'finance/transactions_import_upload.html', {'form': form})


def transactions_import_staging(request):
    """View para exibir transações em staging com filtros"""
    # Verificar se há dados na sessão
    if 'transactions_staging_data' not in request.session:
        messages.warning(request, 'Nenhum arquivo carregado. Por favor, faça o upload do arquivo primeiro.')
        return redirect('finance:transactions_import_upload')
    
    # Debug: verificar se os dados estão na sessão
    if not request.session.get('transactions_staging_data'):
        messages.error(request, 'Erro: Dados da sessão não encontrados após upload.')
        return redirect('finance:transactions_import_upload')
    
    # Recuperar dados da sessão
    transactions_data = request.session['transactions_staging_data'].copy()
    
    # Converter strings de volta para objetos date e Decimal
    for trans in transactions_data:
        if trans.get('transaction_date'):
            try:
                trans['transaction_date'] = datetime.strptime(trans['transaction_date'], '%Y-%m-%d').date()
            except (ValueError, TypeError):
                trans['transaction_date'] = None
        if trans.get('value'):
            try:
                trans['value'] = Decimal(str(trans['value']))
            except (ValueError, TypeError):
                trans['value'] = Decimal('0')
    
    # Verificar status de importação para todas as transações
    # Coletar todos os import_hash e verificar quais já existem no banco
    all_import_hashes = [t.get('import_hash') for t in transactions_data if t.get('import_hash')]
    imported_hashes_set = set()
    if all_import_hashes:
        imported_hashes_set = set(
            Transaction.objects.filter(import_hash__in=all_import_hashes)
            .values_list('import_hash', flat=True)
        )
    
    # Adicionar campo is_imported a cada transação
    for trans in transactions_data:
        trans['is_imported'] = trans.get('import_hash') in imported_hashes_set
    
    # Inicializar campo 'selected' se não existir (padrão: True)
    for trans in transactions_data:
        if 'selected' not in trans:
            trans['selected'] = True
        elif isinstance(trans.get('selected'), str):
            trans['selected'] = trans['selected'].lower() in ('true', '1', 'yes')
    
    
    # Aplicar filtros
    filter_form = TransactionsStagingFilterForm(request.GET)
    filtered_transactions = transactions_data.copy()
    
    if filter_form.is_valid():
        date_start = filter_form.cleaned_data.get('date_start')
        date_end = filter_form.cleaned_data.get('date_end')
        account_filter = filter_form.cleaned_data.get('account', '').lower()
        beneficiary_filter = filter_form.cleaned_data.get('beneficiary', '').lower()
        category_filter = filter_form.cleaned_data.get('category', '').lower()
        transaction_type_filter = filter_form.cleaned_data.get('transaction_type')
        min_value = filter_form.cleaned_data.get('min_value')
        max_value = filter_form.cleaned_data.get('max_value')
        import_status_filter = filter_form.cleaned_data.get('import_status')
        
        filtered_transactions = []
        for trans in transactions_data:
            # Filtro de data
            if date_start and trans.get('transaction_date'):
                if trans['transaction_date'] < date_start:
                    continue
            if date_end and trans.get('transaction_date'):
                if trans['transaction_date'] > date_end:
                    continue
            
            # Filtro de conta
            if account_filter:
                if account_filter not in trans.get('account', '').lower():
                    continue
            
            # Filtro de beneficiário
            if beneficiary_filter:
                if beneficiary_filter not in trans.get('beneficiary', '').lower():
                    continue
            
            # Filtro de categoria
            if category_filter:
                cat = trans.get('category', '') or ''
                subcat = trans.get('subcategory', '') or ''
                if category_filter not in cat.lower() and category_filter not in subcat.lower():
                    continue
            
            # Filtro de tipo
            if transaction_type_filter:
                if trans.get('transaction_type') != transaction_type_filter:
                    continue
            
            # Filtro de valor
            if min_value is not None:
                if trans.get('value', Decimal('0')) < min_value:
                    continue
            if max_value is not None:
                if trans.get('value', Decimal('0')) > max_value:
                    continue
            
            # Filtro de status de importação
            if import_status_filter:
                is_imported = trans.get('is_imported', False)
                if import_status_filter == 'imported' and not is_imported:
                    continue
                if import_status_filter == 'not_imported' and is_imported:
                    continue
            
            filtered_transactions.append(trans)
    
    # Atualizar seleção na sessão se houver POST (para manter estado entre páginas)
    if request.method == 'POST':
        selected_indices = request.POST.getlist('selected_indices')
        selected_indices = [int(i) for i in selected_indices if i.isdigit()]
        # Atualizar estado de seleção nos dados originais
        for idx, trans in enumerate(transactions_data):
            trans['selected'] = idx in selected_indices
        
        # Converter objetos date e Decimal de volta para strings antes de salvar na sessão
        request.session['transactions_staging_data'] = prepare_transactions_for_session(transactions_data)
        request.session.modified = True
    
    # Contar selecionadas
    # Se há filtros aplicados, considerar apenas as explicitamente marcadas (selected=True)
    # Se não há filtros, considerar o padrão (selected=True por padrão)
    has_filters = bool(filter_form.is_valid() and any([
        filter_form.cleaned_data.get('date_start'),
        filter_form.cleaned_data.get('date_end'),
        filter_form.cleaned_data.get('account'),
        filter_form.cleaned_data.get('beneficiary'),
        filter_form.cleaned_data.get('category'),
        filter_form.cleaned_data.get('transaction_type'),
        filter_form.cleaned_data.get('min_value') is not None,
        filter_form.cleaned_data.get('max_value') is not None,
        filter_form.cleaned_data.get('import_status'),
    ]))
    
    if has_filters:
        # Com filtros: contar apenas as explicitamente marcadas
        selected_count = sum(1 for t in filtered_transactions if t.get('selected', False))
    else:
        # Sem filtros: contar todas (padrão selected=True)
        selected_count = sum(1 for t in filtered_transactions if t.get('selected', True))
    
    # Salvar estado atualizado na sessão
    # Converter objetos date e Decimal de volta para strings antes de salvar na sessão
    request.session['transactions_staging_data'] = prepare_transactions_for_session(transactions_data)
    request.session.modified = True
    
    
    # Paginação
    paginator = Paginator(filtered_transactions, IMPORT_STAGING_TRANSACTIONS_PER_PAGE)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    
    # Extrair todas as contas únicas das transações
    unique_accounts = set()
    for trans in transactions_data:
        account_name = trans.get('account', '')
        if account_name:
            normalized = TransactionsParser.normalize_name(account_name)
            if normalized:
                unique_accounts.add(normalized)
        
        # Para transferências, incluir também source_account e destination_account
        if trans.get('is_transfer'):
            source_account = trans.get('source_account', '')
            destination_account = trans.get('destination_account', '')
            if source_account:
                normalized = TransactionsParser.normalize_name(source_account)
                if normalized:
                    unique_accounts.add(normalized)
            if destination_account:
                normalized = TransactionsParser.normalize_name(destination_account)
                if normalized:
                    unique_accounts.add(normalized)
    
    # Ordenar contas alfabeticamente
    unique_accounts = sorted(unique_accounts)
    
    return render(request, 'finance/transactions_import_staging.html', {
        'transactions': page_obj,
        'filter_form': filter_form,
        'total_count': len(transactions_data),
        'filtered_count': len(filtered_transactions),
        'selected_count': selected_count,
        'unique_accounts': unique_accounts,
    })


def transactions_import_edit_item(request):
    """View AJAX para editar item individual em staging"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método não permitido'}, status=405)
    
    try:
        data = json.loads(request.body)
        index = data.get('index')
        field = data.get('field')
        value = data.get('value')
        
        if 'transactions_staging_data' not in request.session:
            return JsonResponse({'success': False, 'error': 'Nenhum dado em staging'}, status=400)
        
        transactions_data = request.session['transactions_staging_data']
        
        # Encontrar transação pelo original_index
        trans = None
        for t in transactions_data:
            if t.get('original_index') == index:
                trans = t
                break
        
        if trans is None:
            return JsonResponse({'success': False, 'error': 'Transação não encontrada'}, status=400)
        
        # Preservar import_hash original (nunca deve ser alterado)
        original_import_hash = trans.get('import_hash')
        
        # Validar e converter valor conforme o campo
        if field == 'import_hash':
            # Não permitir edição do import_hash - ele deve permanecer baseado nos valores originais
            return JsonResponse({'success': False, 'error': 'Campo import_hash não pode ser editado'}, status=400)
        elif field == 'transaction_date':
            try:
                # Aceitar formato YYYY-MM-DD
                trans['transaction_date'] = datetime.strptime(value, '%Y-%m-%d').date().isoformat()
            except ValueError:
                return JsonResponse({'success': False, 'error': 'Data inválida'}, status=400)
        elif field == 'value':
            try:
                trans['value'] = str(Decimal(str(value)))
            except (ValueError, InvalidOperation):
                return JsonResponse({'success': False, 'error': 'Valor inválido'}, status=400)
        elif field in ['account', 'beneficiary', 'memo', 'category', 'subcategory']:
            trans[field] = str(value)
        elif field == 'transaction_type':
            if value not in [TRANSACTION_TYPE_CR, TRANSACTION_TYPE_DB]:
                return JsonResponse({'success': False, 'error': 'Tipo inválido'}, status=400)
            trans['transaction_type'] = value
        elif field == 'selected':
            # Atualizar estado de seleção
            trans['selected'] = bool(value)
        else:
            return JsonResponse({'success': False, 'error': 'Campo inválido'}, status=400)
        
        if field != 'selected':
            trans['edited'] = True
        
        # Garantir que import_hash original seja preservado (nunca alterado)
        if original_import_hash:
            trans['import_hash'] = original_import_hash
        
        # Garantir que dados estão no formato correto para sessão
        # IMPORTANTE: Preservar import_hash antes de preparar para sessão
        original_hash_before = trans.get('import_hash')
        request.session['transactions_staging_data'] = prepare_transactions_for_session(transactions_data)
        request.session.modified = True
        
        
        return JsonResponse({'success': True, 'message': 'Item atualizado com sucesso'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def transactions_import_select_all(request):
    """View AJAX para marcar todas as transações de uma vez"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método não permitido'}, status=405)
    
    try:
        if 'transactions_staging_data' not in request.session:
            return JsonResponse({'success': False, 'error': 'Nenhum dado em staging'}, status=400)
        
        transactions_data = request.session['transactions_staging_data']
        
        # Marcar todas as transações
        for trans in transactions_data:
            trans['selected'] = True
        
        # Garantir que dados estão no formato correto para sessão
        request.session['transactions_staging_data'] = prepare_transactions_for_session(transactions_data)
        request.session.modified = True
        
        return JsonResponse({
            'success': True,
            'message': f'Todas as {len(transactions_data)} transações foram marcadas'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def transactions_import_deselect_all(request):
    """View AJAX para desmarcar todas as transações de uma vez"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método não permitido'}, status=405)
    
    try:
        if 'transactions_staging_data' not in request.session:
            return JsonResponse({'success': False, 'error': 'Nenhum dado em staging'}, status=400)
        
        transactions_data = request.session['transactions_staging_data']
        
        # Desmarcar todas as transações
        for trans in transactions_data:
            trans['selected'] = False
        
        # Garantir que dados estão no formato correto para sessão
        request.session['transactions_staging_data'] = prepare_transactions_for_session(transactions_data)
        request.session.modified = True
        
        return JsonResponse({
            'success': True,
            'message': f'Todas as {len(transactions_data)} transações foram desmarcadas'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def transactions_import_remove_item(request):
    """View AJAX para remover item do staging"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método não permitido'}, status=405)
    
    try:
        data = json.loads(request.body)
        indices = data.get('indices', [])
        
        if 'transactions_staging_data' not in request.session:
            return JsonResponse({'success': False, 'error': 'Nenhum dado em staging'}, status=400)
        
        transactions_data = request.session['transactions_staging_data']
        
        # Remover transações pelos original_index
        indices_to_remove = set(indices)
        transactions_data = [t for t in transactions_data if t.get('original_index') not in indices_to_remove]
        
        # Reindexar original_index após remoção
        for idx, trans in enumerate(transactions_data):
            trans['original_index'] = idx
        
        # Garantir que dados estão no formato correto para sessão
        request.session['transactions_staging_data'] = prepare_transactions_for_session(transactions_data)
        request.session['transactions_staging_count'] = len(transactions_data)
        request.session.modified = True
        
        return JsonResponse({'success': True, 'message': f'{len(indices)} item(ns) removido(s)'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def transactions_import_execute(request):
    """View para executar importação final das transações selecionadas"""
    
    if request.method != 'POST':
        messages.error(request, 'Método não permitido')
        return redirect('finance:transactions_import_staging')
    
    try:
        data = json.loads(request.body)
        selected_indices = data.get('selected_indices', [])
        filters = data.get('filters')  # Filtros aplicados na página de staging
        
        
        if 'transactions_staging_data' not in request.session:
            messages.error(request, 'Nenhum dado em staging')
            return redirect('finance:transactions_import_upload')
        
        transactions_data = request.session['transactions_staging_data']
        
        
        # Converter strings de volta para objetos date e Decimal para aplicar filtros
        selected_count_before_conversion = 0
        selected_as_string_count = 0
        missing_selected_count = 0
        for trans in transactions_data:
            if trans.get('transaction_date') and isinstance(trans['transaction_date'], str):
                try:
                    trans['transaction_date'] = datetime.strptime(trans['transaction_date'], '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    trans['transaction_date'] = None
            if trans.get('value') and isinstance(trans['value'], str):
                try:
                    trans['value'] = Decimal(str(trans['value']))
                except (ValueError, TypeError):
                    trans['value'] = Decimal('0')
            # Garantir que campo 'selected' existe e é booleano
            if 'selected' not in trans:
                missing_selected_count += 1
                trans['selected'] = True  # Padrão: selecionado
            elif isinstance(trans.get('selected'), str):
                selected_as_string_count += 1
                trans['selected'] = trans['selected'].lower() in ('true', '1', 'yes')
            if trans.get('selected'):
                selected_count_before_conversion += 1
        
        
        # Aplicar filtros se fornecidos (mesmos filtros da página de staging)
        if filters:
            
            filtered_transactions = []
            filtered_count = 0
            for trans in transactions_data:
                # Filtro de data
                if filters.get('date_start') and trans.get('transaction_date'):
                    try:
                        date_start = datetime.strptime(filters['date_start'], '%Y-%m-%d').date()
                        if trans['transaction_date'] < date_start:
                            continue
                    except (ValueError, TypeError):
                        pass
                if filters.get('date_end') and trans.get('transaction_date'):
                    try:
                        date_end = datetime.strptime(filters['date_end'], '%Y-%m-%d').date()
                        if trans['transaction_date'] > date_end:
                            continue
                    except (ValueError, TypeError):
                        pass
                
                # Filtro de conta
                if filters.get('account'):
                    account_filter = filters['account'].lower()
                    if account_filter not in trans.get('account', '').lower():
                        continue
                
                # Filtro de beneficiário
                if filters.get('beneficiary'):
                    beneficiary_filter = filters['beneficiary'].lower()
                    if beneficiary_filter not in trans.get('beneficiary', '').lower():
                        continue
                
                # Filtro de categoria
                if filters.get('category'):
                    category_filter = filters['category'].lower()
                    cat = trans.get('category', '') or ''
                    subcat = trans.get('subcategory', '') or ''
                    if category_filter not in cat.lower() and category_filter not in subcat.lower():
                        continue
                
                # Filtro de tipo
                if filters.get('transaction_type'):
                    if trans.get('transaction_type') != filters['transaction_type']:
                        continue
                
                # Filtro de valor
                if filters.get('min_value'):
                    try:
                        min_value = Decimal(str(filters['min_value']))
                        if trans.get('value', Decimal('0')) < min_value:
                            continue
                    except (ValueError, TypeError):
                        pass
                if filters.get('max_value'):
                    try:
                        max_value = Decimal(str(filters['max_value']))
                        if trans.get('value', Decimal('0')) > max_value:
                            continue
                    except (ValueError, TypeError):
                        pass
                
                filtered_transactions.append(trans)
                filtered_count += 1
                
            
            
            # Usar apenas transações filtradas para verificar seleção
            transactions_to_check = filtered_transactions
        else:
            # Sem filtros, usar todas as transações
            transactions_to_check = transactions_data
        
        
        # Filtrar apenas transações selecionadas
        # Se selected_indices estiver vazio, importar todas com selected=True (mas apenas das filtradas, se houver filtros)
        # Caso contrário, importar apenas as especificadas nos índices
        selected_transactions = []
        
        
        checked_count = 0
        included_count = 0
        # Determinar default para selected baseado em se há filtros
        # Sem filtros: default é True (todas selecionadas por padrão)
        # Com filtros: default é False (apenas explicitamente selecionadas)
        default_selected = not bool(filters)
        
        
        for trans in transactions_to_check:
            checked_count += 1
            # Se lista vazia, usar campo 'selected'; senão, verificar índices
            should_include = False
            if not selected_indices:
                # Lista vazia = importar todas as selecionadas
                # Converter selected para booleano se necessário (pode vir como string da sessão)
                selected_value = trans.get('selected', default_selected)
                if isinstance(selected_value, str):
                    should_include = selected_value.lower() in ('true', '1', 'yes')
                else:
                    should_include = bool(selected_value)
            else:
                # Lista com índices = importar apenas essas
                should_include = trans.get('original_index') in selected_indices
            
            
            if should_include:
                trans_copy = trans.copy()
                # Converter strings de volta para objetos (se necessário)
                if trans_copy.get('transaction_date'):
                    # Se já é um objeto date, não precisa converter
                    if isinstance(trans_copy['transaction_date'], str):
                        try:
                            trans_copy['transaction_date'] = datetime.strptime(trans_copy['transaction_date'], '%Y-%m-%d').date()
                        except (ValueError, TypeError):
                            continue
                    # Se já é date, manter como está
                if trans_copy.get('value'):
                    # Se já é Decimal, não precisa converter
                    if isinstance(trans_copy['value'], str):
                        try:
                            trans_copy['value'] = Decimal(str(trans_copy['value']))
                        except (ValueError, TypeError):
                            continue
                    # Se já é Decimal, manter como está
                
                
                selected_transactions.append(trans_copy)
                included_count += 1
        
        
        if not selected_transactions:
            messages.warning(request, 'Nenhuma transação selecionada para importar')
            return redirect('finance:transactions_import_staging')
        
        # Filtrar transações de contas de investimento
        # Buscar todas as contas do tipo INVEST do banco de dados
        investment_accounts_queryset = Account.objects.filter(account_type='INVEST')
        investment_accounts_set = set()
        for account in investment_accounts_queryset:
            normalized = TransactionsParser.normalize_name(account.name)
            if normalized:
                investment_accounts_set.add(normalized)
        
        filtered_by_investment = []
        if investment_accounts_set:
            original_count = len(selected_transactions)
            filtered_transactions = []
            for trans_data in selected_transactions:
                should_filter = False
                
                # Verificar conta principal
                account_name = TransactionsParser.normalize_name(trans_data.get('account', ''))
                if account_name in investment_accounts_set:
                    should_filter = True
                
                # Para transferências, verificar também source_account e destination_account
                if trans_data.get('is_transfer'):
                    source_account = TransactionsParser.normalize_name(trans_data.get('source_account', ''))
                    destination_account = TransactionsParser.normalize_name(trans_data.get('destination_account', ''))
                    if source_account in investment_accounts_set or destination_account in investment_accounts_set:
                        should_filter = True
                
                if not should_filter:
                    filtered_transactions.append(trans_data)
                else:
                    filtered_by_investment.append(trans_data)
            
            selected_transactions = filtered_transactions
            filtered_count = len(filtered_by_investment)
            
        
        # Estatísticas
        stats = {
            'created_accounts': 0,
            'created_beneficiaries': 0,
            'created_categories': 0,
            'created_subcategories': 0,
            'created_transactions': 0,
            'errors': [],
            'duplicates': 0,
            'filtered_by_investment': len(filtered_by_investment),
        }
        
        # Processar transações
        
        with db_transaction.atomic():
            batch_size = TRANSACTIONS_IMPORT_BATCH_SIZE
            transactions_to_create = []
            
            # OTIMIZAÇÃO: Pré-coletar todos os nomes únicos para evitar queries repetidas
            unique_account_names = set()
            unique_beneficiary_names = set()
            unique_category_names = set()
            unique_subcategory_keys = set()  # (category_name, subcategory_name)
            
            for trans_data in selected_transactions:
                # Coletar nomes de contas
                account_name = TransactionsParser.normalize_name(trans_data.get('account', ''))
                if account_name:
                    unique_account_names.add(account_name)
                
                # Coletar nomes de beneficiários
                if trans_data.get('beneficiary'):
                    beneficiary_name = TransactionsParser.normalize_name(trans_data['beneficiary'])
                    if beneficiary_name:
                        unique_beneficiary_names.add(beneficiary_name)
                
                # Coletar categorias e subcategorias
                if trans_data.get('category'):
                    category_name = TransactionsParser.normalize_name(trans_data['category'])
                    unique_category_names.add(category_name)
                    if trans_data.get('subcategory'):
                        subcategory_name = TransactionsParser.normalize_name(trans_data['subcategory'])
                        unique_subcategory_keys.add((category_name, subcategory_name))
                
                # Para transferências, coletar contas de origem e destino
                if trans_data.get('is_transfer'):
                    source_account_name = TransactionsParser.normalize_name(trans_data.get('source_account', ''))
                    destination_account_name = TransactionsParser.normalize_name(trans_data.get('destination_account', ''))
                    if source_account_name:
                        unique_account_names.add(source_account_name)
                    if destination_account_name:
                        unique_account_names.add(destination_account_name)
            
            # OTIMIZAÇÃO: Buscar todos os objetos existentes em batch
            accounts_cache = {acc.name: acc for acc in Account.objects.filter(name__in=unique_account_names)}
            beneficiaries_cache = {ben.full_name: ben for ben in Beneficiary.objects.filter(full_name__in=unique_beneficiary_names)}
            categories_cache = {cat.category: cat for cat in Category.objects.filter(category__in=unique_category_names)}
            
            # Buscar subcategorias existentes (precisa fazer join com categories)
            existing_subcategories = Subcategory.objects.filter(
                category__category__in=unique_category_names
            ).select_related('category')
            subcategories_cache = {}
            for subcat in existing_subcategories:
                key = (subcat.category.category, subcat.subcategory)
                subcategories_cache[key] = subcat
            
            # OTIMIZAÇÃO: Criar objetos que não existem em batch
            accounts_to_create = []
            for account_name in unique_account_names:
                if account_name not in accounts_cache:
                    accounts_to_create.append(Account(
                        name=account_name,
                        account_type=TransactionsParser.infer_account_type(account_name),
                        currency='Real brasileiro',
                        opening_balance=Decimal('0'),
                    ))
            
            if accounts_to_create:
                created_accounts = Account.objects.bulk_create(accounts_to_create, ignore_conflicts=True)
                for acc in created_accounts:
                    accounts_cache[acc.name] = acc
                    stats['created_accounts'] += 1
            
            beneficiaries_to_create = []
            for beneficiary_name in unique_beneficiary_names:
                if beneficiary_name not in beneficiaries_cache:
                    beneficiaries_to_create.append(Beneficiary(full_name=beneficiary_name))
            
            if beneficiaries_to_create:
                created_beneficiaries = Beneficiary.objects.bulk_create(beneficiaries_to_create, ignore_conflicts=True)
                for ben in created_beneficiaries:
                    beneficiaries_cache[ben.full_name] = ben
                    stats['created_beneficiaries'] += 1
            
            categories_to_create = []
            for category_name in unique_category_names:
                if category_name not in categories_cache:
                    categories_to_create.append(Category(category=category_name))
            
            if categories_to_create:
                created_categories = Category.objects.bulk_create(categories_to_create, ignore_conflicts=True)
                for cat in created_categories:
                    categories_cache[cat.category] = cat
                    stats['created_categories'] += 1
            
            # Subcategorias serão criadas durante o loop principal quando necessário
            # porque precisamos do transaction_type de cada transação
            
            # Coletar todos os import_hash que serão criados para verificação em lote
            # Isso evita verificar duplicatas uma por uma dentro do loop
            # Para transferências, precisamos gerar os hashes antecipadamente e armazená-los
            all_import_hashes = []
            transfer_hashes_cache = {}  # Cache para armazenar hashes de transferências por índice
            
            # Coletar hashes de transações normais (após criar caches)
            missing_hash_in_selected = 0
            regenerated_hash_count = 0
            for idx, t in enumerate(selected_transactions):
                if t.get('import_hash'):
                    all_import_hashes.append(t.get('import_hash'))
                elif t.get('is_transfer'):
                    # Transferências geram hash depois no loop principal
                    pass
                else:
                    # CORREÇÃO: Regenerar hash para transações normais que perderam o hash
                    missing_hash_in_selected += 1
                    
                    # Regenerar hash para transação normal
                    try:
                        account_name = TransactionsParser.normalize_name(t.get('account', ''))
                        beneficiary_name = TransactionsParser.normalize_name(t.get('beneficiary', '')) if t.get('beneficiary') else None
                        category_name = TransactionsParser.normalize_name(t.get('category', '')) if t.get('category') else None
                        subcategory_name = TransactionsParser.normalize_name(t.get('subcategory', '')) if t.get('subcategory') else None
                        
                        regenerated_hash = TransactionsParser.generate_import_hash(
                            date=t.get('transaction_date'),
                            beneficiary=beneficiary_name,
                            account=account_name,
                            memo=t.get('memo', ''),
                            category=category_name,
                            subcategory=subcategory_name,
                            value=t.get('value', Decimal('0')),
                            is_transfer=False,
                            line_num=t.get('line_num')
                        )
                        
                        # Atualizar o hash na transação
                        t['import_hash'] = regenerated_hash
                        all_import_hashes.append(regenerated_hash)
                        regenerated_hash_count += 1
                        
                    except Exception as e:
                        # Se não conseguir regenerar, a transação será pulada no loop principal
                        pass
            
            
            # Verificar hashes existentes no banco de dados
            # Dividir em lotes para evitar problemas com muitas variáveis SQL
            existing_hashes_set = set()
            if all_import_hashes:
                hash_batch_size = 1000  # Processar em lotes de 1000 hashes
                for i in range(0, len(all_import_hashes), hash_batch_size):
                    batch = all_import_hashes[i:i + hash_batch_size]
                    existing_hashes_set.update(
                        Transaction.objects.filter(import_hash__in=batch)
                        .values_list('import_hash', flat=True)
                    )
            
            # Set para rastrear hashes do lote atual (evita duplicatas dentro do mesmo lote)
            batch_hashes_set = set()
            
            
            total_transactions = len(selected_transactions)
            for i, trans_data in enumerate(selected_transactions, 1):
                # Log de progresso a cada N transações
                if i % TRANSACTIONS_IMPORT_PROGRESS_LOG_INTERVAL == 0:
                    logger.debug('Import progress: %s / %s', i, total_transactions)
                
                try:
                    # OTIMIZAÇÃO: Usar cache em vez de get_or_create
                    account_name = TransactionsParser.normalize_name(trans_data['account'])
                    if not account_name:
                        stats['errors'].append(f'Linha {trans_data.get("line_num", "?")}: Conta vazia')
                        continue

                    account = accounts_cache.get(account_name)
                    if not account:
                        # Se não está no cache, criar (não deveria acontecer, mas por segurança)
                        account, created = Account.objects.get_or_create(
                            name=account_name,
                            defaults={
                                'account_type': TransactionsParser.infer_account_type(account_name),
                                'currency': 'Real brasileiro',
                                'opening_balance': Decimal('0'),
                            }
                        )
                        accounts_cache[account_name] = account
                        if created:
                            stats['created_accounts'] += 1

                    # OTIMIZAÇÃO: Usar cache para Beneficiary
                    beneficiary = None
                    if trans_data.get('beneficiary'):
                        beneficiary_name = TransactionsParser.normalize_name(trans_data['beneficiary'])
                        beneficiary = beneficiaries_cache.get(beneficiary_name)
                        if not beneficiary:
                            # Se não está no cache, criar
                            beneficiary, created = Beneficiary.objects.get_or_create(
                                full_name=beneficiary_name
                            )
                            beneficiaries_cache[beneficiary_name] = beneficiary
                            if created:
                                stats['created_beneficiaries'] += 1

                    # OTIMIZAÇÃO: Usar cache para Category e Subcategory
                    subcategory = None
                    if trans_data.get('category'):
                        category_name = TransactionsParser.normalize_name(trans_data['category'])
                        category = categories_cache.get(category_name)
                        if not category:
                            # Se não está no cache, criar
                            category, created = Category.objects.get_or_create(
                                category=category_name
                            )
                            categories_cache[category_name] = category
                            if created:
                                stats['created_categories'] += 1

                        if trans_data.get('subcategory'):
                            subcategory_name = TransactionsParser.normalize_name(trans_data['subcategory'])
                            subcategory_key = (category_name, subcategory_name)
                            subcategory = subcategories_cache.get(subcategory_key)
                            if not subcategory:
                                # Se não está no cache, criar
                                subcategory, created = Subcategory.objects.get_or_create(
                                    category=category,
                                    subcategory=subcategory_name,
                                    defaults={
                                        'default_transaction_type': trans_data['transaction_type'],
                                    }
                                )
                                subcategories_cache[subcategory_key] = subcategory
                                if created:
                                    stats['created_subcategories'] += 1

                    # Verificar se é transferência
                    is_transfer = trans_data.get('is_transfer', False)
                    
                    if is_transfer:
                        # Processar transferência entre contas
                        source_account_name = TransactionsParser.normalize_name(trans_data.get('source_account', ''))
                        destination_account_name = TransactionsParser.normalize_name(trans_data.get('destination_account', ''))
                        
                        if not source_account_name or not destination_account_name:
                            stats['errors'].append(f'Linha {trans_data.get("line_num", "?")}: Contas de origem/destino não encontradas na transferência')
                            continue
                        
                        # OTIMIZAÇÃO: Usar cache para contas de transferência
                        source_account = accounts_cache.get(source_account_name)
                        if not source_account:
                            source_account, created = Account.objects.get_or_create(
                                name=source_account_name,
                                defaults={
                                    'account_type': TransactionsParser.infer_account_type(source_account_name),
                                    'currency': 'Real brasileiro',
                                    'opening_balance': Decimal('0'),
                                }
                            )
                            accounts_cache[source_account_name] = source_account
                            if created:
                                stats['created_accounts'] += 1
                        
                        destination_account = accounts_cache.get(destination_account_name)
                        if not destination_account:
                            destination_account, created = Account.objects.get_or_create(
                                name=destination_account_name,
                                defaults={
                                    'account_type': TransactionsParser.infer_account_type(destination_account_name),
                                    'currency': 'Real brasileiro',
                                    'opening_balance': Decimal('0'),
                                }
                            )
                            accounts_cache[destination_account_name] = destination_account
                            if created:
                                stats['created_accounts'] += 1
                        
                        # Gerar transfer_group_id
                        transfer_group_id = uuid.uuid4()
                        
                        # Reutilizar hashes do cache (já foram gerados antes do loop)
                        line_num = trans_data.get('line_num')
                        cache_idx = i - 1  # i-1 porque enumerate começa em 1, mas cache usa índice base 0
                        cached_hashes = transfer_hashes_cache.get(cache_idx)
                        
                        if cached_hashes:
                            import_hash_debit = cached_hashes['debit']
                            import_hash_credit = cached_hashes['credit']
                            # Atualizar nomes das contas do cache (caso tenham sido normalizados)
                            source_account_name = cached_hashes['source_account']
                            destination_account_name = cached_hashes['destination_account']
                        else:
                            # Fallback: gerar hashes se não estiverem no cache (não deveria acontecer)
                            import_hash_debit = TransactionsParser.generate_import_hash(
                                date=trans_data['transaction_date'],
                                beneficiary=None,
                                account=source_account_name,
                                memo=trans_data.get('memo', ''),
                                category=None,
                                subcategory=None,
                                value=trans_data['value'],
                                is_transfer=True,
                                source_account=source_account_name,
                                destination_account=destination_account_name,
                                transfer_side='DB',
                                line_num=line_num
                            )
                            
                            import_hash_credit = TransactionsParser.generate_import_hash(
                                date=trans_data['transaction_date'],
                                beneficiary=None,
                                account=destination_account_name,
                                memo=trans_data.get('memo', ''),
                                category=None,
                                subcategory=None,
                                value=trans_data['value'],
                                is_transfer=True,
                                source_account=source_account_name,
                                destination_account=destination_account_name,
                                transfer_side='CR',
                                line_num=line_num
                            )
                        
                        
                        # Verificar duplicatas para ambas as transações
                        # Verificar tanto no banco de dados quanto no lote atual
                        debit_in_db = import_hash_debit in existing_hashes_set
                        credit_in_db = import_hash_credit in existing_hashes_set
                        debit_in_batch = import_hash_debit in batch_hashes_set
                        credit_in_batch = import_hash_credit in batch_hashes_set
                        
                        if (debit_in_db or credit_in_db or debit_in_batch or credit_in_batch):
                            stats['duplicates'] += 1
                            continue
                        
                        # Adicionar ao set do lote atual para evitar duplicatas dentro do mesmo lote
                        batch_hashes_set.add(import_hash_debit)
                        batch_hashes_set.add(import_hash_credit)
                        
                        # Criar transação de débito (conta origem)
                        debit_transaction = Transaction(
                            account=source_account,
                            beneficiary=None,
                            subcategory=None,
                            transaction_type=TRANSACTION_TYPE_DB,
                            value=trans_data['value'],
                            transaction_date=trans_data['transaction_date'],
                            due_date=None,
                            purchase_date=None,
                            notes=trans_data.get('memo', ''),
                            import_hash=import_hash_debit,
                            transfer_group_id=transfer_group_id,
                            is_transfer=True
                        )
                        transactions_to_create.append(debit_transaction)
                        
                        # Criar transação de crédito (conta destino)
                        credit_transaction = Transaction(
                            account=destination_account,
                            beneficiary=None,
                            subcategory=None,
                            transaction_type=TRANSACTION_TYPE_CR,
                            value=trans_data['value'],
                            transaction_date=trans_data['transaction_date'],
                            due_date=None,
                            purchase_date=None,
                            notes=trans_data.get('memo', ''),
                            import_hash=import_hash_credit,
                            transfer_group_id=transfer_group_id,
                            is_transfer=True
                        )
                        transactions_to_create.append(credit_transaction)
                        
                        # Contar como 2 transações criadas
                        # (será contado no bulk_create)
                    else:
                        # Processar transação normal (não-transferência)
                        # Verificar duplicatas usando import_hash
                        # O hash é baseado nos valores originais e não muda mesmo após edições no stage
                        import_hash = trans_data.get('import_hash')
                        line_num = trans_data.get('line_num')
                        
                        if not import_hash:
                            # Se não há hash, pular esta transação (não deve acontecer, mas por segurança)
                            stats['errors'].append(f'Linha {line_num or "?"}: Hash de importação não encontrado')
                            continue
                        
                        # Verificar no set de hashes existentes (verificação em lote feita antes do loop)
                        # E também no batch_hashes_set para evitar duplicatas dentro do mesmo lote
                        is_duplicate = import_hash in existing_hashes_set or import_hash in batch_hashes_set
                        if is_duplicate:
                            stats['duplicates'] += 1
                            continue
                        
                        # Adicionar ao set para evitar duplicatas dentro do mesmo lote
                        batch_hashes_set.add(import_hash)
                        

                        # Criar Transaction
                        transaction_obj = Transaction(
                            account=account,
                            beneficiary=beneficiary,
                            subcategory=subcategory,
                            transaction_type=trans_data['transaction_type'],
                            value=trans_data['value'],
                            transaction_date=trans_data['transaction_date'],
                            due_date=None,
                            purchase_date=None,
                            notes=trans_data.get('memo', ''),
                            import_hash=import_hash,  # Incluir hash de importação baseado em valores originais
                        )
                        transactions_to_create.append(transaction_obj)

                    # Criar em lotes para melhor performance
                    if len(transactions_to_create) >= batch_size:
                        
                        try:
                            
                            created_objs = Transaction.objects.bulk_create(transactions_to_create, ignore_conflicts=False)
                            actual_created = len(created_objs) if created_objs else 0
                            stats['created_transactions'] += actual_created
                            
                        except Exception as e:
                            
                            # Se for erro de UNIQUE constraint, tratar como duplicatas
                            if 'UNIQUE constraint failed' in str(e) and 'import_hash' in str(e):
                                
                                # Tentar criar uma por uma para identificar quais são duplicatas
                                for trans_obj in transactions_to_create:
                                    try:
                                        Transaction.objects.create(
                                            account=trans_obj.account,
                                            beneficiary=trans_obj.beneficiary,
                                            subcategory=trans_obj.subcategory,
                                            transaction_type=trans_obj.transaction_type,
                                            value=trans_obj.value,
                                            transaction_date=trans_obj.transaction_date,
                                            due_date=trans_obj.due_date,
                                            purchase_date=trans_obj.purchase_date,
                                            notes=trans_obj.notes,
                                            import_hash=trans_obj.import_hash
                                        )
                                        stats['created_transactions'] += 1
                                    except Exception as individual_error:
                                        if 'UNIQUE constraint failed' in str(individual_error) and 'import_hash' in str(individual_error):
                                            stats['duplicates'] += 1
                                        else:
                                            stats['errors'].append(f'Erro ao criar transação individual: {str(individual_error)}')
                            else:
                                # Outros tipos de erro (IntegrityError, ForeignKey, etc.)
                                
                                # Se for erro de chave estrangeira, tentar criar uma por uma para identificar o problema
                                if 'FOREIGN KEY' in str(e) or 'foreign key' in str(e).lower() or 'IntegrityError' in type(e).__name__:
                                    
                                    # Tentar criar uma por uma para identificar qual transação está causando o problema
                                    for idx, trans_obj in enumerate(transactions_to_create):
                                        try:
                                            Transaction.objects.create(
                                                account=trans_obj.account,
                                                beneficiary=trans_obj.beneficiary,
                                                subcategory=trans_obj.subcategory,
                                                transaction_type=trans_obj.transaction_type,
                                                value=trans_obj.value,
                                                transaction_date=trans_obj.transaction_date,
                                                due_date=trans_obj.due_date,
                                                purchase_date=trans_obj.purchase_date,
                                                notes=trans_obj.notes,
                                                import_hash=trans_obj.import_hash,
                                                transfer_group_id=trans_obj.transfer_group_id,
                                                is_transfer=trans_obj.is_transfer,
                                                multiple_transaction_group_id=trans_obj.multiple_transaction_group_id,
                                                is_multiple=trans_obj.is_multiple
                                            )
                                            stats['created_transactions'] += 1
                                        except Exception as individual_error:
                                            
                                            if 'UNIQUE constraint failed' in str(individual_error) and 'import_hash' in str(individual_error):
                                                stats['duplicates'] += 1
                                            else:
                                                stats['errors'].append(f'Erro ao criar transação individual (índice {idx}): {str(individual_error)}')
                                else:
                                    stats['errors'].append(f'Erro ao criar lote: {str(e)}')
                        transactions_to_create = []
                        
                        # NÃO fechar conexões aqui - isso quebra a transação atômica
                        # close_old_connections() será chamado apenas após sair do bloco atomic()

                except Exception as e:
                    error_msg = f'Linha {trans_data.get("line_num", "?")}: {str(e)}'
                    stats['errors'].append(error_msg)
                    continue

            # Criar transações restantes
            if transactions_to_create:
                
                try:
                    created_objs = Transaction.objects.bulk_create(transactions_to_create, ignore_conflicts=False)
                    actual_created = len(created_objs) if created_objs else 0
                    stats['created_transactions'] += actual_created
                    
                except Exception as e:
                    # Se for erro de UNIQUE constraint, tratar como duplicatas
                    if 'UNIQUE constraint failed' in str(e) and 'import_hash' in str(e):
                        
                        # Tentar criar uma por uma para identificar quais são duplicatas
                        for trans_obj in transactions_to_create:
                            try:
                                Transaction.objects.create(
                                    account=trans_obj.account,
                                    beneficiary=trans_obj.beneficiary,
                                    subcategory=trans_obj.subcategory,
                                    transaction_type=trans_obj.transaction_type,
                                    value=trans_obj.value,
                                    transaction_date=trans_obj.transaction_date,
                                    due_date=trans_obj.due_date,
                                    purchase_date=trans_obj.purchase_date,
                                    notes=trans_obj.notes,
                                    import_hash=trans_obj.import_hash
                                )
                                stats['created_transactions'] += 1
                            except Exception as individual_error:
                                if 'UNIQUE constraint failed' in str(individual_error) and 'import_hash' in str(individual_error):
                                    stats['duplicates'] += 1
                                else:
                                    stats['errors'].append(f'Erro ao criar transação individual: {str(individual_error)}')
                    else:
                        stats['errors'].append(f'Erro ao criar lote final: {str(e)}')
        
        
        # Fechar conexões antigas para evitar locks no SQLite
        close_old_connections()
        
        
        # Limpar sessão (após garantir que a transação foi commitada)
        if 'transactions_staging_data' in request.session:
            del request.session['transactions_staging_data']
        if 'transactions_staging_count' in request.session:
            del request.session['transactions_staging_count']
        
        
        
        # Mensagens de sucesso
        success_msg = (
            f'Importação concluída! '
            f'{stats["created_transactions"]} transações criadas, '
            f'{stats["created_accounts"]} contas, '
            f'{stats["created_beneficiaries"]} beneficiários, '
            f'{stats["created_categories"]} categorias, '
            f'{stats["created_subcategories"]} subcategorias. '
            f'{stats["duplicates"]} duplicatas ignoradas.'
        )
        
        if stats.get('filtered_by_investment', 0) > 0:
            success_msg += f' {stats["filtered_by_investment"]} transação(ões) filtrada(s) (contas de investimento).'
        
        messages.success(request, success_msg)
        
        if stats['errors']:
            messages.warning(request, f'{len(stats["errors"])} erros encontrados durante a importação.')
        
        
        # Verificar se é uma requisição AJAX
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json':
            # Retornar JSON para requisições AJAX
            return JsonResponse({
                'success': True,
                'message': f'Importação concluída! {stats["created_transactions"]} transações criadas.',
                'stats': stats,
                'redirect_url': reverse('finance:transaction_list')
            })
        else:
            # Retornar redirect para requisições normais
            return redirect('finance:transaction_list')
        
    except Exception as e:
        
        messages.error(request, f'Erro durante importação: {str(e)}')
        return redirect('finance:transactions_import_staging')


# Asset Transactions Import Views
def asset_transactions_import_upload(request):
    """View para upload e parsing inicial do arquivo de transações de ativos"""
    if request.method == 'POST':
        form = AssetTransactionsImportForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = request.FILES['file']
            
            try:
                # Parsear arquivo
                transactions_data = AssetTransactionsParser.parse_file(uploaded_file)
                
                if not transactions_data:
                    messages.error(request, 'Nenhuma transação válida encontrada no arquivo.')
                    return render(request, 'finance/asset_transactions_import_upload.html', {'form': form})
                
                # Converter datas e Decimals para strings para armazenar na sessão
                for idx, trans in enumerate(transactions_data):
                    if trans.get('date'):
                        trans['date'] = trans['date'].isoformat()
                    # Converter Decimals para string
                    for field in ['quantity', 'price', 'fees', 'total']:
                        if trans.get(field) is not None:
                            trans[field] = str(trans[field])
                    # Adicionar índice original
                    trans['original_index'] = idx
                
                # Armazenar na sessão
                request.session['asset_transactions_staging_data'] = transactions_data
                request.session['asset_transactions_staging_count'] = len(transactions_data)
                
                messages.success(request, f'{len(transactions_data)} transações parseadas com sucesso!')
                return redirect('finance:asset_transactions_import_staging')
            except Exception as e:
                messages.error(request, f'Erro ao processar arquivo: {str(e)}')
    else:
        form = AssetTransactionsImportForm()
    
    return render(request, 'finance/asset_transactions_import_upload.html', {'form': form})


def asset_transactions_import_staging(request):
    """View para exibir transações de ativos em staging com filtros"""
    # Verificar se há dados na sessão
    if 'asset_transactions_staging_data' not in request.session:
        messages.warning(request, 'Nenhum arquivo carregado. Por favor, faça o upload do arquivo primeiro.')
        return redirect('finance:asset_transactions_import_upload')
    
    # Recuperar dados da sessão (manter como strings para evitar problemas de serialização)
    transactions_data_raw = request.session['asset_transactions_staging_data'].copy()
    
    # CORREÇÃO: Ajustar quantidade e preço quando ambos são zero
    # Trabalhar com strings para evitar problemas de serialização na sessão
    session_modified = False
    for trans in transactions_data_raw:
        # Obter valores como strings (sessão armazena como string)
        quantity_str = str(trans.get('quantity', '0') or '0')
        price_str = str(trans.get('price', '0') or '0')
        total_str = str(trans.get('total', '0') or '0')
        
        # Converter para Decimal apenas para comparação
        try:
            quantity = Decimal(quantity_str)
            price = Decimal(price_str)
            total = Decimal(total_str)
        except (ValueError, InvalidOperation):
            continue
        
        # Se ambos são zero e há um total, ajustar
        if quantity == Decimal('0') and price == Decimal('0') and total != Decimal('0'):
            trans['quantity'] = '1'
            trans['price'] = str(total)  # Manter como string para sessão
            session_modified = True
    
    # Salvar alterações na sessão se houver ajustes (mantendo tudo como strings)
    if session_modified:
        request.session['asset_transactions_staging_data'] = transactions_data_raw
        request.session.modified = True
    
    # Criar cópia para o template com objetos date e Decimal convertidos
    # IMPORTANTE: Não modificar transactions_data_raw (que fica na sessão como strings)
    transactions_data = []
    for trans_raw in transactions_data_raw:
        trans = trans_raw.copy()  # Cópia profunda do dicionário
        # Converter date de string para objeto date
        if trans.get('date'):
            if isinstance(trans['date'], str):
                try:
                    trans['date'] = datetime.strptime(trans['date'], '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    trans['date'] = None
        # Converter Decimal de string para objeto Decimal
        for field in ['quantity', 'price', 'fees', 'total']:
            if trans.get(field):
                if isinstance(trans[field], str):
                    try:
                        trans[field] = Decimal(str(trans[field]))
                    except (ValueError, TypeError):
                        trans[field] = Decimal('0')
        transactions_data.append(trans)
    
    # Verificar status de importação para todas as transações
    # Coletar todos os import_hash e verificar quais já existem no banco
    all_import_hashes = [t.get('import_hash') for t in transactions_data if t.get('import_hash')]
    imported_hashes_set = set()
    if all_import_hashes:
        imported_hashes_set = set(
            AssetTransaction.objects.filter(import_hash__in=all_import_hashes)
            .values_list('import_hash', flat=True)
        )
    
    # Adicionar campo is_imported a cada transação
    for trans in transactions_data:
        trans['is_imported'] = trans.get('import_hash') in imported_hashes_set
    
    # Aplicar filtros (usar transactions_data que tem objetos date/Decimal para comparação)
    filter_form = AssetTransactionsStagingFilterForm(request.GET)
    filtered_transactions = transactions_data.copy()
    
    if filter_form.is_valid():
        date_start = filter_form.cleaned_data.get('date_start')
        date_end = filter_form.cleaned_data.get('date_end')
        investment_account_filter = filter_form.cleaned_data.get('investment_account', '').lower()
        cash_account_filter = filter_form.cleaned_data.get('cash_account', '').lower()
        asset_code_filter = filter_form.cleaned_data.get('asset_code', '').lower()
        operation_type_filter = filter_form.cleaned_data.get('operation_type')
        min_value = filter_form.cleaned_data.get('min_value')
        max_value = filter_form.cleaned_data.get('max_value')
        import_status_filter = filter_form.cleaned_data.get('import_status')
        
        filtered_transactions = []
        for trans in transactions_data:
            # Filtro de data
            if date_start and trans.get('date'):
                if trans['date'] < date_start:
                    continue
            if date_end and trans.get('date'):
                if trans['date'] > date_end:
                    continue
            
            # Filtro de conta de investimento
            if investment_account_filter:
                if investment_account_filter not in trans.get('investment_account', '').lower():
                    continue
            
            # Filtro de conta cash
            if cash_account_filter:
                if cash_account_filter not in trans.get('cash_account', '').lower():
                    continue
            
            # Filtro de código do ativo
            if asset_code_filter:
                if asset_code_filter not in trans.get('asset_code', '').lower():
                    continue
            
            # Filtro de tipo de operação
            if operation_type_filter:
                if trans.get('operation_type') != operation_type_filter:
                    continue
            
            # Filtro de valor
            total_value = trans.get('total', Decimal('0'))
            if min_value is not None:
                if total_value < min_value:
                    continue
            if max_value is not None:
                if total_value > max_value:
                    continue
            
            # Filtro de status de importação
            if import_status_filter:
                is_imported = trans.get('is_imported', False)
                if import_status_filter == 'imported' and not is_imported:
                    continue
                if import_status_filter == 'not_imported' and is_imported:
                    continue
            
            filtered_transactions.append(trans)
    
    # Atualizar seleção na sessão se houver POST
    if request.method == 'POST':
        selected_indices = request.POST.getlist('selected_indices')
        selected_indices = [int(i) for i in selected_indices if i.isdigit()]
        # Atualizar estado de seleção nos dados originais (usar transactions_data_raw que tem strings)
        for idx, trans in enumerate(transactions_data_raw):
            trans['selected'] = idx in selected_indices
        # IMPORTANTE: Garantir que não há objetos date ou Decimal antes de salvar
        for trans in transactions_data_raw:
            if trans.get('date') and isinstance(trans['date'], date):
                trans['date'] = trans['date'].isoformat()
            for field in ['quantity', 'price', 'fees', 'total']:
                if trans.get(field) and isinstance(trans[field], Decimal):
                    trans[field] = str(trans[field])
        request.session['asset_transactions_staging_data'] = transactions_data_raw
        request.session.modified = True
    
    # Contar selecionadas (apenas transações com selected=True)
    selected_count = sum(1 for t in filtered_transactions if t.get('selected', False))
    
    # Paginação
    paginator = Paginator(filtered_transactions, IMPORT_STAGING_ASSET_TRANSACTIONS_PER_PAGE)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'finance/asset_transactions_import_staging.html', {
        'transactions': page_obj,
        'filter_form': filter_form,
        'total_count': len(transactions_data),
        'filtered_count': len(filtered_transactions),
        'selected_count': selected_count,
    })


def asset_transactions_import_edit_item(request):
    """View AJAX para editar item individual em staging"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método não permitido'}, status=405)
    
    try:
        data = json.loads(request.body)
        index = data.get('index')
        field = data.get('field')
        value = data.get('value')
        
        if 'asset_transactions_staging_data' not in request.session:
            return JsonResponse({'success': False, 'error': 'Nenhum dado em staging'}, status=400)
        
        transactions_data = request.session['asset_transactions_staging_data']
        
        # Encontrar transação pelo original_index
        trans = None
        for t in transactions_data:
            if t.get('original_index') == index:
                trans = t
                break
        
        if trans is None:
            return JsonResponse({'success': False, 'error': 'Transação não encontrada'}, status=400)
        
        # Preservar import_hash original
        original_import_hash = trans.get('import_hash')
        
        # Validar e converter valor conforme o campo
        if field == 'import_hash':
            return JsonResponse({'success': False, 'error': 'Campo import_hash não pode ser editado'}, status=400)
        elif field == 'date':
            try:
                trans['date'] = datetime.strptime(value, '%Y-%m-%d').date().isoformat()
            except ValueError:
                return JsonResponse({'success': False, 'error': 'Data inválida'}, status=400)
        elif field in ['quantity', 'price', 'fees', 'total']:
            try:
                trans[field] = str(Decimal(str(value)))
            except (ValueError, InvalidOperation):
                return JsonResponse({'success': False, 'error': 'Valor inválido'}, status=400)
        elif field in ['investment_account', 'asset_code', 'asset_name', 'notes', 'cash_account']:
            trans[field] = str(value)
        elif field == 'operation_type':
            valid_types = ['BUY', 'SELL', 'DIVIDEND', 'JCP', 'INTEREST', 'BONUS', 'REDEMPTION', 'TRANSFER_IN', 'PORTABILITY']
            if value not in valid_types:
                return JsonResponse({'success': False, 'error': 'Tipo de operação inválido'}, status=400)
            trans['operation_type'] = value
        elif field == 'selected':
            # Converter valor para booleano corretamente
            # IMPORTANTE: Garantir que seja sempre booleano, não string
            if isinstance(value, str):
                trans['selected'] = value.lower() in ('true', '1', 'yes', 'on')
            elif isinstance(value, bool):
                trans['selected'] = value
            else:
                # Converter para booleano
                trans['selected'] = bool(value)
            
        else:
            return JsonResponse({'success': False, 'error': 'Campo inválido'}, status=400)
        
        if field != 'selected':
            trans['edited'] = True
        
        # Garantir que import_hash original seja preservado
        if original_import_hash:
            trans['import_hash'] = original_import_hash
        
        # Garantir que selected seja sempre booleano antes de salvar na sessão
        # Django session pode serializar booleanos como strings, então vamos garantir que seja booleano
        if 'selected' in trans:
            if isinstance(trans['selected'], str):
                trans['selected'] = trans['selected'].lower() in ('true', '1', 'yes', 'on')
            elif not isinstance(trans['selected'], bool):
                trans['selected'] = bool(trans['selected'])
        
        # IMPORTANTE: Converter objetos date e Decimal para strings antes de salvar na sessão
        # A sessão Django requer serialização JSON, que não suporta objetos date e Decimal
        for t in transactions_data:
            if t.get('date') and isinstance(t['date'], date):
                t['date'] = t['date'].isoformat()
            for field in ['quantity', 'price', 'fees', 'total']:
                if t.get(field) and isinstance(t[field], Decimal):
                    t[field] = str(t[field])
        
        request.session['asset_transactions_staging_data'] = transactions_data
        request.session.modified = True
        
        return JsonResponse({'success': True, 'message': 'Item atualizado com sucesso'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def asset_transactions_import_select_all(request):
    """View AJAX para marcar todas as transações de uma vez"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método não permitido'}, status=405)
    
    try:
        if 'asset_transactions_staging_data' not in request.session:
            return JsonResponse({'success': False, 'error': 'Nenhum dado em staging'}, status=400)
        
        transactions_data = request.session['asset_transactions_staging_data']
        
        # Marcar todas as transações
        for trans in transactions_data:
            trans['selected'] = True
        
        request.session['asset_transactions_staging_data'] = transactions_data
        request.session.modified = True
        
        return JsonResponse({
            'success': True,
            'message': f'Todas as {len(transactions_data)} transações foram marcadas'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def asset_transactions_import_deselect_all(request):
    """View AJAX para desmarcar todas as transações de uma vez"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método não permitido'}, status=405)
    
    try:
        if 'asset_transactions_staging_data' not in request.session:
            return JsonResponse({'success': False, 'error': 'Nenhum dado em staging'}, status=400)
        
        transactions_data = request.session['asset_transactions_staging_data']
        
        # Desmarcar todas as transações
        for trans in transactions_data:
            trans['selected'] = False
        
        request.session['asset_transactions_staging_data'] = transactions_data
        request.session.modified = True
        
        return JsonResponse({
            'success': True,
            'message': f'Todas as {len(transactions_data)} transações foram desmarcadas'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def asset_transactions_import_remove_item(request):
    """View AJAX para remover item do staging"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método não permitido'}, status=405)
    
    try:
        data = json.loads(request.body)
        indices = data.get('indices', [])
        
        if 'asset_transactions_staging_data' not in request.session:
            return JsonResponse({'success': False, 'error': 'Nenhum dado em staging'}, status=400)
        
        transactions_data = request.session['asset_transactions_staging_data']
        
        # Remover transações pelos original_index
        indices_to_remove = set(indices)
        transactions_data = [t for t in transactions_data if t.get('original_index') not in indices_to_remove]
        
        # Reindexar original_index após remoção
        for idx, trans in enumerate(transactions_data):
            trans['original_index'] = idx
        
        request.session['asset_transactions_staging_data'] = transactions_data
        request.session['asset_transactions_staging_count'] = len(transactions_data)
        request.session.modified = True
        
        return JsonResponse({'success': True, 'message': f'{len(indices)} item(ns) removido(s)'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def asset_transactions_import_execute(request):
    """View para executar importação final das transações de ativos selecionadas"""
    if request.method != 'POST':
        messages.error(request, 'Método não permitido')
        return redirect('finance:asset_transactions_import_staging')
    
    try:
        data = json.loads(request.body)
        selected_indices = data.get('selected_indices', [])
        filters = data.get('filters')
        
        if 'asset_transactions_staging_data' not in request.session:
            messages.error(request, 'Nenhum dado em staging')
            return redirect('finance:asset_transactions_import_upload')
        
        transactions_data = request.session['asset_transactions_staging_data']
        
        # Converter strings de volta para objetos date e Decimal
        # IMPORTANTE: Normalizar campo 'selected' para booleano (Django session pode serializar como string)
        for trans in transactions_data:
            if trans.get('date') and isinstance(trans['date'], str):
                try:
                    trans['date'] = datetime.strptime(trans['date'], '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    trans['date'] = None
            for field in ['quantity', 'price', 'fees', 'total']:
                if trans.get(field) and isinstance(trans[field], str):
                    try:
                        trans[field] = Decimal(str(trans[field]))
                    except (ValueError, TypeError):
                        trans[field] = Decimal('0')
            
            # Normalizar campo 'selected' para booleano
            if 'selected' in trans:
                selected_value = trans['selected']
                if isinstance(selected_value, str):
                    trans['selected'] = selected_value.lower() in ('true', '1', 'yes', 'on')
                elif not isinstance(selected_value, bool):
                    trans['selected'] = bool(selected_value)
                # Se já for booleano, manter como está
        
        # Aplicar filtros se fornecidos
        if filters:
            filtered_transactions = []
            for trans in transactions_data:
                if filters.get('date_start') and trans.get('date'):
                    try:
                        date_start = datetime.strptime(filters['date_start'], '%Y-%m-%d').date()
                        if trans['date'] < date_start:
                            continue
                    except (ValueError, TypeError):
                        pass
                if filters.get('date_end') and trans.get('date'):
                    try:
                        date_end = datetime.strptime(filters['date_end'], '%Y-%m-%d').date()
                        if trans['date'] > date_end:
                            continue
                    except (ValueError, TypeError):
                        pass
                if filters.get('investment_account'):
                    if filters['investment_account'].lower() not in trans.get('investment_account', '').lower():
                        continue
                if filters.get('cash_account'):
                    if filters['cash_account'].lower() not in trans.get('cash_account', '').lower():
                        continue
                if filters.get('asset_code'):
                    if filters['asset_code'].lower() not in trans.get('asset_code', '').lower():
                        continue
                if filters.get('operation_type'):
                    if trans.get('operation_type') != filters['operation_type']:
                        continue
                if filters.get('min_value'):
                    try:
                        min_value = Decimal(str(filters['min_value']))
                        if trans.get('total', Decimal('0')) < min_value:
                            continue
                    except (ValueError, TypeError):
                        pass
                if filters.get('max_value'):
                    try:
                        max_value = Decimal(str(filters['max_value']))
                        if trans.get('total', Decimal('0')) > max_value:
                            continue
                    except (ValueError, TypeError):
                        pass
                filtered_transactions.append(trans)
            transactions_to_check = filtered_transactions
        else:
            transactions_to_check = transactions_data
        
        # Filtrar apenas transações selecionadas
        # IMPORTANTE: Todas as transações são inicializadas com selected=False por padrão.
        # Apenas transações explicitamente marcadas (selected=True) serão importadas.
        
        selected_transactions = []
        
        
        # Contar quantas transações têm selected=True antes do loop
        selected_count_before = sum(1 for t in transactions_to_check if t.get('selected', False) is True)
        
        
        for trans in transactions_to_check:
            should_include = False
            if not selected_indices:
                # Quando selected_indices está vazio, verificar campo 'selected' de cada transação
                # Apenas importar transações com selected=True
                selected_value = trans.get('selected')
                
                # Converter para booleano de forma explícita
                # IMPORTANTE: Django session pode serializar booleanos como strings
                if selected_value is None:
                    should_include = False
                elif isinstance(selected_value, str):
                    # Verificar se é string 'True' ou 'False' (Django session serialization)
                    if selected_value.lower() in ('true', '1', 'yes', 'on'):
                        should_include = True
                    elif selected_value.lower() in ('false', '0', 'no', 'off', ''):
                        should_include = False
                    else:
                        # Tentar converter para booleano
                        should_include = bool(selected_value)
                elif isinstance(selected_value, bool):
                    should_include = selected_value
                else:
                    # Converter para booleano
                    should_include = bool(selected_value)
            else:
                # Quando selected_indices é fornecido, usar apenas os índices especificados
                should_include = trans.get('original_index') in selected_indices
            
            if should_include:
                trans_copy = trans.copy()
                # Converter strings de volta para objetos se necessário
                if trans_copy.get('date') and isinstance(trans_copy['date'], str):
                    try:
                        trans_copy['date'] = datetime.strptime(trans_copy['date'], '%Y-%m-%d').date()
                    except (ValueError, TypeError):
                        continue
                for field in ['quantity', 'price', 'fees', 'total']:
                    if trans_copy.get(field) and isinstance(trans_copy[field], str):
                        try:
                            trans_copy[field] = Decimal(str(trans_copy[field]))
                        except (ValueError, TypeError):
                            trans_copy[field] = Decimal('0')
                selected_transactions.append(trans_copy)
        
        
        if not selected_transactions:
            messages.warning(request, 'Nenhuma transação selecionada para importar')
            return redirect('finance:asset_transactions_import_staging')
        
        # Estatísticas
        stats = {
            'created_accounts': 0,
            'created_assets': 0,
            'created_transactions': 0,
            'errors': [],
            'duplicates': 0,
        }
        
        # Processar transações
        with db_transaction.atomic():
            # Coletar todos os import_hash para verificação em lote
            all_import_hashes = [t.get('import_hash') for t in selected_transactions if t.get('import_hash')]
            imported_hashes_set = set()
            if all_import_hashes:
                imported_hashes_set = set(
                    AssetTransaction.objects.filter(import_hash__in=all_import_hashes)
                    .values_list('import_hash', flat=True)
                )
            
            for idx, trans_data in enumerate(selected_transactions):
                # Verificar duplicata
                if trans_data.get('import_hash') in imported_hashes_set:
                    stats['duplicates'] += 1
                    continue
                
                try:
                    # Criar/obter Account (conta de investimento)
                    investment_account_name = AssetTransactionsParser.normalize_name(trans_data['investment_account'])
                    if not investment_account_name:
                        stats['errors'].append(f'Linha {trans_data["line_num"]}: Conta de investimento vazia')
                        continue
                    
                    investment_account, created = Account.objects.get_or_create(
                        name=investment_account_name,
                        defaults={
                            'account_type': 'INVEST',
                            'currency': 'Real brasileiro',
                            'opening_balance': Decimal('0'),
                        }
                    )
                    if created:
                        stats['created_accounts'] += 1
                    
                    # Criar/obter Account (conta de transferência/cash)
                    cash_account = None
                    if trans_data.get('cash_account'):
                        cash_account_name = AssetTransactionsParser.normalize_name(trans_data['cash_account'])
                        if cash_account_name:
                            cash_account, created = Account.objects.get_or_create(
                                name=cash_account_name,
                                defaults={
                                    'account_type': TransactionsParser.infer_account_type(cash_account_name),
                                    'currency': 'Real brasileiro',
                                    'opening_balance': Decimal('0'),
                                }
                            )
                            if created:
                                stats['created_accounts'] += 1
                    
                    # Criar/obter Asset
                    asset_code = trans_data['asset_code'].upper().strip()
                    asset_name = trans_data.get('asset_name', asset_code)
                    investment_str = trans_data.get('investment_str', '')
                    asset_type = AssetTransactionsParser.infer_asset_type(investment_str, asset_code)
                    
                    asset, created = Asset.objects.get_or_create(
                        code=asset_code,
                        defaults={
                            'name': asset_name,
                            'asset_type': asset_type,
                            'currency': 'BRL',
                        }
                    )
                    if created:
                        stats['created_assets'] += 1
                    
                    # Determinar valores
                    quantity = trans_data.get('quantity', Decimal('0'))
                    price = trans_data.get('price', Decimal('0'))
                    fees = trans_data.get('fees', Decimal('0'))
                    total = trans_data.get('total', Decimal('0'))
                    operation_type = trans_data['operation_type']
                    
                    # Detectar portabilidade: se investment_account e cash_account são ambos tipo INVEST
                    if cash_account and investment_account.account_type == 'INVEST' and cash_account.account_type == 'INVEST':
                        operation_type = 'PORTABILITY'
                    # Se operation_type ainda é BUY e não há cash_account, pode ser TRANSFER_IN
                    # (já mapeado pelo parser, mas garantir que não seja alterado)
                    elif operation_type == 'TRANSFER_IN' and not cash_account:
                        # Manter como TRANSFER_IN
                        pass
                    
                    # Determinar total_value e income_value
                    is_income = trans_data.get('is_income_operation', False)
                    if is_income:
                        total_value = Decimal('0')
                        income_value = total
                    else:
                        total_value = total
                        income_value = Decimal('0')
                    
                    # Criar AssetTransaction
                    asset_transaction = AssetTransaction(
                        asset=asset,
                        account=investment_account,
                        operation_type=operation_type,
                        date=trans_data['date'],
                        quantity=quantity,
                        price=price,
                        fees=fees,
                        total_value=total_value,
                        income_value=income_value,
                        notes=trans_data.get('notes', ''),
                        import_hash=trans_data.get('import_hash'),
                    )
                    
                    # Definir cash_account temporariamente para uso no save
                    if cash_account:
                        asset_transaction._cash_account = cash_account
                    
                    # Salvar para criar Transactions relacionadas
                    asset_transaction.save()
                    
                    stats['created_transactions'] += 1
                    
                except Exception as e:
                    stats['errors'].append(f'Linha {trans_data.get("line_num", "?")}: {str(e)}')
                    continue
        
        # Mensagem de sucesso
        success_msg = (
            f'Importação concluída! '
            f'{stats["created_transactions"]} transações criadas, '
            f'{stats["created_accounts"]} contas criadas, '
            f'{stats["created_assets"]} ativos criados, '
            f'{stats["duplicates"]} duplicatas ignoradas.'
        )
        if stats['errors']:
            success_msg += f' {len(stats["errors"])} erro(s).'
        messages.success(request, success_msg)
        
        if stats['errors']:
            for error in stats['errors'][:10]:  # Mostrar apenas primeiros 10 erros
                messages.warning(request, error)
        
        return JsonResponse({
            'success': True,
            'message': success_msg,
            'stats': stats
        })
        
    except Exception as e:
        messages.error(request, f'Erro durante importação: {str(e)}')
        return redirect('finance:asset_transactions_import_staging')


# Chatbot Views
def chatbot_view(request):
    """View para renderizar a interface do chatbot"""
    return render(request, 'finance/chatbot.html')


def chatbot_api(request):
    """API endpoint para processar mensagens do chatbot"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        query = data.get('query', '').strip()
        
        if not query:
            return JsonResponse({'error': 'Query não fornecida'}, status=400)
        
        # Obter histórico da sessão (opcional)
        chat_history = request.session.get('chat_history', [])
        
        # Processar query
        response = get_chatbot_response(query, chat_history)
        
        # Atualizar histórico na sessão (manter últimas N mensagens)
        chat_history.append({'role': 'user', 'content': query})
        chat_history.append({'role': 'assistant', 'content': response})
        if len(chat_history) > CHAT_HISTORY_MAX_MESSAGES:
            chat_history = chat_history[-CHAT_HISTORY_MAX_MESSAGES:]
        request.session['chat_history'] = chat_history
        
        return JsonResponse({
            'response': response,
            'success': True
        })
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({
            'error': f'Erro ao processar consulta: {str(e)}',
            'success': False
        }, status=500)
