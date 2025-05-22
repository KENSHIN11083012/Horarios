"""
Algoritmo principal para la generación de horarios.
Funciones coordinadoras que orquestan el proceso completo.
"""

import re
from datetime import datetime, timedelta
from config.settings import SHIFT_TYPES, TECHS_PER_SHIFT, ENG_PER_SHIFT
from core.schedule import Schedule
from utils.date_utils import date_range, get_week_start, get_week_end
from core.constraints import validate_schedule, check_night_to_day_transition
from core.constraints import check_consecutive_shifts, check_adequate_rest, check_adequate_rest_relaxed
from utils.compensation import calculate_compensation
from config import is_colombian_holiday

# Importar de los módulos refactorizados
from algorithms.common import create_date_index, predict_assignment_impact, get_recent_shifts
from algorithms.selector import select_workers_proactively
from algorithms.day_off_planner import ensure_weekly_days_off, verify_weekly_days_off
from algorithms.balancer import balance_workload, optimize_fairness
from algorithms.repair import fix_schedule_issues, resolve_constraint_violations

def generate_schedule(start_date, end_date, technologists, engineers):
    """
    Genera un horario completo para el período especificado con validación y corrección.
    Versión mejorada con detección proactiva de violaciones.
    
    Args:
        start_date: Fecha de inicio del periodo
        end_date: Fecha final del periodo
        technologists: Lista de tecnólogos disponibles
        engineers: Lista de ingenieros disponibles
        
    Returns:
        Schedule: Objeto horario completo validado y optimizado
    """
    print("Iniciando generación de horario con detección proactiva de violaciones...")
    
    # Inicializar cronograma
    schedule = Schedule(start_date, end_date, technologists + engineers)
    
    # Crear índice de fechas para búsquedas eficientes O(1)
    date_index = create_date_index(schedule)
    print(f"  Índice de fechas creado para {len(date_index)} días.")
    
    # FASE DE PREPARACIÓN
    critical_days = identify_critical_days(start_date, end_date)
    
    # FASE DE ASIGNACIÓN INICIAL ESTRATÉGICA
    # Fase 1: Pre-asignar ingenieros (prioritario)
    preassign_engineers(schedule, start_date, end_date, engineers, date_index)
    
    # Fase 2: Pre-asignar tecnólogos para turnos nocturnos (críticos)
    preassign_night_technologists(schedule, start_date, end_date, technologists, date_index)
    
    # Fase 3: Generar turnos restantes priorizando días críticos
    generate_remaining_shifts_proactive(
        schedule, start_date, end_date, technologists, engineers, critical_days, date_index
    )
    
    # FASE DE OPTIMIZACIÓN Y VALIDACIÓN
    # Asignar días libres semanales obligatorios
    ensure_weekly_days_off(schedule, technologists, engineers, date_index)
    
    # Balancear carga de trabajo
    balance_workload(schedule, technologists, engineers, date_index)
    
    # Verificar si quedan problemas de cobertura (deberían ser pocos)
    fix_schedule_issues(schedule, technologists, engineers, date_index)
    
    # Corregir las pocas violaciones que pudieran quedar
    resolve_constraint_violations(schedule, technologists, engineers, date_index)
    
    # Verificación final de días libres semanales
    verify_weekly_days_off(schedule, technologists, engineers)
    
    # Optimización final para equidad económica
    optimize_fairness(schedule, technologists, engineers, date_index)
    
    # Reporte final
    report_final_schedule_status(schedule)
    
    return schedule

def identify_critical_days(start_date, end_date):
    """
    Identifica días críticos como fines de semana y festivos colombianos.
    
    Args:
        start_date: Fecha de inicio del periodo
        end_date: Fecha final del periodo
        
    Returns:
        list: Lista de fechas consideradas críticas
    """
    print("Identificando días críticos...")
    critical_days = set()  # Usar set para evitar duplicados automáticamente
    weekend_count = 0
    holiday_count = 0
    
    for current_date in date_range(start_date, end_date):
        # Considerar fines de semana como críticos
        if current_date.weekday() >= 5:  # 5=Sábado, 6=Domingo
            critical_days.add(current_date)
            weekend_count += 1
        
        # Considerar festivos como críticos
        if is_colombian_holiday(current_date):
            critical_days.add(current_date)
            holiday_count += 1
    
    critical_days_list = list(critical_days)
    print(f"  Identificados {len(critical_days_list)} días críticos (incluyendo {weekend_count} fines de semana y {holiday_count} festivos).")
    return critical_days_list

