"""
Definición y verificación de restricciones para horarios.
"""

from datetime import datetime, timedelta
from config.settings import SHIFT_TYPES

# Funciones para verificar restricciones individuales

def check_consecutive_shifts(worker, date, shift_type):
    """
    Verifica si este turno sería consecutivo a uno existente.
    Retorna True si habría violación de restricción.
    """
    # Verificar turno de noche del día anterior
    prev_date = date - timedelta(days=1)
    if shift_type == "Mañana" and any(d == prev_date and s == "Noche" for d, s in worker.shifts):
        return True
    
    # Verificar turnos en el mismo día
    shift_indices = {"Mañana": 0, "Tarde": 1, "Noche": 2}
    for d, s in worker.shifts:
        if d == date:
            s_idx = shift_indices[s]
            current_idx = shift_indices[shift_type]
            if abs(s_idx - current_idx) == 1:  # Turnos adyacentes
                return True
    
    return False

def check_night_to_day_transition(worker, date, shift_type):
    """
    Verifica si habría transición de noche a día.
    Retorna True si habría violación de restricción.
    """
    prev_date = date - timedelta(days=1)
    worked_night_prev = any(d == prev_date and s == "Noche" for d, s in worker.shifts)
    is_morning_shift = shift_type == "Mañana"
    
    return worked_night_prev and is_morning_shift

def check_adequate_rest(worker, date, shift_type):
    """
    Verifica si hay descanso adecuado (mínimo 2 turnos).
    Retorna True si hay descanso adecuado.
    """
    # Convertir turnos a una representación de línea de tiempo
    shift_indices = {"Mañana": 0, "Tarde": 1, "Noche": 2}
    
    # Calcular la posición del nuevo turno
    new_timeline_pos = (date - datetime(2025, 1, 1)).days * 3 + shift_indices[shift_type]
    
    for d, s in worker.shifts:
        # Calcular posición del turno existente
        existing_pos = (d - datetime(2025, 1, 1)).days * 3 + shift_indices[s]
        
        # Verificar si hay menos de 2 turnos de descanso
        if 0 < abs(new_timeline_pos - existing_pos) <= 2:
            return False
    
    return True

def validate_schedule(schedule):
    """
    Valida que un horario cumpla con todas las restricciones.
    Retorna lista de violaciones encontradas.
    """
    violations = []
    
    # TODO: Implementar validación completa de horario
    # Esta función podría usarse para verificar el horario final
    
    return violations