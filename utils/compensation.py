"""
Cálculo de compensaciones según tipo de turno y fecha.
"""

from config.settings import NIGHT_SHIFT_RATE, HOLIDAY_RATE, SUNDAY_RATE
from config import is_colombian_holiday

def calculate_compensation(date, shift_type):
    """
    Calcula la compensación para un turno específico.
    
    Args:
        date (datetime): Fecha del turno
        shift_type (str): Tipo de turno ('Mañana', 'Tarde', 'Noche')
        
    Returns:
        float: Factor de compensación
    """
    base_rate = 1.0
    
    # Aplicar factor por turno nocturno
    if shift_type == "Noche":
        base_rate *= NIGHT_SHIFT_RATE
    
    # Aplicar factor por día festivo o domingo
    weekday = date.weekday()
    is_holiday = is_colombian_holiday(date)
    
    if is_holiday:
        base_rate *= HOLIDAY_RATE
    elif weekday == 6:  # Domingo
        base_rate *= SUNDAY_RATE
    
    return base_rate