def report_final_schedule_status(schedule):
    """
    Valida y reporta el estado final del horario.
    
    Args:
        schedule: Horario a validar
    """
    violations = validate_schedule(schedule)
    
    if violations:
        violation_types = {}
        for v in violations:
            v_type = "Cobertura" if "tecnólogos cuando deberían ser" in v or "Falta ingeniero" in v else "Restricción"
            violation_types[v_type] = violation_types.get(v_type, 0) + 1
            
        print(f"ADVERTENCIA: Se encontraron {len(violations)} problemas en el horario:")
        for v_type, count in violation_types.items():
            print(f"  - {count} violaciones de tipo {v_type}")
            
        # Mostrar ejemplos de cada tipo
        shown = {v_type: 0 for v_type in violation_types}
        for v in violations:
            v_type = "Cobertura" if "tecnólogos cuando deberían ser" in v or "Falta ingeniero" in v else "Restricción"
            if shown[v_type] < 3:  # Mostrar hasta 3 ejemplos de cada tipo
                print(f"    • {v}")
                shown[v_type] += 1
    else:
        print("✓ Horario generado cumple con todas las restricciones.")

def preassign_engineers(schedule, start_date, end_date, engineers, date_index):
    """
    Pre-asigna ingenieros a todos los turnos como primera prioridad.
    
    Args:
        schedule: Horario a modificar
        start_date: Fecha de inicio
        end_date: Fecha final
        engineers: Lista de ingenieros disponibles
        date_index: Índice de fechas para acceso rápido
    """
    print("Fase 1: Pre-asignando ingenieros para todos los turnos...")
    
    # Contador para estadísticas
    assignments = 0
    
    for current_date in date_range(start_date, end_date):
        for shift_type in SHIFT_TYPES:
            # Verificar si ya hay ingeniero asignado
            day_data = date_index.get(current_date)
            if day_data and day_data["shifts"][shift_type]["engineer"] is not None:
                continue
                
            # Encontrar ingenieros elegibles
            eligible_engs = [e for e in engineers if strictly_can_work_shift(e, current_date, shift_type, schedule)]
            
            # Si hay elegibles, asignar el que tenga menos turnos
            if eligible_engs:
                eligible_engs.sort(key=lambda e: (e.get_shift_count(), e.get_shift_types_count().get(shift_type, 0)))
                selected_eng = eligible_engs[0]
                schedule.assign_worker(selected_eng, current_date, shift_type)
                assignments += 1
    
    print(f"  Se realizaron {assignments} asignaciones de ingenieros.")


def preassign_night_technologists(schedule, start_date, end_date, technologists, date_index):
    """
    Pre-asigna tecnólogos a turnos nocturnos que son críticos.
    
    Args:
        schedule: Horario a modificar
        start_date: Fecha de inicio
        end_date: Fecha final
        technologists: Lista de tecnólogos disponibles
        date_index: Índice de fechas para acceso rápido
    """
    print("Fase 2: Pre-asignando tecnólogos para turnos nocturnos...")
    
    # Contador para estadísticas
    assignments = 0
    incomplete = 0
    
    for current_date in date_range(start_date, end_date):
        shift_type = "Noche"
        
        # Verificar si ya está completo el turno
        day_data = date_index.get(current_date)
        if day_data:
            shift_data = day_data["shifts"][shift_type]
            if len(shift_data["technologists"]) >= 2:
                continue
        
        # Encontrar tecnólogos elegibles para turnos nocturnos
        eligible_techs = [t for t in technologists if strictly_can_work_shift(t, current_date, shift_type, schedule)]
        
        # Siempre se necesitan 2 para turno nocturno
        num_needed = 2
        
        # Si hay suficientes elegibles, seleccionar los que tienen menos turnos
        if len(eligible_techs) >= num_needed:
            # Ordenar por número de turnos y luego por número de turnos nocturnos
            eligible_techs.sort(key=lambda t: (t.get_shift_count(), t.get_shift_types_count().get(shift_type, 0)))
            selected_techs = eligible_techs[:num_needed]
            
            # Asignar
            for tech in selected_techs:
                schedule.assign_worker(tech, current_date, shift_type)
                assignments += 1
        else:
            incomplete += 1
    
    print(f"  Se asignaron {assignments} tecnólogos a {assignments//2} turnos nocturnos.")
    if incomplete > 0:
        print(f"  Quedaron {incomplete} turnos nocturnos incompletos para la siguiente fase.")


