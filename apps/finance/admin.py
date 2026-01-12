from django.contrib import admin
from django.utils.html import format_html
from .models import *

@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'account_type',
        'currency',
        'opening_balance',
        'created_at',
        'updated_at',
    )
    search_fields = ('name',)
    list_filter = ('account_type', 'currency', 'created_at')
    ordering = ('name',)


@admin.register(Beneficiary)
class BeneficiaryAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'created_at', 'updated_at')
    search_fields = ('full_name',)
    ordering = ('full_name',)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = (
        'category',
        'created_at',
        'updated_at',
    )
    search_fields = ('category',)
    list_filter = ('created_at',)
    ordering = ('category',)


class CashFlowMappingFilter(admin.SimpleListFilter):
    """Filtro customizado para status de mapeamento no fluxo de caixa"""
    title = 'Status no Fluxo de Caixa'
    parameter_name = 'cash_flow_mapping'

    def lookups(self, request, model_admin):
        return (
            ('not_mapped', 'Não mapeadas'),
            ('mapped', 'Mapeadas'),
            ('duplicate', 'Duplicadas'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'not_mapped':
            # Subcategorias não mapeadas
            mapping_count = CashFlowItem.get_subcategory_mapping_count()
            mapped_ids = set(mapping_count.keys())
            return queryset.exclude(id__in=mapped_ids)
        elif self.value() == 'mapped':
            # Subcategorias mapeadas uma vez
            mapping_count = CashFlowItem.get_subcategory_mapping_count()
            mapped_once_ids = [sid for sid, count in mapping_count.items() if count == 1]
            return queryset.filter(id__in=mapped_once_ids)
        elif self.value() == 'duplicate':
            # Subcategorias duplicadas
            mapping_count = CashFlowItem.get_subcategory_mapping_count()
            duplicate_ids = [sid for sid, count in mapping_count.items() if count > 1]
            return queryset.filter(id__in=duplicate_ids)
        return queryset


@admin.register(Subcategory)
class SubcategoryAdmin(admin.ModelAdmin):
    list_display = (
        'category',
        'subcategory',
        'default_transaction_type',
        'get_mapping_status',
        'get_mapping_count',
        'created_at',
        'updated_at',
    )
    search_fields = ('category__category', 'subcategory')
    list_filter = ('default_transaction_type', 'category', CashFlowMappingFilter, 'created_at')
    ordering = ('category', 'subcategory')
    
    def get_mapping_status(self, obj):
        """Retorna o status de mapeamento formatado com cores"""
        count = obj.get_cash_flow_mapping_count()
        if count == 0:
            return format_html(
                '<span style="background-color: #ffebee; color: #c62828; padding: 4px 8px; border-radius: 4px; font-weight: bold;">✗ Não mapeada</span>'
            )
        elif count == 1:
            return format_html(
                '<span style="background-color: #e8f5e9; color: #2e7d32; padding: 4px 8px; border-radius: 4px; font-weight: bold;">✓ Mapeada</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #fff3e0; color: #e65100; padding: 4px 8px; border-radius: 4px; font-weight: bold;">⚠ Duplicada</span>'
            )
    get_mapping_status.short_description = 'Status no Fluxo de Caixa'
    
    def get_mapping_count(self, obj):
        """Retorna o número de mapeamentos"""
        count = obj.get_cash_flow_mapping_count()
        if count == 0:
            return format_html('<span style="color: #c62828;">0</span>')
        elif count == 1:
            return format_html('<span style="color: #2e7d32;">1</span>')
        else:
            return format_html('<span style="color: #e65100; font-weight: bold;">{}</span>', count)
    get_mapping_count.short_description = 'Mapeamentos'


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'account',
        'beneficiary',
        'subcategory',
        'transaction_type',
        'value',
        'due_date',
        'transaction_date',
        'purchase_date',
        'created_at',
        'updated_at',
    )
    search_fields = ('account__name', 'beneficiary__full_name', 'subcategory__subcategory', 'subcategory__category__category', 'notes')
    list_filter = ('account', 'subcategory', 'transaction_type', 'due_date', 'created_at')
    ordering = ('-created_at',)


@admin.register(Scheduler)
class SchedulerAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'account',
        'beneficiary',
        'subcategory',
        'transaction_type',
        'value',
        'due_date',
        'recurrence_type',
        'recurrence_interval',
        'termination_type',
        'status',
        'registered_count',
        'created_at',
        'updated_at',
    )
    search_fields = ('account__name', 'beneficiary__full_name', 'subcategory__subcategory', 'subcategory__category__category', 'notes')
    list_filter = ('status', 'recurrence_type', 'termination_type', 'account', 'subcategory', 'transaction_type', 'created_at')
    ordering = ('-created_at',)


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'name',
        'asset_type',
        'sector',
        'currency',
        'created_at',
        'updated_at',
    )
    search_fields = ('code', 'name', 'sector')
    list_filter = ('asset_type', 'currency', 'created_at')
    ordering = ('code',)


