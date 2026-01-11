import os
import re
import logging
from decimal import Decimal, InvalidOperation
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.dateparse import parse_date
from apps.finance.models import Account, Beneficiary, Category, Subcategory, Transaction

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Importa transações do arquivo transactions.txt do Money99'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='transactions.txt',
            help='Caminho do arquivo de transações (padrão: transactions.txt)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simula a importação sem criar registros no banco de dados'
        )
        parser.add_argument(
            '--skip-existing',
            action='store_true',
            help='Pula transações duplicadas (mesma data, conta e valor)'
        )
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Limpa todas as tabelas (Transações, Categorias, Beneficiários, Contas) antes de importar'
        )

    def handle(self, *args, **options):
        file_path = options['file']
        dry_run = options['dry_run']
        skip_existing = options['skip_existing']
        reset = options['reset']

        if not os.path.exists(file_path):
            raise CommandError(f'Arquivo não encontrado: {file_path}')

        self.stdout.write(self.style.SUCCESS(f'Iniciando importação do arquivo: {file_path}'))
        if dry_run:
            self.stdout.write(self.style.WARNING('MODO DRY-RUN: Nenhum registro será criado'))
        
        # Limpar tabelas se solicitado
        if reset:
            if dry_run:
                self.stdout.write(self.style.WARNING('MODO DRY-RUN: Tabelas não serão limpas'))
            else:
                self._reset_tables()

        # Estatísticas
        stats = {
            'total_lines': 0,
            'skipped_lines': 0,
            'parsed_transactions': 0,
            'created_accounts': 0,
            'created_beneficiaries': 0,
            'created_categories': 0,
            'created_subcategories': 0,
            'created_transactions': 0,
            'errors': [],
            'duplicates': 0,
        }

        # Detectar encoding e ler arquivo
        encoding = self._detect_encoding(file_path)
        self.stdout.write(f'Encoding detectado: {encoding}')

            # Processar arquivo
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                lines = f.readlines()
                stats['total_lines'] = len(lines)

            # Parsear linhas
            transactions_data = []
            header_found = False

            for line_num, line in enumerate(lines, 1):
                line = line.rstrip('\n\r')
                
                # Verificar se é cabeçalho
                if not header_found and ('Data' in line and 'Favorecido' in line and 'Conta' in line):
                    header_found = True
                    self.stdout.write(f'Cabeçalho encontrado na linha {line_num}')
                    continue

                if not header_found:
                    continue

                # Ignorar linhas vazias
                if not line.strip():
                    stats['skipped_lines'] += 1
                    continue

                # Ignorar linhas de totalização
                if line.strip().startswith('Total'):
                    stats['skipped_lines'] += 1
                    continue

                # Ignorar linhas de seção (não começam com tab ou número de transação)
                # Aceitar linhas que começam com tab OU com número de transação (dígito)
                line_stripped = line.strip()
                if not line.startswith('\t') and not (line_stripped and line_stripped[0].isdigit()):
                    stats['skipped_lines'] += 1
                    continue

                # Parsear linha de transação
                parsed = self._parse_transaction_line(line, line_num)
                if parsed:
                    transactions_data.append(parsed)
                    stats['parsed_transactions'] += 1
                else:
                    stats['skipped_lines'] += 1

            self.stdout.write(f'Total de transações parseadas: {stats["parsed_transactions"]}')

            # Processar transações
            if not dry_run:
                with transaction.atomic():
                    self._process_transactions(transactions_data, stats, skip_existing)
            else:
                self._process_transactions_dry_run(transactions_data, stats, skip_existing)

            # Relatório final
            self._print_report(stats)

        except Exception as e:
            logger.exception('Erro durante importação')
            raise CommandError(f'Erro durante importação: {str(e)}')

    def _reset_tables(self):
        """Limpa todas as tabelas envolvidas na importação"""
        self.stdout.write(self.style.WARNING('Limpando tabelas...'))
        
        try:
            # Contar registros antes de deletar
            transaction_count = Transaction.objects.count()
            category_count = Category.objects.count()
            beneficiary_count = Beneficiary.objects.count()
            account_count = Account.objects.count()
            
            # Deletar em lotes para evitar "too many SQL variables" no SQLite
            batch_size = 1000
            
            # 1. Transações (depende de Account, Beneficiary, Subcategory)
            deleted_transactions = 0
            while Transaction.objects.exists():
                batch = Transaction.objects.all()[:batch_size]
                batch_ids = list(batch.values_list('id', flat=True))
                if batch_ids:
                    deleted = Transaction.objects.filter(id__in=batch_ids).delete()[0]
                    deleted_transactions += deleted
                    self.stdout.write(f'  - Deletadas {deleted_transactions}/{transaction_count} transações...', ending='\r')
            self.stdout.write(f'  - {deleted_transactions} transação(ões) deletada(s)')
            
            # 2. Subcategorias (depende de Category)
            deleted_subcategories = 0
            while Subcategory.objects.exists():
                batch = Subcategory.objects.all()[:batch_size]
                batch_ids = list(batch.values_list('id', flat=True))
                if batch_ids:
                    deleted = Subcategory.objects.filter(id__in=batch_ids).delete()[0]
                    deleted_subcategories += deleted
            self.stdout.write(f'  - {deleted_subcategories} subcategoria(s) deletada(s)')
            
            # 3. Categorias
            deleted_categories = 0
            while Category.objects.exists():
                batch = Category.objects.all()[:batch_size]
                batch_ids = list(batch.values_list('id', flat=True))
                if batch_ids:
                    deleted = Category.objects.filter(id__in=batch_ids).delete()[0]
                    deleted_categories += deleted
            self.stdout.write(f'  - {deleted_categories} categoria(s) deletada(s)')
            
            # 4. Beneficiários
            deleted_beneficiaries = 0
            while Beneficiary.objects.exists():
                batch = Beneficiary.objects.all()[:batch_size]
                batch_ids = list(batch.values_list('id', flat=True))
                if batch_ids:
                    deleted = Beneficiary.objects.filter(id__in=batch_ids).delete()[0]
                    deleted_beneficiaries += deleted
            self.stdout.write(f'  - {deleted_beneficiaries} beneficiário(s) deletado(s)')
            
            # 5. Contas
            deleted_accounts = 0
            while Account.objects.exists():
                batch = Account.objects.all()[:batch_size]
                batch_ids = list(batch.values_list('id', flat=True))
                if batch_ids:
                    deleted = Account.objects.filter(id__in=batch_ids).delete()[0]
                    deleted_accounts += deleted
            self.stdout.write(f'  - {deleted_accounts} conta(s) deletada(s)')
            
            self.stdout.write(self.style.SUCCESS(
                f'Tabelas limpas com sucesso! '
                f'Total: {transaction_count} transações, {category_count} categorias, '
                f'{beneficiary_count} beneficiários, {account_count} contas'
            ))
        except Exception as e:
            logger.exception('Erro ao limpar tabelas')
            raise CommandError(f'Erro ao limpar tabelas: {str(e)}')

    def _detect_encoding(self, file_path):
        """Detecta o encoding do arquivo tentando múltiplos encodings"""
        encodings = ['utf-8', 'windows-1252', 'iso-8859-1', 'latin1']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    # Ler algumas linhas para testar
                    for i, line in enumerate(f):
                        if i > 100:  # Testar primeiras 100 linhas
                            break
                return encoding
            except (UnicodeDecodeError, UnicodeError):
                continue
        
        # Se nenhum funcionar, tentar utf-8 com errors='replace'
        return 'utf-8'

    def _parse_transaction_line(self, line, line_num):
        """Parseia uma linha de transação"""
        try:
            # Remover tab inicial e dividir por tabs
            line = line.lstrip('\t')
            parts = [p.strip() for p in line.split('\t')]
            
            if len(parts) < 6:
                return None

            # Extrair campos
            # Formato: Data | Favorecido | Conta | Memo | Categoria | (vazio) | Montante
            # OU: NumTransação | Data | Favorecido | Conta | Memo | Categoria | (vazio) | Montante
            date_str = parts[0] if len(parts) > 0 else ''
            
            # Se o primeiro campo é numérico (número de transação), pular para o próximo
            if date_str.isdigit():
                if len(parts) > 1:
                    date_str = parts[1]
                    beneficiary_str = parts[2] if len(parts) > 2 else ''
                    account_str = parts[3] if len(parts) > 3 else ''
                    memo_str = parts[4] if len(parts) > 4 else ''
                    category_str = parts[5] if len(parts) > 5 else ''
                    amount_str = parts[7] if len(parts) > 7 and parts[7] else (parts[6] if len(parts) > 6 else '')
                else:
                    return None
            else:
                beneficiary_str = parts[1] if len(parts) > 1 else ''
                account_str = parts[2] if len(parts) > 2 else ''
                memo_str = parts[3] if len(parts) > 3 else ''
                category_str = parts[4] if len(parts) > 4 else ''
                # Montante pode estar em parts[6] (se houver coluna vazia) ou parts[5]
                amount_str = parts[6] if len(parts) > 6 and parts[6] else (parts[5] if len(parts) > 5 else '')

            # Validar campos obrigatórios
            if not date_str or not account_str or not amount_str:
                return None

            # Validar e converter data
            transaction_date = self._parse_date(date_str)
            if not transaction_date:
                return None

            # Validar e converter valor
            amount = self._parse_amount(amount_str)
            if amount is None:
                return None

            # Determinar tipo de transação
            transaction_type = 'CR' if amount >= 0 else 'DB'
            value = abs(amount)

            # Separar categoria e subcategoria
            category, subcategory = self._parse_category(category_str)

            result = {
                'transaction_date': transaction_date,
                'beneficiary': beneficiary_str,
                'account': account_str,
                'memo': memo_str,
                'category': category,
                'subcategory': subcategory,
                'transaction_type': transaction_type,
                'value': value,
                'line_num': line_num,
            }
            return result
        except Exception as e:
            logger.warning(f'Erro ao parsear linha {line_num}: {str(e)}')
            return None

    def _parse_date(self, date_str):
        """Converte data do formato DD/MM/YYYY para objeto date"""
        try:
            # Formato esperado: DD/MM/YYYY
            date_obj = datetime.strptime(date_str, '%d/%m/%Y').date()
            return date_obj
        except ValueError:
            return None

    def _parse_amount(self, amount_str):
        """Converte valor monetário do formato brasileiro para Decimal"""
        try:
            # Remover espaços
            amount_str = amount_str.strip()
            
            # Verificar se é negativo (pode ter sinal de menos)
            is_negative = amount_str.startswith('-')
            if is_negative:
                amount_str = amount_str[1:]

            # Remover pontos de milhar e substituir vírgula por ponto
            # Formato: 1.234,56 ou 1234,56 ou 1234.56
            amount_str = amount_str.replace('.', '').replace(',', '.')
            
            value = Decimal(amount_str)
            if is_negative:
                value = -value
            
            return value
        except (ValueError, InvalidOperation):
            return None

    def _parse_category(self, category_str):
        """Separa categoria e subcategoria do formato "Categoria : Subcategoria" """
        if not category_str:
            return None, None

        # Separar por " : "
        if ' : ' in category_str:
            parts = category_str.split(' : ', 1)
            category = parts[0].strip()
            subcategory = parts[1].strip() if len(parts) > 1 else ''
            return category, subcategory
        else:
            # Se não tem subcategoria, usar a categoria como subcategoria também
            return category_str.strip(), category_str.strip()

    def _normalize_name(self, name):
        """Normaliza nome removendo espaços extras"""
        if not name:
            return ''
        return ' '.join(name.split())

    def _infer_account_type(self, account_name):
        """Infere o tipo de conta baseado no nome"""
        name_lower = account_name.lower()
        if 'dinheiro' in name_lower or 'cash' in name_lower:
            return 'CASH'
        elif 'cartão' in name_lower or 'card' in name_lower or 'credcard' in name_lower:
            return 'CREDCARD'
        elif 'investimento' in name_lower or 'invest' in name_lower:
            return 'INVEST'
        else:
            return 'BANK'

    def _process_transactions(self, transactions_data, stats, skip_existing):
        """Processa e cria as transações no banco de dados"""
        batch_size = 100
        transactions_to_create = []

        for i, trans_data in enumerate(transactions_data, 1):
            try:
                # Criar/obter Account
                account_name = self._normalize_name(trans_data['account'])
                if not account_name:
                    stats['errors'].append(f'Linha {trans_data["line_num"]}: Conta vazia')
                    continue

                account, created = Account.objects.get_or_create(
                    name=account_name,
                    defaults={
                        'account_type': self._infer_account_type(account_name),
                        'currency': 'Real brasileiro',
                        'opening_balance': Decimal('0'),
                    }
                )
                if created:
                    stats['created_accounts'] += 1

                # Criar/obter Beneficiary (se houver)
                beneficiary = None
                if trans_data['beneficiary']:
                    beneficiary_name = self._normalize_name(trans_data['beneficiary'])
                    beneficiary, created = Beneficiary.objects.get_or_create(
                        full_name=beneficiary_name
                    )
                    if created:
                        stats['created_beneficiaries'] += 1

                # Criar/obter Category e Subcategory
                subcategory = None
                if trans_data['category']:
                    category_name = self._normalize_name(trans_data['category'])
                    category, created = Category.objects.get_or_create(
                        category=category_name
                    )
                    if created:
                        stats['created_categories'] += 1

                    if trans_data['subcategory']:
                        subcategory_name = self._normalize_name(trans_data['subcategory'])
                        subcategory, created = Subcategory.objects.get_or_create(
                            category=category,
                            subcategory=subcategory_name,
                            defaults={
                                'default_transaction_type': trans_data['transaction_type'],
                            }
                        )
                        if created:
                            stats['created_subcategories'] += 1

                # Verificar duplicatas se solicitado
                if skip_existing:
                    existing = Transaction.objects.filter(
                        account=account,
                        transaction_date=trans_data['transaction_date'],
                        value=trans_data['value'],
                        transaction_type=trans_data['transaction_type'],
                    )
                    if beneficiary:
                        existing = existing.filter(beneficiary=beneficiary)
                    else:
                        existing = existing.filter(beneficiary__isnull=True)
                    
                    # Incluir subcategoria na verificação de duplicatas
                    if subcategory:
                        existing = existing.filter(subcategory=subcategory)
                    else:
                        existing = existing.filter(subcategory__isnull=True)
                    
                    if existing.exists():
                        stats['duplicates'] += 1
                        continue

                # Criar Transaction
                transaction_obj = Transaction(
                    account=account,
                    beneficiary=beneficiary,
                    subcategory=subcategory,
                    transaction_type=trans_data['transaction_type'],
                    value=trans_data['value'],
                    transaction_date=trans_data['transaction_date'],
                    due_date=None,
                    purchase_date=None,
                    notes=trans_data['memo'],
                )
                transactions_to_create.append(transaction_obj)

                # Criar em lotes para melhor performance
                if len(transactions_to_create) >= batch_size:
                    Transaction.objects.bulk_create(transactions_to_create)
                    stats['created_transactions'] += len(transactions_to_create)
                    transactions_to_create = []
                    self.stdout.write(f'Processadas {i}/{len(transactions_data)} transações...')

            except Exception as e:
                error_msg = f'Linha {trans_data["line_num"]}: {str(e)}'
                stats['errors'].append(error_msg)
                logger.exception(error_msg)
                continue

        # Criar transações restantes
        if transactions_to_create:
            Transaction.objects.bulk_create(transactions_to_create)
            stats['created_transactions'] += len(transactions_to_create)

    def _process_transactions_dry_run(self, transactions_data, stats, skip_existing):
        """Simula o processamento sem criar registros"""
        # Usar sets para rastrear entidades únicas que seriam criadas
        accounts_to_create = set()
        beneficiaries_to_create = set()
        categories_to_create = set()
        subcategories_to_create = set()

        for trans_data in transactions_data:
            try:
                account_name = self._normalize_name(trans_data['account'])
                if not account_name:
                    stats['errors'].append(f'Linha {trans_data["line_num"]}: Conta vazia')
                    continue

                # Verificar se Account existe ou seria criada
                account_exists = Account.objects.filter(name=account_name).exists()
                if not account_exists:
                    accounts_to_create.add(account_name)

                # Verificar Beneficiary
                if trans_data['beneficiary']:
                    beneficiary_name = self._normalize_name(trans_data['beneficiary'])
                    beneficiary_exists = Beneficiary.objects.filter(full_name=beneficiary_name).exists()
                    if not beneficiary_exists:
                        beneficiaries_to_create.add(beneficiary_name)

                # Verificar Category e Subcategory
                if trans_data['category']:
                    category_name = self._normalize_name(trans_data['category'])
                    category_exists = Category.objects.filter(category=category_name).exists()
                    if not category_exists:
                        categories_to_create.add(category_name)

                    if trans_data['subcategory']:
                        subcategory_name = self._normalize_name(trans_data['subcategory'])
                        category = Category.objects.filter(category=category_name).first()
                        if category:
                            subcategory_exists = Subcategory.objects.filter(
                                category=category,
                                subcategory=subcategory_name
                            ).exists()
                            if not subcategory_exists:
                                subcategories_to_create.add((category_name, subcategory_name))
                        else:
                            # Se categoria não existe, subcategoria também não existe
                            subcategories_to_create.add((category_name, subcategory_name))

                # Verificar duplicatas
                if skip_existing:
                    account = Account.objects.filter(name=account_name).first()
                    if account:
                        existing = Transaction.objects.filter(
                            account=account,
                            transaction_date=trans_data['transaction_date'],
                            value=trans_data['value'],
                            transaction_type=trans_data['transaction_type'],
                        )
                        if trans_data['beneficiary']:
                            beneficiary = Beneficiary.objects.filter(
                                full_name=self._normalize_name(trans_data['beneficiary'])
                            ).first()
                            if beneficiary:
                                existing = existing.filter(beneficiary=beneficiary)
                            else:
                                existing = existing.filter(beneficiary__isnull=True)
                        else:
                            existing = existing.filter(beneficiary__isnull=True)
                        
                        if existing.exists():
                            stats['duplicates'] += 1
                            continue

                stats['created_transactions'] += 1

            except Exception as e:
                error_msg = f'Linha {trans_data["line_num"]}: {str(e)}'
                stats['errors'].append(error_msg)
                logger.exception(error_msg)
                continue

        # Atualizar estatísticas com contagens únicas
        stats['created_accounts'] = len(accounts_to_create)
        stats['created_beneficiaries'] = len(beneficiaries_to_create)
        stats['created_categories'] = len(categories_to_create)
        stats['created_subcategories'] = len(subcategories_to_create)

    def _print_report(self, stats):
        """Imprime relatório final da importação"""
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('RELATÓRIO DE IMPORTAÇÃO'))
        self.stdout.write('='*60)
        self.stdout.write(f'Total de linhas no arquivo: {stats["total_lines"]}')
        self.stdout.write(f'Linhas ignoradas: {stats["skipped_lines"]}')
        self.stdout.write(f'Transações parseadas: {stats["parsed_transactions"]}')
        self.stdout.write(f'Contas criadas: {stats["created_accounts"]}')
        self.stdout.write(f'Beneficiários criados: {stats["created_beneficiaries"]}')
        self.stdout.write(f'Categorias criadas: {stats["created_categories"]}')
        self.stdout.write(f'Subcategorias criadas: {stats["created_subcategories"]}')
        self.stdout.write(f'Transações criadas: {stats["created_transactions"]}')
        self.stdout.write(f'Duplicatas ignoradas: {stats["duplicates"]}')
        self.stdout.write(f'Erros: {len(stats["errors"])}')

        if stats['errors']:
            self.stdout.write('\n' + self.style.ERROR('ERROS ENCONTRADOS:'))
            for error in stats['errors'][:20]:  # Mostrar apenas primeiros 20 erros
                self.stdout.write(self.style.ERROR(f'  - {error}'))
            if len(stats['errors']) > 20:
                self.stdout.write(self.style.ERROR(f'  ... e mais {len(stats["errors"]) - 20} erros'))

        self.stdout.write('='*60)
