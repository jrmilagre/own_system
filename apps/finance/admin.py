from django.contrib import admin
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


@admin.register(Subcategory)
class SubcategoryAdmin(admin.ModelAdmin):
    list_display = (
        'category',
        'subcategory',
        'default_transaction_type',
        'created_at',
        'updated_at',
    )
    search_fields = ('category__category', 'subcategory')
    list_filter = ('default_transaction_type', 'category', 'created_at')
    ordering = ('category', 'subcategory')


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