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
        'subcategory',
        'default_transaction_type',
        'created_at',
        'updated_at',
    )
    search_fields = ('category', 'subcategory')
    list_filter = ('default_transaction_type', 'created_at')
    ordering = ('category', 'subcategory')


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        'account',
        'beneficiary',
        'category',
        'value',
        'due_date',
        'registration_date',
        'purchase_date',
        'created_at',
        'updated_at',
    )
    search_fields = ('account__name', 'beneficiary__full_name', 'category__category', 'notes')
    list_filter = ('account', 'category', 'due_date', 'created_at')
    ordering = ('-created_at',)


@admin.register(Scheduler)
class SchedulerAdmin(admin.ModelAdmin):
    list_display = (
        'account',
        'beneficiary',
        'category',
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
    search_fields = ('account__name', 'beneficiary__full_name', 'category__category', 'notes')
    list_filter = ('status', 'recurrence_type', 'termination_type', 'account', 'category', 'created_at')
    ordering = ('-created_at',)