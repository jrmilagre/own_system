"""
Budget and spending calculation service.
Uses DB aggregation instead of Python loops.
"""
from datetime import date
from decimal import Decimal

from django.db.models import Q, Sum, Case, When, F, Value, DecimalField

from apps.finance.constants import TRANSACTION_TYPE_CR, TRANSACTION_TYPE_DB
from apps.finance.models import Transaction, Budget


def calculate_spent_by_subcategory(subcategory, start_date, end_date):
    """Calcula gastos por subcategoria em um período (agregação no banco)."""
    if not subcategory:
        return Decimal('0')
    date_filter = Q(
        Q(transaction_date__gte=start_date, transaction_date__lte=end_date) |
        Q(transaction_date__isnull=True, due_date__gte=start_date, due_date__lte=end_date)
    )
    result = Transaction.objects.filter(subcategory=subcategory).filter(date_filter).aggregate(
        total=Sum(
            Case(
                When(transaction_type=TRANSACTION_TYPE_CR, then=F('value')),
                When(transaction_type=TRANSACTION_TYPE_DB, then=-F('value')),
                default=Value(0),
                output_field=DecimalField(),
            )
        )
    )
    return result['total'] or Decimal('0')


def calculate_spent_by_category(category, start_date, end_date):
    """Calcula gastos por categoria em um período (agregação no banco)."""
    if not category:
        return Decimal('0')
    date_filter = Q(
        Q(transaction_date__gte=start_date, transaction_date__lte=end_date) |
        Q(transaction_date__isnull=True, due_date__gte=start_date, due_date__lte=end_date)
    )
    result = Transaction.objects.filter(subcategory__category=category).filter(date_filter).aggregate(
        total=Sum(
            Case(
                When(transaction_type=TRANSACTION_TYPE_CR, then=F('value')),
                When(transaction_type=TRANSACTION_TYPE_DB, then=-F('value')),
                default=Value(0),
                output_field=DecimalField(),
            )
        )
    )
    return result['total'] or Decimal('0')


def calculate_budget_by_subcategory(subcategory, year, month):
    """Calcula orçamento por subcategoria em um mês/ano."""
    if not subcategory:
        return Decimal('0')
    budget_date = date(year, month, 1)
    result = Budget.objects.filter(
        subcategory=subcategory,
        budget_date=budget_date
    ).aggregate(total=Sum('amount'))
    return result['total'] or Decimal('0')


def calculate_budget_by_category(category, year, month):
    """Calcula orçamento por categoria em um mês/ano."""
    if not category:
        return Decimal('0')
    budget_date = date(year, month, 1)
    result = Budget.objects.filter(
        subcategory__category=category,
        budget_date=budget_date
    ).aggregate(total=Sum('amount'))
    return result['total'] or Decimal('0')


def calculate_budget_by_subcategory_year(subcategory, year):
    """Calcula orçamento total por subcategoria em um ano."""
    if not subcategory:
        return Decimal('0')
    result = Budget.objects.filter(
        subcategory=subcategory,
        budget_date__year=year
    ).aggregate(total=Sum('amount'))
    return result['total'] or Decimal('0')


def calculate_budget_by_category_year(category, year):
    """Calcula orçamento total por categoria em um ano."""
    if not category:
        return Decimal('0')
    result = Budget.objects.filter(
        subcategory__category=category,
        budget_date__year=year
    ).aggregate(total=Sum('amount'))
    return result['total'] or Decimal('0')


def calculate_budget_accumulated_by_subcategory(subcategory, year, month):
    """Calcula orçamento acumulado por subcategoria desde o início do ano até o mês especificado."""
    if not subcategory:
        return Decimal('0')
    year_start = date(year, 1, 1)
    month_end = date(year, month, 1)
    result = Budget.objects.filter(
        subcategory=subcategory,
        budget_date__gte=year_start,
        budget_date__lte=month_end
    ).aggregate(total=Sum('amount'))
    return result['total'] or Decimal('0')


def calculate_budget_accumulated_by_category(category, year, month):
    """Calcula orçamento acumulado por categoria desde o início do ano até o mês especificado."""
    if not category:
        return Decimal('0')
    year_start = date(year, 1, 1)
    month_end = date(year, month, 1)
    result = Budget.objects.filter(
        subcategory__category=category,
        budget_date__gte=year_start,
        budget_date__lte=month_end
    ).aggregate(total=Sum('amount'))
    return result['total'] or Decimal('0')