def generate_remaining_shifts_proactive(schedule, start_date, end_date, technologists, engineers, critical_days, date_index=None):
    """
    Genera los turnos restantes utilizando un enfoque proactivo para minimizar violaciones.
    
    Args:
        schedule: Horario a modificar
        start_date: Fecha de inicio
        end_date: Fecha final
        technologists: Lista de tecnólogos
        engineers: Lista de ingenieros
        critical_days: Lista de días críticos
        date_index: Índice de fechas para acceso rápido
    """
    print("Fase 3: Generando turnos restantes con detección proactiva de violaciones...")
    
    # Usar índice para acceso O(1)
    if date_index is None:
        date_index = create_date_index(schedule)
    
    # Ordenar los días para procesar primero los críticos
    ordered_dates = sorted(date_range(start_date, end_date), 
                          key=lambda d: (0 if d in critical_days else 1, d))
    
    total_shifts = 0
    completed_shifts = 0
    problematic_shifts = 0
    
    # Aplicar un enfoque de dos pasadas:
    # Pasada 1: Asignar sólo turnos críticos (noches y fines de semana)
    # Pasada 2: Asignar el resto de turnos
    
    for pass_num in range(1, 3):
        pass_type = "críticos" if pass_num == 1 else "restantes"
        print(f"  Pasada {pass_num}: Asignando turnos {pass_type}...")
        
        for current_date in ordered_dates:
            # En la primera pasada, solo procesar días críticos y turnos nocturnos
            is_critical_day = current_date in critical_days
            
            if pass_num == 1 and not is_critical_day:
                # En la primera pasada, para días no críticos, solo asignar turno noche
                ordered_shifts = ["Noche"]
            else:
                # En la segunda pasada, o para días críticos, asignar todos los turnos
                ordered_shifts = SHIFT_TYPES
            
            print(f"  Procesando {current_date.strftime('%d/%m/%Y')} - {'día crítico' if is_critical_day else 'día normal'}")
            
            for shift_type in ordered_shifts:
                # Verificar si el turno ya está completamente asignado
                day_data = date_index.get(current_date)
                
                if not day_data:
                    continue
                    
                shift_data = day_data["shifts"][shift_type]
                current_techs = len(shift_data["technologists"])
                required_techs = TECHS_PER_SHIFT[shift_type]
                has_engineer = shift_data["engineer"] is not None
                
                # Si ya está completo, continuar con el siguiente
                if current_techs >= required_techs and has_engineer:
                    completed_shifts += 1
                    continue
                
                total_shifts += 1
                
                # Asignar personal para el turno incompleto utilizando enfoque proactivo
                success = assign_shift_proactively(
                    schedule, current_date, shift_type, 
                    technologists, engineers, date_index
                )
                
                if success:
                    completed_shifts += 1
                else:
                    problematic_shifts += 1
                    print(f"    ⚠️ No se pudo completar {current_date.strftime('%d/%m/%Y')} {shift_type}")
    
    # Reportar resultados
    print(f"  Asignación proactiva completada: {completed_shifts}/{total_shifts} turnos asignados.")
    if problematic_shifts > 0:
        print(f"  ⚠️ Se encontraron problemas en {problematic_shifts} turnos que requieren atención.")

