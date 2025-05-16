"""
Módulo de configuración para el generador de horarios.
"""

from datetime import datetime

def is_colombian_holiday(date):
    """Verifica si una fecha es festivo en Colombia."""
    from config.settings import COLOMBIAN_HOLIDAYS_2025
    date_str = date.strftime("%m-%d")
    return date_str in COLOMBIAN_HOLIDAYS_2025