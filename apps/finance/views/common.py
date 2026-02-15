"""
Shared utilities for finance views (session serialization, etc.).
"""
from datetime import date
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


def prepare_transactions_for_session(transactions_data):
    """
    Converte objetos date e Decimal para strings antes de salvar na sessão.
    A sessão Django não serializa objetos date e Decimal diretamente.
    Preserva todos os campos, incluindo import_hash.
    """
    transactions_data_for_session = []
    missing_hash_count = 0
    for trans in transactions_data:
        trans_copy = {}
        for key, value in trans.items():
            if value is None:
                trans_copy[key] = None
            elif isinstance(value, date):
                trans_copy[key] = value.isoformat()
            elif isinstance(value, Decimal):
                trans_copy[key] = str(value)
            elif isinstance(value, (int, float, str, bool)):
                trans_copy[key] = value
            elif isinstance(value, (list, tuple)):
                trans_copy[key] = [str(v) if isinstance(v, (date, Decimal)) else v for v in value]
            elif isinstance(value, dict):
                trans_copy[key] = {
                    k: (v.isoformat() if isinstance(v, date) else str(v) if isinstance(v, Decimal) else v)
                    for k, v in value.items()
                }
            else:
                trans_copy[key] = str(value)
        if 'import_hash' in trans and 'import_hash' not in trans_copy:
            missing_hash_count += 1
            if trans.get('import_hash'):
                trans_copy['import_hash'] = trans['import_hash']
        transactions_data_for_session.append(trans_copy)
    if missing_hash_count > 0:
        logger.debug(
            'prepare_transactions_for_session: import_hash lost for %s of %s transactions',
            missing_hash_count, len(transactions_data)
        )
    return transactions_data_for_session
