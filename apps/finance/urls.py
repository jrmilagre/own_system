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
]

