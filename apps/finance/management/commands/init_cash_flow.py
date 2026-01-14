from django.core.management.base import BaseCommand
from apps.finance.models import CashFlowItem


class Command(BaseCommand):
    help = 'Inicializa os itens do fluxo de caixa com a estrutura pré-definida'

    def handle(self, *args, **options):
        # Dados a serem criados: (código, descrição, acumula_em)
        items_data = [
            ('1', 'Início', '2'),
            ('1.01', 'Renda (marido)', '2'),
            ('2', 'Caixa bruto', '3'),
            ('2.01', 'Despesas fixas', '3'),
            ('3', 'Caixa após despesas fixas', '4'),
            ('3.01', 'Despesas variáveis', '4'),
            ('4', 'Caixa após despesas variáveis', '5'),
            ('4.01', 'Resultado financeiro', '5'),
            ('4.01.01', 'Receitas financeiras', '4.01'),
            ('4.01.02', 'Despesas financeiras', '4.01'),
            ('5', 'Caixa após resultado financeiro', '6'),
            ('5.01', 'Resultado patrimonial', '6'),
            ('5.01.01', 'Aportes', '5.01'),
            ('5.01.02', 'Resgates', '5.01'),
            ('6', 'Caixa após resultado patrimonial', '7'),
            ('6.01', 'Captação de recursos', '7'),
            ('6.02', 'Dispêndio de recursos', '7'),
            ('7', 'Caixa líquido', None),
        ]
        
        # Criar um dicionário para armazenar os objetos criados
        created_items = {}
        
        # Primeiro, criar todos os itens sem o relacionamento accumulates_in
        for code, description, accumulates_in_code in items_data:
            item, created = CashFlowItem.objects.get_or_create(
                code=code,
                defaults={
                    'description': description,
                    'calculation_type': 'SUBTOTAL',
                    'order': len(created_items) + 1,
                    'calculation_rules': [],
                }
            )
            created_items[code] = item
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'[OK] Criado: {code} - {description}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'[EXISTS] Ja existe: {code} - {description}')
                )
        
        # Depois, atualizar os relacionamentos accumulates_in
        for code, description, accumulates_in_code in items_data:
            item = created_items[code]
            
            if accumulates_in_code:
                try:
                    accumulates_in_item = created_items[accumulates_in_code]
                    item.accumulates_in = accumulates_in_item
                    item.save()
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'[OK] Relacionamento: {code} acumula em {accumulates_in_code}'
                        )
                    )
                except KeyError:
                    self.stdout.write(
                        self.style.ERROR(
                            f'[ERRO] Item {accumulates_in_code} nao encontrado para {code}'
                        )
                    )
            else:
                # Já está como None, não precisa atualizar
                pass
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n[OK] Total de {len(created_items)} itens processados!'
            )
        )
