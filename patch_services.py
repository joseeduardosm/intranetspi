filepath = '/root/aplicacoesspi/contratos/services.py'
with open(filepath, 'r') as f:
    c = f.read()

missing_functions = """
import calendar
from datetime import date, timedelta
import re

CONTRATO_NUMERO_RE = re.compile(r'^(?P<sequencial>\d{3})/(?P<ano>\d{4})$')

def quantize_money(value):
    from decimal import Decimal, ROUND_HALF_UP
    return (value or Decimal('0.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

def add_months(base_date, months):
    if not base_date:
        return None
    month_index = base_date.month - 1 + int(months or 0)
    year = base_date.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    day = min(base_date.day, last_day)
    return date(year, month, day)

def inclusive_end_date(start_date, months):
    final_date = add_months(start_date, months)
    if not final_date:
        return None
    return final_date - timedelta(days=1)

def ultimo_dia_mes(data_referencia):
    return date(
        data_referencia.year,
        data_referencia.month,
        calendar.monthrange(data_referencia.year, data_referencia.month)[1],
    )

def iterar_periodos_competencia(data_inicio, data_fim):
    if not data_inicio or not data_fim or data_fim < data_inicio:
        return []

    periodos = []
    cursor = data_inicio
    while cursor <= data_fim:
        fim_mes = ultimo_dia_mes(cursor)
        periodo_fim = min(fim_mes, data_fim)
        periodos.append((cursor, periodo_fim))
        cursor = periodo_fim + timedelta(days=1)
    return periodos

def parse_numero_contrato(value):
    match = CONTRATO_NUMERO_RE.match((value or '').strip())
    if not match:
        return None
    return int(match.group('sequencial')), int(match.group('ano'))
"""

if "def quantize_money" not in c:
    c = c.replace("from contratos.services import inclusive_end_date, iterar_periodos_competencia, quantize_money", missing_functions)
    
with open(filepath, 'w') as f:
    f.write(c)
