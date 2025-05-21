"""
Funciones comunes compartidas entre el generador y selector de horarios.
"""

from datetime import timedelta
from config.settings import SHIFT_TYPES
from core.constraints import check_night_to_day_transition, check_consecutive_shifts, check_adequate_rest
from config import is_colombian_holiday

def create_date_index(schedule):
    """
    Crea un diccionario de acceso rápido para búsquedas O(1) por fecha.
    
    Args:
        schedule: Horario a indexar
        
    Returns:
        dict: Diccionario con fechas como claves y referencias a los días como valores
    """
    return {day["date"]: day for day in schedule.days}

def get_recent_shifts(worker, date, days=3):
    """
    Obtiene los turnos recientes de un trabajador en los últimos N días.
    
    Args:
        worker: Trabajador a analizar
        date: Fecha de referencia
        days: Número de días a considerar hacia atrás
        
    Returns:
        list: Lista de tuplas (fecha, turno) dentro del rango especificado
    """
    return [(d, s) for d, s in worker.shifts if 0 <= (date - d).days < days]

def predict_assignment_impact(schedule, worker, date, shift_type, date_index=None):
    """
    Predice el impacto de asignar un turno a un trabajador, identificando posibles
    violaciones futuras además de las actuales.
    
    Args:
        schedule: Horario actual
        worker: Trabajador a evaluar
        date: Fecha del turno
        shift_type: Tipo de turno
        date_index: Índice de fechas para acceso rápido
        
    Returns:
        tuple: (puede_asignar, [lista_de_violaciones], puntuación_impacto)
    """
    if date_index is None:
        date_index = create_date_index(schedule)
    
    violations = []
    impact_score = 0
    
    # 1. Verificar restricciones actuales
    if date in worker.days_off:
        violations.append("Viola día libre")
        impact_score += 40
    
    if any(d == date for d, _ in worker.shifts):
        violations.append("Ya tiene asignación ese día")
        impact_score += 100  # Bloqueante total
        return False, violations, float('inf')
    
    # Verificar restricciones básicas
    if check_night_to_day_transition(worker, date, shift_type):
        violations.append("Transición noche a día")
        impact_score += 30
    
    if check_consecutive_shifts(worker, date, shift_type):
        violations.append("Turnos consecutivos")
        impact_score += 20
    
    if not check_adequate_rest(worker, date, shift_type):
        violations.append("Descanso inadecuado")
        impact_score += 15
    
    # 2. Verificar impacto en turnos futuros (próximos 3 días)
    future_blocking = 0
    
    for future_days in range(1, 4):
        future_date = date + timedelta(days=future_days)
        
        # Solo evaluar si está dentro del período del horario
        if future_date > schedule.end_date:
            continue
            
        for future_shift in SHIFT_TYPES:
            # Simular la asignación actual para evaluar su efecto
            original_shifts = worker.shifts.copy()
            worker.shifts.append((date, shift_type))
            
            # Verificar si esta asignación impedirá trabajo futuro
            # Importar aquí para evitar importación circular
            from algorithms.generator import strictly_can_work_shift
            can_work_future = strictly_can_work_shift(worker, future_date, future_shift, schedule)
            
            # Deshacer la simulación
            worker.shifts = original_shifts
            
            if not can_work_future:
                # Calcular la criticidad de este bloqueo
                is_critical_day = future_date.weekday() >= 5 or is_colombian_holiday(future_date)
                shift_criticality = 3 if future_shift == "Noche" else (2 if future_shift == "Tarde" else 1)
                day_proximity = 4 - future_days  # 3, 2, 1 para días 1, 2, 3 en el futuro
                
                future_impact = day_proximity * shift_criticality * (2 if is_critical_day else 1)
                impact_score += future_impact
                future_blocking += 1
    
    if future_blocking > 0:
        violations.append(f"Bloquea {future_blocking} asignaciones futuras")
    
    # 3. Verificar si la asignación podría crear cadenas de turnos muy largas
    recent_shifts = get_recent_shifts(worker, date, days=5)  # Ampliado a 5 días para más contexto
    
    # Crear una copia temporal para simulación
    temp_shifts = [(d, s) for d, s in recent_shifts]
    temp_shifts.append((date, shift_type))  # Añadir la asignación simulada
    
    # Ordenar por fecha
    temp_shifts.sort(key=lambda x: x[0])
    
    # Buscar secuencias largas de días consecutivos
    consecutive_days = 1
    max_consecutive = 1
    
    for i in range(1, len(temp_shifts)):
        if (temp_shifts[i][0] - temp_shifts[i-1][0]).days == 1:
            consecutive_days += 1
            max_consecutive = max(max_consecutive, consecutive_days)
        else:
            consecutive_days = 1
    
    # Penalizar secuencias largas (más de 3 días seguidos)
    if max_consecutive > 3:
        fatigue_impact = (max_consecutive - 3) * 5
        impact_score += fatigue_impact
        violations.append(f"Crearía {max_consecutive} días consecutivos de trabajo")
    
    # 4. Verificar distribución de tipos de turno
    shift_counts = worker.get_shift_types_count().copy()
    shift_counts[shift_type] = shift_counts.get(shift_type, 0) + 1
    
    if shift_counts:
        max_count = max(shift_counts.values()) if shift_counts.values() else 0
        min_count = min(shift_counts.values()) if shift_counts.values() else 0
        diff = max_count - min_count
        
        if diff >= 3:
            imbalance_impact = diff * 2
            impact_score += imbalance_impact
            violations.append(f"Aumenta desequilibrio de tipos de turno a {diff}")
    
    # Determinar si se puede asignar basado en el impacto total
    can_assign = impact_score < 20 or (impact_score < 40 and shift_type == "Noche")
    
    return can_assign, violations, impact_score