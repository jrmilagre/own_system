import os
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from apps.finance.models import CashFlowItem


class Command(BaseCommand):
    help = 'Carrega a fixture cash_flow_items com tratamento de dados existentes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Remove todos os itens existentes antes de carregar a fixture'
        )

    def handle(self, *args, **options):
        force = options.get('force', False)
        
        # Verificar quantos itens já existem
        existing_count = CashFlowItem.objects.count()
        
        if existing_count > 0:
            if force:
                self.stdout.write(
                    self.style.WARNING(f'Removendo {existing_count} itens existentes...')
                )
                CashFlowItem.objects.all().delete()
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f'Erro: Ja existem {existing_count} itens no banco. '
                        'Use --force para remover antes de carregar, ou use o comando init_cash_flow.'
                    )
                )
                return

        # Carregar a fixture
        fixture_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'fixtures',
            'cash_flow_items.json'
        )

        if not os.path.exists(fixture_path):
            raise CommandError(f'Fixture nao encontrada: {fixture_path}')

        try:
            call_command('loaddata', 'cash_flow_items', verbosity=0)
            
            self.stdout.write(
                self.style.SUCCESS('Fixture carregada com sucesso!')
            )
            self.stdout.write(
                self.style.WARNING(
                    'Nota: A fixture nao configura os relacionamentos accumulates_in. '
                    'Execute init_cash_flow para configurar os relacionamentos.'
                )
            )
        except Exception as e:
            raise CommandError(f'Erro ao carregar fixture: {e}')