def assign_shift_proactively(schedule, date, shift_type, technologists, engineers, date_index=None):
    """
    Asigna un turno utilizando un enfoque proactivo para minimizar violaciones futuras.
    
    Args:
        schedule: Horario a modificar
        date: Fecha del turno
        shift_type: Tipo de turno
        technologists: Lista de tecnólogos
        engineers: Lista de ingenieros
        date_index: Índice de fechas para acceso rápido
        
    Returns:
        bool: True si se completó la asignación, False en caso contrario
    """
    # Usar índice para acceso O(1)
    if date_index is None:
        date_index = create_date_index(schedule)
    
    # Verificar si el turno es crítico
    is_critical = shift_type == "Noche" or date.weekday() >= 5 or is_colombian_holiday(date)
    
    # Intentar asignar tecnólogos proactivamente
    tech_success = assign_technologists_proactive(schedule, date, shift_type, technologists, date_index)
    
    # Intentar asignar ingenieros proactivamente
    eng_success = assign_engineers_proactive(schedule, date, shift_type, engineers, date_index)
    
    # Verificar si se completó la asignación
    success = tech_success and eng_success
    
    # En caso de fallo en turno crítico, intentar asignación forzada pero evaluando impacto
    if not success and is_critical:
        print(f"  ⚠️ No se pudo completar asignación normal para turno crítico {date.strftime('%d/%m/%Y')} {shift_type}.")
        print(f"  Intentando asignación de emergencia con menor impacto...")
        
        # Si falló asignación de tecnólogos, forzar pero considerando impacto
        if not tech_success:
            force_assign_with_impact(schedule, date, shift_type, technologists, 
                                   is_technologist=True, date_index=date_index)
        
        # Si falló asignación de ingenieros, forzar pero considerando impacto
        if not eng_success:
            force_assign_with_impact(schedule, date, shift_type, engineers,
                                   is_technologist=False, date_index=date_index)
        
        success = True  # Asumimos que la asignación forzada tuvo éxito
    
    return success

def strictly_can_work_shift(worker, date, shift_type, schedule):
    """
    Verificación estricta de elegibilidad para un turno.
    Implementa todas las restricciones laborales y de balance.
    
    Args:
        worker: Trabajador a evaluar
        date: Fecha del turno
        shift_type: Tipo de turno
        schedule: Horario actual
        
    Returns:
        bool: True si el trabajador puede realizar el turno, False en caso contrario
    """
    # Verificar restricciones básicas del trabajador
    if not worker.can_work_shift(date, shift_type):
        return False
    
    # 1. Verificar la carga de trabajo reciente
    recent_shifts = get_recent_shifts(worker, date, days=3)
    if len(recent_shifts) >= 3:  # Si ya trabajó 3 turnos en los últimos 3 días
        return False
    
    # 2. Verificar balanceo de tipos de turno
    shift_counts = worker.get_shift_types_count()
    if shift_counts:
        max_count = max(shift_counts.values())
        min_count = min(shift_counts.values())
        if max_count - min_count > 5 and shift_counts.get(shift_type, 0) == max_count:
            return False
    
    # 3. Verificar si hay próximo turno nocturno asignado
    if shift_type in ["Mañana", "Tarde"]:
        next_day = date + timedelta(days=1)
        if any(d == next_day and s == "Noche" for d, s in worker.shifts):
            # No asignar turno tarde si tiene turno nocturno al día siguiente
            if shift_type == "Tarde":
                return False
    
    # 4. Verificar si tiene asignación ese mismo día
    if any(d == date for d, _ in worker.shifts):
        return False
    
    # 5. Verificar descanso adecuado
    if not check_adequate_rest(worker, date, shift_type):
        return False
    
    # 6. Verificar transición noche a día (prohibida)
    if check_night_to_day_transition(worker, date, shift_type):
        return False
    
    # 7. Verificar turnos consecutivos (evitar)
    if check_consecutive_shifts(worker, date, shift_type):
        return False
    
    return True

