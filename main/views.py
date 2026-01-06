from django.shortcuts import render


def home(request):
    """Página inicial do sistema listando aplicações disponíveis"""
    applications = [
        {
            'name': 'Finance',
            'display_name': 'Finanças',
            'url': 'finance:index',
        }
    ]
    return render(request, 'home.html', {'applications': applications})


