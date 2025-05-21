"""
Definición y verificación de restricciones para horarios.
"""

from datetime import datetime, timedelta
from config.settings import SHIFT_TYPES

def check_adequate_rest(worker, date, shift_type):
    """
    Verifica estrictamente que haya descanso adecuado (mínimo 2 turnos).
    Retorna True si hay descanso adecuado, False si no hay suficiente descanso.
    """
    # Convertir turnos a una representación de línea de tiempo
    shift_indices = {"Mañana": 0, "Tarde": 1, "Noche": 2}
    current_date_idx = (date - datetime(2025, 1, 1)).days
    current_shift_idx = shift_indices[shift_type]
    
    # Posición temporal del nuevo turno (día * 3 + índice_turno)
    new_pos = current_date_idx * 3 + current_shift_idx
    
    # Verificar cada turno asignado previamente
    for work_date, work_shift in worker.shifts:
        date_idx = (work_date - datetime(2025, 1, 1)).days
        shift_idx = shift_indices[work_shift]
        existing_pos = date_idx * 3 + shift_idx
        
        # Calcular la diferencia en "espacios de turnos"
        diff = abs(new_pos - existing_pos)
        
        # Si la diferencia es menor o igual a 2, no hay suficiente descanso
        if 0 < diff <= 2:
            return False
    
    return True

def check_adequate_rest_relaxed(worker, date, shift_type):
    """
    Verificación relajada de descanso adecuado para casos críticos.
    Permite menos descanso (mínimo 1 turno) en lugar de los 2 habituales.
    """
    # Convertir turnos a una representación de línea de tiempo
    shift_indices = {"Mañana": 0, "Tarde": 1, "Noche": 2}
    current_date_idx = (date - datetime(2025, 1, 1)).days
    current_shift_idx = shift_indices[shift_type]
    
    # Posición temporal del nuevo turno (día * 3 + índice_turno)
    new_pos = current_date_idx * 3 + current_shift_idx
    
    # Verificar cada turno asignado previamente
    for work_date, work_shift in worker.shifts:
        date_idx = (work_date - datetime(2025, 1, 1)).days
        shift_idx = shift_indices[work_shift]
        existing_pos = date_idx * 3 + shift_idx
        
        # Calcular la diferencia en "espacios de turnos"
        diff = abs(new_pos - existing_pos)
        
        # Si la diferencia es exactamente 1, no hay suficiente descanso
        # RELAJADO: Solo rechaza turnos consecutivos (diferencia de 1), permite diferencia de 2
        if diff == 1:
            return False
    
    return True

def check_night_to_day_transition(worker, date, shift_type):
    """
    Verifica si habría transición de noche a día.
    Retorna True si hay violación de restricción, False si es válido.
    """
    # Si no es turno de mañana, no aplica esta restricción
    if shift_type != "Mañana":
        return False
    
    # Verificar si trabajó turno nocturno el día anterior
    prev_date = date - timedelta(days=1)
    worked_night_prev = any(d == prev_date and s == "Noche" for d, s in worker.shifts)
    
    return worked_night_prev

def check_consecutive_shifts(worker, date, shift_type):
    """
    Verifica si habría turnos consecutivos en el mismo día.
    Retorna True si hay violación, False si es válido.
    """
    shift_indices = {"Mañana": 0, "Tarde": 1, "Noche": 2}
    current_idx = shift_indices[shift_type]
    
    # Verificar otros turnos en el mismo día
    for work_date, work_shift in worker.shifts:
        if work_date == date:
            existing_idx = shift_indices[work_shift]
            # Verificar si son consecutivos (diferencia de 1)
            if abs(current_idx - existing_idx) == 1:
                return True
    
    return False

def validate_schedule(schedule):
    """
    Valida que el horario cumpla todas las restricciones.
    Retorna una lista de violaciones encontradas.
    """
    violations = []
    
    # 1. Verificar cantidad de tecnólogos e ingenieros por turno
    for day in schedule.days:
        date = day["date"]
        date_str = date.strftime("%Y-%m-%d")
        
        for shift_type in SHIFT_TYPES:
            shift = day["shifts"][shift_type]
            
            # Verificar número de tecnólogos
            from config.settings import TECHS_PER_SHIFT
            required_techs = TECHS_PER_SHIFT[shift_type]
            actual_techs = len(shift["technologists"])
            
            if actual_techs != required_techs:
                violations.append(
                    f"Error en {date_str} {shift_type}: {actual_techs} tecnólogos " +
                    f"cuando deberían ser {required_techs}"
                )
            
            # Verificar que haya un ingeniero
            if shift["engineer"] is None:
                violations.append(
                    f"Error en {date_str} {shift_type}: Falta ingeniero asignado"
                )
    
    # 2. Verificar restricciones individuales para cada trabajador
    for worker in schedule.get_all_workers():
        # Ordenar turnos por fecha y tipo
        shifts = sorted(worker.shifts, key=lambda x: (x[0], {"Mañana": 0, "Tarde": 1, "Noche": 2}[x[1]]))
        
        for i in range(len(shifts) - 1):
            date1, shift1 = shifts[i]
            date2, shift2 = shifts[i + 1]
            
            # Verificar turnos consecutivos (mismo día)
            if date1 == date2:
                shift_indices = {"Mañana": 0, "Tarde": 1, "Noche": 2}
                if abs(shift_indices[shift1] - shift_indices[shift2]) == 1:
                    violations.append(
                        f"{worker.get_formatted_id()} tiene turnos consecutivos el " +
                        f"{date1.strftime('%Y-%m-%d')}: {shift1} y {shift2}"
                    )
            
            # Verificar transición noche a día
            if shift1 == "Noche" and shift2 == "Mañana" and (date2 - date1).days == 1:
                violations.append(
                    f"{worker.get_formatted_id()} tiene transición de noche a día: " +
                    f"{date1.strftime('%Y-%m-%d')} Noche -> {date2.strftime('%Y-%m-%d')} Mañana"
                )
            
            # Verificar períodos de descanso
            shift_indices = {"Mañana": 0, "Tarde": 1, "Noche": 2}
            idx1 = (date1 - datetime(2025, 1, 1)).days * 3 + shift_indices[shift1]
            idx2 = (date2 - datetime(2025, 1, 1)).days * 3 + shift_indices[shift2]
            
            if 0 < idx2 - idx1 <= 2:
                violations.append(
                    f"{worker.get_formatted_id()} no tiene descanso adecuado entre " +
                    f"{date1.strftime('%Y-%m-%d')} {shift1} y {date2.strftime('%Y-%m-%d')} {shift2}"
                )
    
    return violations