from django.urls import path
from . import views

app_name = 'finance'

urlpatterns = [
    path('', views.index, name='index'),
    # Account URLs
    path('accounts/', views.account_list, name='account_list'),
    path('accounts/create/', views.account_create, name='account_create'),
    path('accounts/<int:pk>/update/', views.account_update, name='account_update'),
    path('accounts/<int:pk>/delete/', views.account_delete, name='account_delete'),
    path('accounts/<int:account_id>/historico/', views.account_statement, name='historico'),
    # Beneficiary URLs
    path('beneficiaries/', views.beneficiary_list, name='beneficiary_list'),
    path('beneficiaries/create/', views.beneficiary_create, name='beneficiary_create'),
    path('beneficiaries/<int:pk>/update/', views.beneficiary_update, name='beneficiary_update'),
    path('beneficiaries/<int:pk>/delete/', views.beneficiary_delete, name='beneficiary_delete'),
    # Category URLs
    path('categories/', views.category_list, name='category_list'),
    path('categories/create/', views.category_create, name='category_create'),
    path('categories/<int:pk>/update/', views.category_update, name='category_update'),
    path('categories/<int:pk>/delete/', views.category_delete, name='category_delete'),
    # Subcategory URLs (nested under categories)
    path('categories/<int:category_pk>/subcategories/', views.subcategory_list, name='subcategory_list'),
    path('categories/<int:category_pk>/subcategories/create/', views.subcategory_create, name='subcategory_create'),
    path('categories/<int:category_pk>/subcategories/<int:pk>/update/', views.subcategory_update, name='subcategory_update'),
    path('categories/<int:category_pk>/subcategories/<int:pk>/delete/', views.subcategory_delete, name='subcategory_delete'),
    # Transaction URLs
    path('transactions/', views.transaction_list, name='transaction_list'),
    path('transactions/create/', views.transaction_create, name='transaction_create'),
    path('transactions/<int:pk>/update/', views.transaction_update, name='transaction_update'),
    path('transactions/<int:pk>/delete/', views.transaction_delete, name='transaction_delete'),
    # Multiple Transaction URLs
    path('transactions/multiple/create/', views.multiple_transaction_create, name='multiple_transaction_create'),
    path('transactions/multiple/<uuid:group_id>/update/', views.multiple_transaction_update, name='multiple_transaction_update'),
    path('transactions/multiple/<uuid:group_id>/delete/', views.multiple_transaction_delete, name='multiple_transaction_delete'),
    # Scheduler URLs
    path('schedulers/', views.scheduler_list, name='scheduler_list'),
    path('schedulers/create/', views.scheduler_create, name='scheduler_create'),
    path('schedulers/<int:pk>/update/', views.scheduler_update, name='scheduler_update'),
    path('schedulers/<int:pk>/delete/', views.scheduler_delete, name='scheduler_delete'),
    path('schedulers/<int:pk>/register/', views.scheduler_register, name='scheduler_register'),
    # Multiple Scheduler URLs (usando group_id em vez de pk)
    path('schedulers/multiple/', views.multiple_scheduler_list, name='multiple_scheduler_list'),
    path('schedulers/multiple/create/', views.multiple_scheduler_create, name='multiple_scheduler_create'),
    path('schedulers/multiple/<uuid:group_id>/update/', views.multiple_scheduler_update, name='multiple_scheduler_update'),
    path('schedulers/multiple/<uuid:group_id>/delete/', views.multiple_scheduler_delete, name='multiple_scheduler_delete'),
    path('schedulers/multiple/<uuid:group_id>/register/', views.multiple_scheduler_register, name='multiple_scheduler_register'),
    # API endpoint for JavaScript
    path('api/subcategory/<int:subcategory_id>/default-transaction-type/', views.get_subcategory_default_transaction_type, name='subcategory_default_transaction_type'),
    # Quick create endpoints (AJAX)
    path('api/quick-create/account/', views.quick_create_account, name='quick_create_account'),
    path('api/quick-create/beneficiary/', views.quick_create_beneficiary, name='quick_create_beneficiary'),
    path('api/quick-create/subcategory/', views.quick_create_subcategory, name='quick_create_subcategory'),
    # Asset URLs
    path('assets/', views.asset_list, name='asset_list'),
    path('assets/create/', views.asset_create, name='asset_create'),
    path('assets/<int:pk>/update/', views.asset_update, name='asset_update'),
    path('assets/<int:pk>/delete/', views.asset_delete, name='asset_delete'),
    # AssetTransaction URLs
    path('asset-transactions/', views.asset_transaction_list, name='asset_transaction_list'),
    path('asset-transactions/create/', views.asset_transaction_create, name='asset_transaction_create'),
    path('asset-transactions/<int:pk>/update/', views.asset_transaction_update, name='asset_transaction_update'),
    path('asset-transactions/<int:pk>/delete/', views.asset_transaction_delete, name='asset_transaction_delete'),
    # AssetPosition URLs
    path('asset-positions/create/', views.asset_position_create, name='asset_position_create'),
    path('asset-positions/<int:pk>/update/', views.asset_position_update, name='asset_position_update'),
    path('asset-positions/<int:pk>/delete/', views.asset_position_delete, name='asset_position_delete'),
    # Reports URLs
    path('reports/', views.reports_index, name='reports_index'),
    path('reports/account-statement/', views.account_statement, name='account_statement'),
    path('reports/asset-stock-position/', views.asset_stock_position_report, name='asset_stock_position_report'),
    path('reports/cash-flow/', views.cash_flow_report, name='cash_flow_report'),
    # Budget URLs
    path('budgets/', views.budget_list, name='budget_list'),
    path('budgets/create/', views.budget_create, name='budget_create'),
    path('budgets/<int:pk>/update/', views.budget_update, name='budget_update'),
    path('budgets/<int:pk>/delete/', views.budget_delete, name='budget_delete'),
    path('budgets/manage/', views.budget_manage, name='budget_manage'),
    # Inventory URLs
    path('inventory/', views.inventory_list, name='inventory_list'),
    path('inventory/create/', views.inventory_create, name='inventory_create'),
    path('inventory/<int:pk>/update/', views.inventory_update, name='inventory_update'),
    path('inventory/<int:pk>/delete/', views.inventory_delete, name='inventory_delete'),
    # Cash Flow Item URLs
    path('cash-flow-items/', views.cash_flow_item_list, name='cash_flow_item_list'),
    path('cash-flow-items/create/', views.cash_flow_item_create, name='cash_flow_item_create'),
    path('cash-flow-items/<int:pk>/update/', views.cash_flow_item_update, name='cash_flow_item_update'),
    path('cash-flow-items/<int:pk>/delete/', views.cash_flow_item_delete, name='cash_flow_item_delete'),
]

