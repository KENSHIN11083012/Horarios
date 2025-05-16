"""
Algoritmo principal para la generación de horarios.
"""

import random
from datetime import datetime, timedelta
from config.settings import SHIFT_TYPES, TECHS_PER_SHIFT, ENG_PER_SHIFT

def generate_schedule(start_date, end_date, technologists, engineers):
    """
    Genera un horario completo para el período especificado.
    
    Args:
        start_date: Fecha de inicio
        end_date: Fecha de fin
        technologists: Lista de tecnólogos
        engineers: Lista de ingenieros
        
    Returns:
        Schedule: Horario generado
    """
    from core.schedule import Schedule
    from utils.date_utils import date_range
    
    # Inicializar cronograma
    schedule = Schedule(start_date, end_date, technologists + engineers)
    
    # Generar el cronograma día a día, turno por turno
    for current_date in date_range(start_date, end_date):
        print(f"Generando turnos para {current_date.strftime('%d/%m/%Y')}...")
        
        for shift_type in SHIFT_TYPES:
            # Asignar tecnólogos
            assign_technologists(schedule, current_date, shift_type, technologists)
            
            # Asignar ingenieros
            assign_engineers(schedule, current_date, shift_type, engineers)
    
    # Asegurar que cada trabajador tenga un día libre semanal
    ensure_weekly_days_off(schedule)
    
    return schedule

def assign_technologists(schedule, date, shift_type, technologists):
    """Asigna tecnólogos a un turno específico."""
    # Encontrar tecnólogos elegibles para este turno
    from algorithms.selector import select_workers_for_shift
    
    eligible_techs = [t for t in technologists if t.can_work_shift(date, shift_type)]
    
    # Determinar cuántos tecnólogos se necesitan
    num_needed = TECHS_PER_SHIFT[shift_type]
    
    # Verificar si hay suficientes tecnólogos disponibles
    if len(eligible_techs) < num_needed:
        print(f"Advertencia: No hay suficientes tecnólogos para {date.strftime('%d/%m/%Y')} {shift_type}.")
        selected_techs = eligible_techs  # Usar todos los disponibles
    else:
        # Seleccionar tecnólogos basados en equidad y rotación
        selected_techs = select_workers_for_shift(
            eligible_techs, num_needed, date, shift_type
        )
    
    # Asignar tecnólogos seleccionados al turno
    for tech in selected_techs:
        schedule.assign_worker(tech, date, shift_type)
    
    return len(selected_techs) == num_needed

def assign_engineers(schedule, date, shift_type, engineers):
    """Asigna ingenieros a un turno específico."""
    from algorithms.selector import select_workers_for_shift
    
    eligible_engs = [e for e in engineers if e.can_work_shift(date, shift_type)]
    
    if len(eligible_engs) < ENG_PER_SHIFT:
        print(f"Advertencia: No hay suficientes ingenieros para {date.strftime('%d/%m/%Y')} {shift_type}.")
        if eligible_engs:
            selected_eng = eligible_engs[0]
        else:
            return False
    else:
        selected_engs = select_workers_for_shift(
            eligible_engs, ENG_PER_SHIFT, date, shift_type
        )
        selected_eng = selected_engs[0] if selected_engs else None
    
    if selected_eng:
        schedule.assign_worker(selected_eng, date, shift_type)
        return True
    
    return False

def ensure_weekly_days_off(schedule):
    """
    Asegura que cada trabajador tenga un día libre por semana,
    preferiblemente después de un turno nocturno.
    """
    from utils.date_utils import date_range, get_week_start, get_week_end
    
    # Procesar semana por semana
    current_date = schedule.start_date
    while current_date <= schedule.end_date:
        week_start = get_week_start(current_date)
        week_end = get_week_end(week_start)
        
        # Verificar cada trabajador
        for worker in schedule.get_all_workers():
            # Obtener días libres en esta semana
            days_off_in_week = worker.get_days_off_in_week(week_start)
            
            # Si no hay día libre en esta semana, tratar de asignar uno
            if not days_off_in_week:
                # Encontrar noches trabajadas en esta semana
                night_shifts = [(d, s) for d, s in worker.shifts 
                              if s == "Noche" and week_start <= d <= week_end]
                
                if night_shifts:
                    # Ordenar por fecha
                    night_shifts.sort()
                    # Tomar el último turno nocturno y dar el día siguiente libre
                    last_night_date = night_shifts[-1][0]
                    next_day = last_night_date + timedelta(days=1)
                    
                    if next_day <= week_end:
                        worker.add_day_off(next_day)
                else:
                    # Si no tiene turnos nocturnos, asignar un día libre cualquiera
                    available_days = []
                    for day in date_range(week_start, week_end):
                        # Verificar si ya tiene turno asignado ese día
                        has_shift_on_day = any(d == day for d, _ in worker.shifts)
                        if not has_shift_on_day:
                            available_days.append(day)
                    
                    if available_days:
                        day_off = random.choice(available_days)
                        worker.add_day_off(day_off)
        
        # Avanzar a la siguiente semana
        current_date = week_end + timedelta(days=1)