from .models import Account


def sidebar_accounts(request):
    """
    Context processor que fornece lista de contas com saldos calculados
    para exibição na sidebar.
    """
    accounts = Account.objects.all().order_by('account_type', 'name')
    
    accounts_with_balance = []
    for account in accounts:
        balance = account.get_balance()
        accounts_with_balance.append({
            'account': account,
            'balance': balance,
        })
    
    return {
        'sidebar_accounts': accounts_with_balance,
    }
