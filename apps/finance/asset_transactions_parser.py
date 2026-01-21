"""
Utilitário para parsing de arquivos asset_transactions.txt
Similar ao transactions_parser.py mas específico para transações de ativos
"""
import re
import logging
import hashlib
from decimal import Decimal, InvalidOperation
from datetime import datetime

logger = logging.getLogger(__name__)


class AssetTransactionsParser:
    """Classe utilitária para parsing de arquivos de transações de ativos"""
    
    @staticmethod
    def detect_encoding_from_file(file_obj):
        """Detecta encoding de um arquivo já aberto (para uso com upload)"""
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
            date_obj = datetime.strptime(date_str.strip(), '%d/%m/%Y').date()
            return date_obj
        except ValueError:
            return None
    
    @staticmethod
    def parse_amount(amount_str):
        """Converte valor monetário do formato brasileiro para Decimal"""
        try:
            # Remover espaços
            amount_str = amount_str.strip()
            
            if not amount_str:
                return Decimal('0')
            
            # Verificar se é negativo
            is_negative = amount_str.startswith('-')
            if is_negative:
                amount_str = amount_str[1:]
            
            # Remover pontos de milhar e substituir vírgula por ponto
            amount_str = amount_str.replace('.', '').replace(',', '.')
            
            value = Decimal(amount_str)
            if is_negative:
                value = -value
            
            return value
        except (ValueError, InvalidOperation):
            return None
    
    @staticmethod
    def parse_quantity(quantity_str):
        """Converte quantidade do formato brasileiro para Decimal"""
        try:
            quantity_str = quantity_str.strip()
            
            if not quantity_str:
                return Decimal('0')
            
            # Remover pontos de milhar e substituir vírgula por ponto
            quantity_str = quantity_str.replace('.', '').replace(',', '.')
            
            return Decimal(quantity_str)
        except (ValueError, InvalidOperation):
            return Decimal('0')
    
    @staticmethod
    def extract_asset_code(investment_str):
        """
        Extrai código do ativo do campo Investimento.
        Formato esperado: "Tipo: Nome (CÓDIGO)" ou "Nome (CÓDIGO)" ou apenas "CÓDIGO"
        Exemplos:
        - "Ação: Klabin (KLBN11)" -> "KLBN11"
        - "Cripto: Ethereum (ETH)" -> "ETH"
        - "Renda fixa: CDB" -> "CDB" (sem parênteses, usar o nome após ":")
        """
        if not investment_str:
            return None, None
        
        investment_str = investment_str.strip()
        
        # Tentar extrair código entre parênteses
        match = re.search(r'\(([^)]+)\)', investment_str)
        if match:
            code = match.group(1).strip()
            # Extrair nome (tudo antes dos parênteses, removendo prefixo tipo se houver)
            name_part = investment_str[:match.start()].strip()
            if ':' in name_part:
                name = name_part.split(':', 1)[1].strip()
            else:
                name = name_part
            if not name:
                name = code
            return code, name
        
        # Se não tem parênteses, tentar extrair após ":"
        if ':' in investment_str:
            parts = investment_str.split(':', 1)
            code = parts[1].strip()
            name = code
            return code, name
        
        # Se não tem nem parênteses nem ":", usar o texto completo
        return investment_str, investment_str
    
    @staticmethod
    def infer_asset_type(investment_str, asset_code):
        """Infere o tipo de ativo baseado no nome do investimento"""
        investment_lower = investment_str.lower()
        code_upper = asset_code.upper() if asset_code else ''
        
        if 'ação' in investment_lower or 'acao' in investment_lower:
            return 'STOCK'
        elif 'fii' in investment_lower or 'fundo imobiliário' in investment_lower:
            return 'FII'
        elif 'cripto' in investment_lower or 'crypto' in investment_lower:
            return 'CRYPTO'
        elif 'renda fixa' in investment_lower or 'cdb' in investment_lower.lower():
            return 'BOND'
        elif 'fgts' in investment_lower:
            return 'BOND'
        elif 'fundo' in investment_lower and 'fi:' in investment_lower:
            return 'FII'
        elif code_upper.endswith('11') and len(code_upper) >= 5:
            # Códigos terminados em 11 geralmente são FIIs
            return 'FII'
        elif code_upper.endswith('3') or code_upper.endswith('4'):
            # Códigos terminados em 3 ou 4 geralmente são ações
            return 'STOCK'
        else:
            return 'OTHER'
    
    @staticmethod
    def map_operation_type(activity_str, category_str=''):
        """
        Mapeia atividade para operation_type do modelo.
        Atividades possíveis: Comprar, Vender, Dividendo, Juros, Adicionar ações
        """
        if not activity_str:
            return None
        
        activity_lower = activity_str.strip().lower()
        category_lower = category_str.lower() if category_str else ''
        
        if 'comprar' in activity_lower or 'compra' in activity_lower:
            return 'BUY'
        elif 'vender' in activity_lower or 'venda' in activity_lower:
            return 'SELL'
        elif 'dividendo' in activity_lower:
            return 'DIVIDEND'
        elif 'juros' in activity_lower:
            # Verificar se é JCP ou INTEREST baseado na categoria
            if 'capital próprio' in category_lower or 'jcp' in category_lower:
                return 'JCP'
            else:
                return 'INTEREST'
        elif 'adicionar' in activity_lower and 'ações' in activity_lower:
            # Se quantidade > 0, será tratado como BUY; senão, como BONUS
            return 'BUY'  # Será ajustado na view se necessário
        elif 'bonificação' in activity_lower or 'bonus' in activity_lower:
            return 'BONUS'
        elif 'resgate' in activity_lower:
            return 'REDEMPTION'
        else:
            return None
    
    @staticmethod
    def normalize_name(name):
        """Normaliza nome removendo espaços extras"""
        if not name:
            return ''
        return ' '.join(name.split())
    
    @staticmethod
    def generate_import_hash(date, investment_account, asset_code, operation_type, quantity, price, total, 
                            memo, cash_account, category, line_num):
        """
        Gera hash MD5 baseado nos dados originais da transação para prevenir duplicatas.
        
        Args:
            date: Data da transação (objeto date)
            investment_account: Nome da conta de investimento (string)
            asset_code: Código do ativo (string)
            operation_type: Tipo de operação (string)
            quantity: Quantidade (Decimal)
            price: Preço (Decimal)
            total: Valor total (Decimal)
            memo: Memo/anotações (string)
            cash_account: Nome da conta de transferência (string)
            category: Categoria (string)
            line_num: Número da linha no arquivo original (int)
        
        Returns:
            Hash MD5 hexadecimal de 32 caracteres
        """
        # Normalizar valores
        date_str = date.strftime('%Y-%m-%d') if date else ''
        investment_account_str = AssetTransactionsParser.normalize_name(investment_account) if investment_account else ''
        asset_code_str = asset_code.upper().strip() if asset_code else ''
        operation_type_str = operation_type if operation_type else ''
        quantity_str = f"{quantity:.8f}" if quantity is not None else '0.00000000'
        price_str = f"{price:.4f}" if price is not None else '0.0000'
        total_str = f"{total:.2f}" if total is not None else '0.00'
        memo_str = ' '.join(memo.split()) if memo else ''
        cash_account_str = AssetTransactionsParser.normalize_name(cash_account) if cash_account else ''
        category_str = AssetTransactionsParser.normalize_name(category) if category else ''
        line_num_str = str(line_num) if line_num is not None else ''
        
        # Concatenar: Data|ContaInvest|Ativo|Operacao|Qtde|Preco|Total|Memo|ContaCash|Categoria|LineNum
        hash_string = f"{date_str}|{investment_account_str}|{asset_code_str}|{operation_type_str}|{quantity_str}|{price_str}|{total_str}|{memo_str}|{cash_account_str}|{category_str}|{line_num_str}"
        
        # Gerar MD5
        return hashlib.md5(hash_string.encode('utf-8')).hexdigest()
    
    @staticmethod
    def parse_transaction_line(line, line_num):
        """Parseia uma linha de transação de ativo"""
        try:
            # Dividir por tabs
            parts = [p.strip() for p in line.split('\t')]
            
            # Formato esperado: Data | Conta | Investimento | Atividade | Quantidade | Preço | Comissão | Total | Memo | Conta de transferência | Categoria
            # Mínimo necessário: Data, Conta, Investimento, Atividade
            if len(parts) < 4:
                return None
            
            # Extrair campos
            date_str = parts[0] if len(parts) > 0 else ''
            investment_account_str = parts[1] if len(parts) > 1 else ''
            investment_str = parts[2] if len(parts) > 2 else ''
            activity_str = parts[3] if len(parts) > 3 else ''
            quantity_str = parts[4] if len(parts) > 4 else ''
            price_str = parts[5] if len(parts) > 5 else ''
            fees_str = parts[6] if len(parts) > 6 else ''
            total_str = parts[7] if len(parts) > 7 else ''
            memo_str = parts[8] if len(parts) > 8 else ''
            cash_account_str = parts[9] if len(parts) > 9 else ''
            category_str = parts[10] if len(parts) > 10 else ''
            
            # Validar campos obrigatórios
            if not date_str or not investment_account_str or not investment_str or not activity_str:
                return None
            
            # Validar e converter data
            transaction_date = AssetTransactionsParser.parse_date(date_str)
            if not transaction_date:
                return None
            
            # Extrair código e nome do ativo
            asset_code, asset_name = AssetTransactionsParser.extract_asset_code(investment_str)
            if not asset_code:
                return None
            
            # Mapear tipo de operação
            operation_type = AssetTransactionsParser.map_operation_type(activity_str, category_str)
            if not operation_type:
                return None
            
            # Converter valores
            quantity = AssetTransactionsParser.parse_quantity(quantity_str)
            price = AssetTransactionsParser.parse_amount(price_str) if price_str else Decimal('0')
            fees = AssetTransactionsParser.parse_amount(fees_str) if fees_str else Decimal('0')
            total = AssetTransactionsParser.parse_amount(total_str) if total_str else Decimal('0')
            
            # Determinar se usa total_value ou income_value
            # Para operações de rendimento (DIVIDEND, JCP, INTEREST), usar income_value
            # Para outras operações, usar total_value
            is_income_operation = operation_type in ['DIVIDEND', 'JCP', 'INTEREST', 'AMORTIZATION']
            
            # Gerar hash de importação
            import_hash = AssetTransactionsParser.generate_import_hash(
                date=transaction_date,
                investment_account=investment_account_str,
                asset_code=asset_code,
                operation_type=operation_type,
                quantity=quantity,
                price=price,
                total=total,
                memo=memo_str,
                cash_account=cash_account_str,
                category=category_str,
                line_num=line_num
            )
            
            result = {
                'date': transaction_date,
                'investment_account': investment_account_str,
                'asset_name': asset_name,
                'asset_code': asset_code,
                'investment_str': investment_str,  # Manter original para inferir tipo
                'operation_type': operation_type,
                'quantity': quantity,
                'price': price,
                'fees': fees,
                'total': total,
                'is_income_operation': is_income_operation,
                'notes': memo_str,
                'cash_account': cash_account_str,
                'category': category_str,
                'line_num': line_num,
                'original_index': None,  # Será preenchido após parsing
                'import_hash': import_hash,
                'selected': False,  # Por padrão, nenhuma selecionada - usuário deve selecionar explicitamente
                'edited': False,
            }
            return result
        except Exception as e:
            logger.warning(f'Erro ao parsear linha {line_num}: {str(e)}')
            return None
    
    @staticmethod
    def parse_file(file_obj, encoding=None):
        """
        Parseia um arquivo completo e retorna lista de transações de ativos
        
        Args:
            file_obj: Arquivo aberto (file object)
            encoding: Encoding a ser usado (opcional, será detectado se não fornecido)
        
        Returns:
            Lista de dicionários com dados das transações parseadas
        """
        # Detectar encoding se não fornecido
        if encoding is None:
            encoding = AssetTransactionsParser.detect_encoding_from_file(file_obj)
        
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
            if not header_found and ('Data' in line and 'Conta' in line and 'Investimento' in line and 'Atividade' in line):
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
            
            # Parsear linha de transação
            parsed = AssetTransactionsParser.parse_transaction_line(line, line_num)
            if parsed:
                transactions_data.append(parsed)
        
        # Adicionar original_index após parsing
        for idx, trans in enumerate(transactions_data):
            trans['original_index'] = idx
        
        return transactions_data
