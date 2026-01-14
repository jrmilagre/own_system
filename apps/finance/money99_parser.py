"""
Utilitário para parsing de arquivos transactions.txt do Money99
Extraído do comando import_money99.py para reutilização em views
"""
import re
import logging
import hashlib
from decimal import Decimal, InvalidOperation
from datetime import datetime

logger = logging.getLogger(__name__)


class Money99Parser:
    """Classe utilitária para parsing de arquivos Money99"""
    
    @staticmethod
    def detect_encoding(file_path):
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
    
    @staticmethod
    def detect_encoding_from_file(file_obj):
        """Detecta encoding de um arquivo já aberto (para uso com upload)"""
        # Para arquivos enviados via upload, tentar ler com diferentes encodings
        encodings = ['utf-8', 'windows-1252', 'iso-8859-1', 'latin1']
        
        # Salvar posição atual
        current_pos = file_obj.tell()
        file_obj.seek(0)
        
        for encoding in encodings:
            try:
                file_obj.seek(0)
                content = file_obj.read()
                # Tentar decodificar
                content.decode(encoding)
                file_obj.seek(current_pos)
                return encoding
            except (UnicodeDecodeError, UnicodeError):
                continue
        
        file_obj.seek(current_pos)
        return 'utf-8'
    
    @staticmethod
    def parse_date(date_str):
        """Converte data do formato DD/MM/YYYY para objeto date"""
        try:
            # Formato esperado: DD/MM/YYYY
            date_obj = datetime.strptime(date_str, '%d/%m/%Y').date()
            return date_obj
        except ValueError:
            return None
    
    @staticmethod
    def parse_amount(amount_str):
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
    
    @staticmethod
    def parse_category(category_str):
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
    
    @staticmethod
    def normalize_name(name):
        """Normaliza nome removendo espaços extras"""
        if not name:
            return ''
        return ' '.join(name.split())
    
    @staticmethod
    def infer_account_type(account_name):
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
    
    @staticmethod
    def generate_import_hash(date, beneficiary, account, memo, category, subcategory, value):
        """
        Gera hash MD5 baseado nos dados originais da transação para prevenir duplicatas.
        
        Args:
            date: Data da transação (objeto date)
            beneficiary: Nome do favorecido (string)
            account: Nome da conta (string)
            memo: Memo/anotações (string)
            category: Categoria (string)
            subcategory: Subcategoria (string)
            value: Valor da transação (Decimal)
        
        Returns:
            Hash MD5 hexadecimal de 32 caracteres
        """
        # Normalizar valores
        # Data: Formato YYYY-MM-DD
        date_str = date.strftime('%Y-%m-%d') if date else ''
        
        # Favorecido: Normalizar espaços, converter para string vazia se None
        beneficiary_str = Money99Parser.normalize_name(beneficiary) if beneficiary else ''
        
        # Conta: Normalizar espaços
        account_str = Money99Parser.normalize_name(account) if account else ''
        
        # Memo: Normalizar espaços, converter para string vazia se None
        memo_str = ' '.join(memo.split()) if memo else ''
        
        # Categoria: Normalizar espaços, usar categoria + " : " + subcategoria (ou apenas categoria se não houver subcategoria)
        category_str = ''
        if category:
            category_normalized = Money99Parser.normalize_name(category)
            if subcategory and subcategory != category:
                subcategory_normalized = Money99Parser.normalize_name(subcategory)
                category_str = f"{category_normalized} : {subcategory_normalized}"
            else:
                category_str = category_normalized
        
        # Montante: Converter Decimal para string com 2 casas decimais (sem separadores)
        if value is not None:
            value_str = f"{value:.2f}"
        else:
            value_str = '0.00'
        
        # Concatenar na ordem: Data|Favorecido|Conta|Memo|Categoria|Montante
        hash_string = f"{date_str}|{beneficiary_str}|{account_str}|{memo_str}|{category_str}|{value_str}"
        
        # Gerar MD5
        return hashlib.md5(hash_string.encode('utf-8')).hexdigest()
    
    @staticmethod
    def parse_transaction_line(line, line_num):
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
            transaction_date = Money99Parser.parse_date(date_str)
            if not transaction_date:
                return None

            # Validar e converter valor
            amount = Money99Parser.parse_amount(amount_str)
            if amount is None:
                return None

            # Determinar tipo de transação
            transaction_type = 'CR' if amount >= 0 else 'DB'
            value = abs(amount)

            # Separar categoria e subcategoria
            category, subcategory = Money99Parser.parse_category(category_str)

            # Gerar hash de importação baseado nos valores originais
            import_hash = Money99Parser.generate_import_hash(
                date=transaction_date,
                beneficiary=beneficiary_str,
                account=account_str,
                memo=memo_str,
                category=category,
                subcategory=subcategory,
                value=value
            )

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
                'original_index': None,  # Será preenchido após parsing
                'import_hash': import_hash,  # Hash baseado em valores originais
            }
            return result
        except Exception as e:
            logger.warning(f'Erro ao parsear linha {line_num}: {str(e)}')
            return None
    
    @staticmethod
    def parse_file(file_obj, encoding=None):
        """
        Parseia um arquivo completo e retorna lista de transações
        
        Args:
            file_obj: Arquivo aberto (file object)
            encoding: Encoding a ser usado (opcional, será detectado se não fornecido)
        
        Returns:
            Lista de dicionários com dados das transações parseadas
        """
        # Detectar encoding se não fornecido
        if encoding is None:
            encoding = Money99Parser.detect_encoding_from_file(file_obj)
        
        # Ler arquivo
        file_obj.seek(0)
        try:
            content = file_obj.read()
            if isinstance(content, bytes):
                content = content.decode(encoding)
            lines = content.splitlines()
        except UnicodeDecodeError:
            # Tentar com encoding alternativo
            file_obj.seek(0)
            content = file_obj.read()
            try:
                content = content.decode('utf-8', errors='replace')
            except:
                content = content.decode('latin1', errors='replace')
            lines = content.splitlines()
        
        transactions_data = []
        header_found = False

        for line_num, line in enumerate(lines, 1):
            line = line.rstrip('\n\r')
            
            # Verificar se é cabeçalho
            if not header_found and ('Data' in line and 'Favorecido' in line and 'Conta' in line):
                header_found = True
                continue

            if not header_found:
                continue

            # Ignorar linhas vazias
            if not line.strip():
                continue

            # Ignorar linhas de totalização
            if line.strip().startswith('Total'):
                continue

            # Ignorar linhas de seção (não começam com tab ou número de transação)
            line_stripped = line.strip()
            if not line.startswith('\t') and not (line_stripped and line_stripped[0].isdigit()):
                continue

            # Parsear linha de transação
            parsed = Money99Parser.parse_transaction_line(line, line_num)
            if parsed:
                # Adicionar flags para staging
                parsed['selected'] = True  # Por padrão, todas selecionadas
                parsed['edited'] = False
                transactions_data.append(parsed)

        return transactions_data
