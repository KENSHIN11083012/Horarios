"""
Utilidades para manejo de fechas.
"""

from datetime import datetime, timedelta

def parse_date(date_str, format_str="%d/%m/%Y"):
    """Convierte string a objeto datetime."""
    return datetime.strptime(date_str, format_str)

def format_date(date, format_str="%d de %B de %Y"):
    """Formatea una fecha para mostrar."""
    return date.strftime(format_str)

def date_range(start_date, end_date):
    """Genera un rango de fechas entre inicio y fin, inclusivo."""
    current_date = start_date
    while current_date <= end_date:
        yield current_date
        current_date += timedelta(days=1)

def get_week_start(date):
    """Retorna la fecha de inicio de la semana (lunes)."""
    weekday = date.weekday()
    return date - timedelta(days=weekday)

def get_week_end(start_date):
    """Retorna la fecha final de una semana dado su inicio."""
    return start_date + timedelta(days=6)

def get_month_range(year, month):
    """Retorna el rango completo (primer y último día) de un mes."""
    import calendar
    _, last_day = calendar.monthrange(year, month)
    start_date = datetime(year, month, 1)
    end_date = datetime(year, month, last_day)
    return start_date, end_date

def is_weekend(date):
    """Verifica si una fecha cae en fin de semana."""
    return date.weekday() >= 5  # 5=Sábado, 6=Domingo

def get_nearby_dates(date, days_before=1, days_after=1):
    """Obtiene fechas cercanas a una fecha dada."""
    dates = []
    for i in range(-days_before, days_after+1):
        if i == 0:  # Saltar la fecha actual
            continue
        nearby_date = date + timedelta(days=i)
        dates.append(nearby_date)
    return dates