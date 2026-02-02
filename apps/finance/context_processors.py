from .models import Account


def sidebar_accounts(request):
    """
    Context processor que fornece lista de contas com saldos calculados
    para exibição na sidebar. Usa uma única query com annotate (balance_delta).
    """
    accounts = (
        Account.objects.annotate(
            balance_delta=Account.get_balance_delta_annotation()
        )
        .order_by('account_type', 'name')
    )
    accounts_with_balance = [
        {
            'account': account,
            'balance': account.get_balance_from_annotation(),
        }
        for account in accounts
    ]
    return {
        'sidebar_accounts': accounts_with_balance,
    }