def assign_technologists_proactive(schedule, date, shift_type, technologists, date_index=None):
    """
    Asigna tecnólogos a un turno utilizando detección proactiva de violaciones.
    
    Args:
        schedule: Horario a modificar
        date: Fecha del turno
        shift_type: Tipo de turno
        technologists: Lista de tecnólogos disponibles
        date_index: Índice de fechas para acceso rápido
        
    Returns:
        bool: True si se completó la asignación, False en caso contrario
    """
    # Usar índice para acceso O(1)
    if date_index is None:
        date_index = create_date_index(schedule)
    
    # Determinar cuántos tecnólogos se necesitan
    num_needed = TECHS_PER_SHIFT[shift_type]
    
    # Obtener información actual del turno
    day_data = date_index.get(date)
    current_techs = []
    
    if day_data:
        shift_data = day_data["shifts"][shift_type]
        current_techs = [t for t in technologists if t.id in shift_data["technologists"]]
        
    # Determinar cuántos tecnólogos adicionales necesitamos
    additional_needed = num_needed - len(current_techs)
    
    if additional_needed <= 0:
        return True  # Ya tenemos suficientes tecnólogos
    
    # Encontrar tecnólogos elegibles para este turno con verificación básica
    eligible_techs = []
    for tech in technologists:
        if tech not in current_techs and not any(d == date for d, _ in tech.shifts) and date not in tech.days_off:
            eligible_techs.append(tech)
    
    # Verificar si hay suficientes tecnólogos disponibles
    if len(eligible_techs) < additional_needed:
        print(f"  Advertencia: No hay suficientes tecnólogos para {date.strftime('%d/%m/%Y')} {shift_type}. " +
              f"Necesarios: {additional_needed}, Disponibles: {len(eligible_techs)}.")
        
        # Intentar relajar algunas restricciones solo si es absolutamente necesario
        if len(eligible_techs) < additional_needed * 0.5:  # Menos del 50% de lo necesario
            print("  Buscando recursos adicionales con restricciones relajadas...")
            eligible_techs = find_additional_eligible_workers(technologists, date, shift_type, eligible_techs, schedule)
    
    # Si aún así no hay suficientes, retornar lo que tenemos
    if len(eligible_techs) < additional_needed:
        selected_techs = eligible_techs
    else:
        # Usar nuestra selección proactiva en lugar de select_workers_for_shift
        selected_techs = select_workers_proactively(
            eligible_techs, additional_needed, date, shift_type, schedule, date_index
        )
    
    # Asignar tecnólogos seleccionados al turno
    for tech in selected_techs:
        # Si es un día libre, quitarlo (solo en casos extremos)
        if date in tech.days_off:
            tech.days_off.remove(date)
            print(f"    ⚠️ {tech.get_formatted_id()} pierde día libre para {date.strftime('%d/%m/%Y')} {shift_type}")
        
        schedule.assign_worker(tech, date, shift_type)
    
    # Verificar si se completó la asignación
    return len(current_techs) + len(selected_techs) >= num_needed

def assign_engineers_proactive(schedule, date, shift_type, engineers, date_index=None):
    """
    Asigna ingenieros a un turno utilizando detección proactiva de violaciones.
    
    Args:
        schedule: Horario a modificar
        date: Fecha del turno
        shift_type: Tipo de turno
        engineers: Lista de ingenieros disponibles
        date_index: Índice de fechas para acceso rápido
        
    Returns:
        bool: True si se completó la asignación, False en caso contrario
    """
    # Usar índice para acceso O(1)
    if date_index is None:
        date_index = create_date_index(schedule)
    
    # Verificar si ya hay ingeniero asignado
    day_data = date_index.get(date)
    if day_data and day_data["shifts"][shift_type]["engineer"] is not None:
        return True  # Ya hay ingeniero asignado
    
    # Encontrar ingenieros disponibles básicos
    available_engs = []
    for eng in engineers:
        if not any(d == date for d, _ in eng.shifts) and date not in eng.days_off:
            available_engs.append(eng)
    
    if not available_engs:
        print(f"  Advertencia: No hay ingenieros disponibles para {date.strftime('%d/%m/%Y')} {shift_type}.")
        
        # En caso crítico, buscar con restricciones relajadas
        if shift_type == "Noche" or date.weekday() >= 5 or is_colombian_holiday(date):
            relaxed_engs = []
            for eng in engineers:
                if not any(d == date for d, _ in eng.shifts):
                    # Considerar incluso con día libre en casos críticos
                    relaxed_engs.append((eng, 40 if date in eng.days_off else 0))
            
            # Seleccionar el de menor impacto
            relaxed_engs.sort(key=lambda x: x[1])
            
            if relaxed_engs:
                selected_eng, impact = relaxed_engs[0]
                
                # Si es un día libre, quitarlo
                if date in selected_eng.days_off:
                    selected_eng.days_off.remove(date)
                    print(f"    ⚠️ CRÍTICO: {selected_eng.get_formatted_id()} pierde día libre para turno esencial")
                
                schedule.assign_worker(selected_eng, date, shift_type)
                return True
        
        return False
    
    # Evaluar impacto de cada ingeniero
    eng_impacts = []
    for eng in available_engs:
        can_assign, violations, impact_score = predict_assignment_impact(
            schedule, eng, date, shift_type, date_index
        )
        
        if can_assign:
            eng_impacts.append((eng, impact_score, violations))
    
    # Ordenar por impacto (menor primero)
    eng_impacts.sort(key=lambda x: x[1])
    
    # Seleccionar el mejor candidato
    if eng_impacts:
        selected_eng, impact, violations = eng_impacts[0]
        schedule.assign_worker(selected_eng, date, shift_type)
        
        violations_str = ", ".join(violations) if violations else "ninguna"
        print(f"    Asignado {selected_eng.get_formatted_id()} a {date.strftime('%d/%m/%Y')} {shift_type} " +
              f"(impacto: {impact}, violaciones: {violations_str})")
        
        return True
    
    return False

