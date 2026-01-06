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
    # Transaction URLs
    path('transactions/', views.transaction_list, name='transaction_list'),
    path('transactions/create/', views.transaction_create, name='transaction_create'),
    path('transactions/<int:pk>/update/', views.transaction_update, name='transaction_update'),
    path('transactions/<int:pk>/delete/', views.transaction_delete, name='transaction_delete'),
    # Scheduler URLs
    path('schedulers/', views.scheduler_list, name='scheduler_list'),
    path('schedulers/create/', views.scheduler_create, name='scheduler_create'),
    path('schedulers/<int:pk>/update/', views.scheduler_update, name='scheduler_update'),
    path('schedulers/<int:pk>/delete/', views.scheduler_delete, name='scheduler_delete'),
    path('schedulers/<int:pk>/register/', views.scheduler_register, name='scheduler_register'),
]