@admin.register(AssetTransaction)
class AssetTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'asset',
        'account',
        'operation_type',
        'date',
        'quantity',
        'price',
        'total_value',
        'income_value',
        'created_at',
        'updated_at',
    )
    search_fields = ('asset__code', 'asset__name', 'account__name', 'notes')
    list_filter = ('operation_type', 'asset', 'account', 'date', 'created_at')
    ordering = ('-date', '-created_at')
    date_hierarchy = 'date'


@admin.register(AssetPosition)
class AssetPositionAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'asset',
        'account',
        'date',
        'quantity',
        'average_cost',
        'current_price',
        'created_at',
        'updated_at',
    )
    search_fields = ('asset__code', 'asset__name', 'account__name')
    list_filter = ('asset', 'account', 'date', 'created_at')
    ordering = ('-date', 'asset')
    date_hierarchy = 'date'


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = (
        'subcategory',
        'budget_date',
        'year',
        'month',
        'amount',
        'get_transaction_type_display',
        'created_at',
        'updated_at',
    )
    search_fields = ('subcategory__subcategory', 'subcategory__category__category')
    list_filter = ('budget_date', 'subcategory__category', 'subcategory__default_transaction_type', 'created_at')
    ordering = ('-budget_date', 'subcategory')
    date_hierarchy = 'budget_date'
    
    def year(self, obj):
        """Retorna o ano do orçamento"""
        return obj.budget_date.year
    year.short_description = 'Ano'
    
    def month(self, obj):
        """Retorna o mês do orçamento"""
        return obj.budget_date.month
    month.short_description = 'Mês'
    
    def get_transaction_type_display(self, obj):
        """Retorna o tipo de transação da subcategoria"""
        return obj.subcategory.get_default_transaction_type_display() if obj.subcategory else '-'
    get_transaction_type_display.short_description = 'Tipo de Transação'


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'type',
        'description',
        'brand',
        'model',
        'buy_price',
        'actual_price',
        'buy_date',
        'condition',
        'status',
        'location',
        'created_at',
        'updated_at',
    )
    search_fields = ('description', 'brand', 'model', 'serial_number', 'location', 'notes')
    list_filter = ('type', 'status', 'condition', 'buy_date', 'created_at')
    ordering = ('-created_at',)
    date_hierarchy = 'buy_date'
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('type', 'description', 'brand', 'model', 'serial_number')
        }),
        ('Valores e Datas', {
            'fields': ('buy_price', 'buy_date', 'actual_price', 'purchase_transaction')
        }),
        ('Estado e Localização', {
            'fields': ('condition', 'status', 'location')
        }),
        ('Garantia', {
            'fields': ('warranty_end_date',)
        }),
        ('Venda', {
            'fields': ('sale_date', 'sale_price'),
            'classes': ('collapse',)
        }),
        ('Observações', {
            'fields': ('notes',)
        }),
    )


@admin.register(CashFlowItem)
class CashFlowItemAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'description',
        'calculation_type',
        'accumulates_in',
        'order',
        'created_at',
        'updated_at',
    )
    search_fields = ('code', 'description')
    list_filter = ('calculation_type', 'accumulates_in', 'created_at')
    ordering = ('order', 'code')
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('code', 'description', 'order')
        }),
        ('Cálculo', {
            'fields': ('calculation_type', 'accumulates_in', 'calculation_rules')
        }),
    )