def find_additional_eligible_workers(workers, date, shift_type, already_eligible, schedule):
    """
    Busca trabajadores adicionales relajando ciertas restricciones para garantizar cobertura.
    Implementa una clasificación por prioridad para mantener calidad del servicio.
    
    Args:
        workers: Lista de trabajadores a considerar
        date: Fecha del turno
        shift_type: Tipo de turno
        already_eligible: Lista de trabajadores ya elegibles
        schedule: Horario actual
        
    Returns:
        list: Lista ampliada de trabajadores elegibles
    """
    # Primero, identificar todos los que no están ya elegibles
    not_eligible = [w for w in workers if w not in already_eligible]
    
    # Clasificar por nivel de restricciones violadas
    medium_priority = []   # Viola restricciones menos críticas
    low_priority = []      # Viola más restricciones, pero puede usarse
    
    for worker in not_eligible:
        # Verificar restricciones críticas
        has_day_off = date in worker.days_off
        night_to_day = check_night_to_day_transition(worker, date, shift_type)
        consecutive = check_consecutive_shifts(worker, date, shift_type)
        already_assigned = any(d == date for d, _ in worker.shifts)
        
        # Las restricciones de día libre y asignación el mismo día NO deben relajarse en esta fase
        if has_day_off or already_assigned:
            continue
            
        # Si viola noche a día, es de muy baja prioridad (casi nunca usarse)
        if night_to_day:
            # Sólo considerar para turnos nocturnos que son críticos
            if shift_type == "Noche":
                low_priority.append(worker)
            continue
        
        # Si viola turnos consecutivos, es de baja prioridad
        if consecutive:
            low_priority.append(worker)
            continue
            
        # Verificar descanso adecuado con versión relajada (1 turno mínimo)
        adequate_rest_relaxed = check_adequate_rest_relaxed(worker, date, shift_type)
        
        if adequate_rest_relaxed:
            medium_priority.append(worker)
        else:
            low_priority.append(worker)
    
    # Ordenar cada grupo por carga de trabajo y tipo de turno
    def sorting_key(worker):
        total_shifts = worker.get_shift_count()
        type_shifts = worker.get_shift_types_count().get(shift_type, 0)
        return (total_shifts, type_shifts)
    
    medium_priority.sort(key=sorting_key)
    low_priority.sort(key=sorting_key)
    
    # Considerar trabajadores con día libre como último recurso para turnos críticos
    if shift_type == "Noche" and len(already_eligible) + len(medium_priority) + len(low_priority) < 2:
        print("  ⚠️ ALERTA: Insuficientes trabajadores para turno nocturno crítico. Considerando todos los recursos.")
        
        last_resort = []
        for worker in not_eligible:
            if worker not in medium_priority and worker not in low_priority:
                # Verificar si tiene día libre pero no está asignado ese día
                if date in worker.days_off and not any(d == date for d, _ in worker.shifts):
                    last_resort.append(worker)
        
        # Ordenar por número de días libres (descendente) y turnos (ascendente)
        last_resort.sort(key=lambda w: (-len(w.days_off), w.get_shift_count()))
        
        # Agregar al final pero no quitar días libres todavía
        return already_eligible + medium_priority + low_priority + last_resort
    
    # Retornar la combinación de todos, manteniendo el orden de prioridad
    return already_eligible + medium_priority + low_priority

