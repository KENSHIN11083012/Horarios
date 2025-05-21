"""
Cálculo de compensaciones según tipo de turno y fecha.
"""

from config import is_colombian_holiday

def calculate_compensation(date, shift_type):
    """
    Calcula la compensación para un turno específico según las nuevas reglas.
    
    Reglas:
    - Turnos DIURNOS: 1x
    - Turnos NOCTURNOS: 1.5x
    - Turnos FIN DE SEMANA DIURNO: 2x
    - Turnos FIN DE SEMANA NOCTURNO: 2.5x
    - Festivos tienen reglas especiales
    
    Args:
        date (datetime): Fecha del turno
        shift_type (str): Tipo de turno ('Mañana', 'Tarde', 'Noche')
        
    Returns:
        float: Factor de compensación
    """
    from config.settings import COMPENSATION_RATES
    
    # Determinar si es fin de semana
    is_weekend = date.weekday() >= 5  # 5=Sábado, 6=Domingo
    
    # Determinar si es turno nocturno
    is_night = (shift_type == "Noche")
    
    # Calcular tasa base según la combinación
    if is_weekend and is_night:
        # Fin de semana nocturno
        base_rate = COMPENSATION_RATES["FIN_DE_SEMANA_NOCTURNO"]
    elif is_weekend:
        # Fin de semana diurno
        base_rate = COMPENSATION_RATES["FIN_DE_SEMANA_DIURNO"]
    elif is_night:
        # Día normal, turno nocturno
        base_rate = COMPENSATION_RATES["NOCTURNO"]
    else:
        # Día normal, turno diurno
        base_rate = COMPENSATION_RATES["DIURNO"]
    
    # Ajuste por festivo (si aplica)
    if is_colombian_holiday(date):
        # Si ya es fin de semana, aplicamos un incremento adicional del 25%
        if is_weekend:
            base_rate *= 1.25
        else:
            # Si no es fin de semana, aplicamos la tarifa de fin de semana
            if is_night:
                base_rate = COMPENSATION_RATES["FIN_DE_SEMANA_NOCTURNO"]
            else:
                base_rate = COMPENSATION_RATES["FIN_DE_SEMANA_DIURNO"]
    
    return base_rate