def remove_assignments(schedule, date, shift_type, date_index=None):
    """
    Elimina todas las asignaciones para un turno específico.
    
    Args:
        schedule: Horario a modificar
        date: Fecha del turno
        shift_type: Tipo de turno
        date_index: Índice de fechas para acceso rápido
    """
    # Usar índice para acceso O(1)
    if date_index is None:
        date_index = create_date_index(schedule)
    
    # Obtener el día del horario
    day_data = date_index.get(date)
    
    if not day_data:
        return
    
    # Obtener información del turno
    shift_data = day_data["shifts"][shift_type]
    
    # Eliminar registro de tecnólogos
    tech_ids = shift_data["technologists"].copy()  # Crear copia para iterar
    tech_workers = [w for w in schedule.get_technologists() if w.id in tech_ids]
    shift_data["technologists"] = []
    
    # Eliminar registro de ingeniero
    eng_id = shift_data["engineer"]
    eng_workers = [w for w in schedule.get_engineers() if w.id == eng_id]
    shift_data["engineer"] = None
    
    # Eliminar turnos de los registros de trabajadores
    for worker in tech_workers + eng_workers:
        worker.shifts = [(d, s) for d, s in worker.shifts 
                        if not (d == date and s == shift_type)]

def force_assign_with_impact(schedule, date, shift_type, workers, is_technologist=True, date_index=None):
    """
    Realiza una asignación forzada evaluando el impacto para minimizar problemas.
    
    Args:
        schedule: Horario a modificar
        date: Fecha del turno
        shift_type: Tipo de turno
        workers: Lista de trabajadores
        is_technologist: True si son tecnólogos, False si son ingenieros
        date_index: Índice de fechas para acceso rápido
    """
    if date_index is None:
        date_index = create_date_index(schedule)
    
    # Obtener el número requerido
    num_needed = TECHS_PER_SHIFT[shift_type] if is_technologist else 1
    
    # Obtener información actual del turno
    day_data = date_index.get(date)
    if not day_data:
        print(f"  Error: No se encontró el día {date.strftime('%d/%m/%Y')} en el horario.")
        return
    
    shift_data = day_data["shifts"][shift_type]
    
    # Determinar cuántos más necesitamos
    if is_technologist:
        current_count = len(shift_data["technologists"])
        additional_needed = num_needed - current_count
    else:  # Ingenieros
        current_count = 1 if shift_data["engineer"] is not None else 0
        additional_needed = 1 - current_count
    
    if additional_needed <= 0:
        return  # Ya tenemos suficientes
    
    # Recopilar todos los trabajadores con su impacto
    worker_impacts = []
    
    for worker in workers:
        # Verificar si ya está asignado a este turno
        already_assigned = False
        if is_technologist:
            already_assigned = worker.id in shift_data["technologists"]
        else:
            already_assigned = shift_data["engineer"] == worker.id
        
        if already_assigned:
            continue
        
        # Verificar si tiene otro turno ese día
        has_other_shift = any(d == date for d, _ in worker.shifts)
        
        # Verificar restricciones y calcular impacto
        impact = 0
        violations = []
        
        # El día libre es muy importante pero puede relajarse en emergencias
        has_day_off = date in worker.days_off
        if has_day_off:
            impact += 40
            violations.append("Día libre")
        
        # Restricciones críticas
        night_to_day = check_night_to_day_transition(worker, date, shift_type)
        if night_to_day:
            impact += 30
            violations.append("Transición noche a día")
        
        consecutive = check_consecutive_shifts(worker, date, shift_type)
        if consecutive:
            impact += 20
            violations.append("Turnos consecutivos")
        
        inadequate_rest = not check_adequate_rest(worker, date, shift_type)
        if inadequate_rest:
            impact += 15
            violations.append("Descanso inadecuado")
        
        # Otro turno ese día es un bloqueador
        if has_other_shift:
            impact += 50
            violations.append("Ya tiene turno ese día")
            
            # Recuperar el otro turno para evaluar intercambio
            other_shift = next((s for d, s in worker.shifts if d == date), None)
            
            # Si el otro turno es de menor prioridad que el actual y no es noche,
            # podríamos considerar liberarlo, pero con un impacto alto
            if other_shift and other_shift != "Noche" and shift_type == "Noche":
                impact -= 10  # Reducir impacto para hacer este caso menos desfavorable
                violations.append(f"(Podría liberar de turno {other_shift})")
        
        # Calcular impacto total considerando carga de trabajo
        workload = worker.get_shift_count()
        shift_experience = worker.get_shift_types_count().get(shift_type, 0)
        
        # Ajustar impacto por experiencia y carga
        adjusted_impact = impact + (workload / 10.0) - (shift_experience / 10.0)
        
        worker_impacts.append((worker, adjusted_impact, violations, has_other_shift, has_day_off))
    
    # Ordenar por impacto (menor primero)
    worker_impacts.sort(key=lambda x: x[1])
    
    # Seleccionar los mejores candidatos
    selected_workers = []
    
    for worker, impact, violations, has_other_shift, has_day_off in worker_impacts:
        if len(selected_workers) >= additional_needed:
            break
        
        violations_str = ", ".join(violations) if violations else "ninguna"
        print(f"    Evaluando asignación forzada: {worker.get_formatted_id()}, impacto={impact:.2f}, violaciones: {violations_str}")
        
        # Si tiene otro turno ese día, intentar liberarlo
        if has_other_shift:
            other_shift = next((s for d, s in worker.shifts if d == date), None)
            
            # Solo liberar si es un caso donde vale la pena
            shift_priority = {"Noche": 3, "Tarde": 2, "Mañana": 1}
            current_priority = shift_priority.get(shift_type, 0)
            other_priority = shift_priority.get(other_shift, 0)
            
            # Solo liberar si el turno actual es más importante
            if current_priority > other_priority:
                # Quitar del otro turno
                day_data = date_index.get(date)
                if day_data:
                    other_shift_data = day_data["shifts"][other_shift]
                    
                    if is_technologist:
                        if worker.id in other_shift_data["technologists"]:
                            other_shift_data["technologists"].remove(worker.id)
                    else:
                        if other_shift_data["engineer"] == worker.id:
                            other_shift_data["engineer"] = None
                
                # Quitar del registro del trabajador
                worker.shifts = [(d, s) for d, s in worker.shifts if not (d == date and s == other_shift)]
                
                print(f"      Liberado {worker.get_formatted_id()} de {date.strftime('%d/%m/%Y')} {other_shift} para turno más crítico")
                
                # Intentar reemplazar ese turno
                from algorithms.repair import replace_worker
                replace_worker(schedule, date, other_shift, worker, 
                             workers if is_technologist else workers, date_index)
            else:
                # No podemos liberar, saltar este trabajador
                continue
        
        # Si es un día libre, quitarlo
        if has_day_off:
            worker.days_off.remove(date)
            print(f"      ⚠️ {worker.get_formatted_id()} pierde día libre para cubrir turno esencial")
        
        # Asignar al trabajador
        schedule.assign_worker(worker, date, shift_type)
        selected_workers.append(worker)
        
        print(f"      Asignación forzada: {worker.get_formatted_id()} a {date.strftime('%d/%m/%Y')} {shift_type} (impacto: {impact:.2f})")
    
    # Si aún así no completamos, reportar el problema
    if len(selected_workers) < additional_needed:
        shortfall = additional_needed - len(selected_workers)
        print(f"    ⚠️⚠️ ALERTA CRÍTICA: Faltan {shortfall} {('tecnólogos' if is_technologist else 'ingenieros')} " +
              f"para {date.strftime('%d/%m/%Y')} {shift_type} incluso después de asignación forzada!")