"""
Algoritmo principal para la generación de horarios.
Implementa un sistema optimizado de asignación equitativa con restricciones laborales.
"""

import re
from datetime import datetime, timedelta
from config.settings import SHIFT_TYPES, TECHS_PER_SHIFT, ENG_PER_SHIFT
from core.schedule import Schedule
from utils.date_utils import date_range, get_week_start, get_week_end
from core.constraints import validate_schedule, check_night_to_day_transition
from core.constraints import check_consecutive_shifts, check_adequate_rest, check_adequate_rest_relaxed
from algorithms.selector import select_workers_proactively
from utils.compensation import calculate_compensation
from config import is_colombian_holiday
from algorithms.common import create_date_index, predict_assignment_impact, get_recent_shifts
###########################################################################
# FUNCIONES PRINCIPALES DEL GENERADOR                                     #
###########################################################################

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
    # *** AQUÍ USAMOS LA NUEVA FUNCIÓN PROACTIVA ***
    generate_remaining_shifts_proactive(
        schedule, start_date, end_date, technologists, engineers, critical_days, date_index
    )
    
    # FASE DE OPTIMIZACIÓN Y VALIDACIÓN
    # Las violaciones deberían ser mínimas ahora, pero aún así verificamos
    
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

###########################################################################
# FUNCIONES AUXILIARES Y DE UTILIDAD                                      #
###########################################################################

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
        


###########################################################################
# FUNCIONES DE PRE-ASIGNACIÓN                                             #
###########################################################################

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


###########################################################################
# FUNCIONES DE ASIGNACIÓN Y VERIFICACIÓN                                  #
###########################################################################

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
        
    
        
###########################################################################
# FUNCIONES PARA DÍAS LIBRES Y EQUILIBRIO                                 #
###########################################################################

def ensure_weekly_days_off(schedule, technologists, engineers, date_index=None):
    """
    Asegura que cada trabajador tenga un día libre semanal.
    Optimizado para distribuir mejor los días libres a lo largo de la semana.
    
    Args:
        schedule: Horario a modificar
        technologists: Lista de tecnólogos
        engineers: Lista de ingenieros
        date_index: Índice de fechas para acceso rápido
    """
    print("Asignando días libres semanales...")
    
    # Usar índice para acceso O(1)
    if date_index is None:
        date_index = create_date_index(schedule)
    
    # Obtener todas las semanas en el período
    weeks = []
    current_date = get_week_start(schedule.start_date)  # Comenzar desde el inicio de la semana
    
    while current_date <= schedule.end_date:
        week_end = get_week_end(current_date)
        
        # Solo incluir semanas que se superpongan con el período
        if not (week_end < schedule.start_date or current_date > schedule.end_date):
            effective_start = max(current_date, schedule.start_date)
            effective_end = min(week_end, schedule.end_date)
            weeks.append((current_date, week_end, effective_start, effective_end))
        
        current_date += timedelta(days=7)
    
    all_workers = technologists + engineers
    
    # Fase 1: Asignar días libres después de turnos nocturnos (prioridad máxima)
    print("  Fase 1: Asignando días libres post-nocturnos...")
    workers_with_days_off = set()  # Seguimiento de trabajadores con días libres asignados
    
    for worker in all_workers:
        worker_id = worker.get_formatted_id()
        
        for week_start, week_end, effective_start, effective_end in weeks:
            # Verificar si ya tiene día libre esta semana
            days_off_in_week = [d for d in worker.days_off 
                             if effective_start <= d <= effective_end]
            
            if days_off_in_week:
                workers_with_days_off.add(worker.id)
                continue  # Ya tiene día libre esta semana, pasar a la siguiente
            
            # Buscar turnos nocturnos en la semana
            night_shifts = [(d, s) for d, s in worker.shifts 
                          if s == "Noche" and effective_start <= d <= effective_end]
            
            # Si hay turnos nocturnos, intentar asignar día libre al día siguiente
            if night_shifts:
                night_shifts.sort(key=lambda x: x[0])  # Ordenar por fecha
                
                for night_date, _ in night_shifts:
                    next_day = night_date + timedelta(days=1)
                    
                    # Verificar si el día siguiente está en el rango efectivo
                    if effective_start <= next_day <= effective_end:
                        # Verificar si no hay turno asignado ese día
                        if not any(d == next_day for d, _ in worker.shifts):
                            worker.add_day_off(next_day)
                            workers_with_days_off.add(worker.id)
                            print(f"    Día libre asignado a {worker_id} el {next_day.strftime('%d/%m/%Y')} (después de noche)")
                            break  # Asignado un día libre para esta semana
    
    # Fase 2: Distribución equilibrada de días libres
    print("  Fase 2: Distribución equilibrada de días libres...")
    
    for week_start, week_end, effective_start, effective_end in weeks:
        # Analizar distribución actual de días libres en esta semana
        days_off_distribution = {}
        for day in date_range(effective_start, effective_end):
            days_off_distribution[day] = {
                'tech_count': 0,
                'eng_count': 0,
                'total_assigned': 0,  # Trabajadores asignados ese día
                'workers': []  # Lista de trabajadores con día libre ese día
            }
        
        # Contar días libres actuales por día
        for worker in all_workers:
            for day in worker.days_off:
                if effective_start <= day <= effective_end:
                    worker_type = 'tech_count' if worker.is_technologist else 'eng_count'
                    if day in days_off_distribution:
                        days_off_distribution[day][worker_type] += 1
                        days_off_distribution[day]['workers'].append(worker.id)
        
        # Contar asignaciones por día
        for day in date_range(effective_start, effective_end):
            day_data = date_index.get(day)
            if day_data:
                for shift_type in SHIFT_TYPES:
                    shift_data = day_data["shifts"][shift_type]
                    techs_count = len(shift_data["technologists"])
                    eng_assigned = 1 if shift_data["engineer"] is not None else 0
                    days_off_distribution[day]['total_assigned'] += techs_count + eng_assigned
        
        # Asignar días libres a trabajadores que aún no los tienen
        workers_needing_day_off = [w for w in all_workers if w.id not in workers_with_days_off]
        
        # Ordenar trabajadores por carga de trabajo (descendente)
        workers_needing_day_off.sort(key=lambda w: w.get_shift_count(), reverse=True)
        
        print(f"    Semana del {week_start.strftime('%d/%m/%Y')}: {len(workers_needing_day_off)} trabajadores necesitan día libre")
        
        for worker in workers_needing_day_off:
            # Calcular días candidatos (no asignados)
            candidate_days = []
            
            for day in date_range(effective_start, effective_end):
                # Verificar si ya tiene asignación ese día
                if any(d == day for d, _ in worker.shifts):
                    continue
                
                # Calcular costo de asignar día libre aquí
                # Menor costo = mejor candidato
                
                # 1. Penalizar días ya sobrecargados con días libres
                worker_type_key = 'tech_count' if worker.is_technologist else 'eng_count'
                days_off_count = days_off_distribution[day][worker_type_key]
                days_off_penalty = days_off_count * 5  # 5 puntos por cada día libre ya asignado
                
                # 2. Penalizar días con poca gente asignada
                assigned_count = days_off_distribution[day]['total_assigned']
                assignment_penalty = max(0, (len(all_workers) // 3) - assigned_count) * 3
                
                # 3. Priorizar días laborables (menor costo)
                weekday_cost = 0 if day.weekday() < 5 else 10
                
                # 4. Penalizar lunes y viernes (para distribuir mejor)
                edge_day_penalty = 5 if day.weekday() in [0, 4] else 0
                
                # 5. Preferir días con menos carga total
                total_workers_penalty = sum(1 for w in all_workers if any(d == day for d, _ in w.shifts)) * 0.2
                
                # Costo total
                total_cost = days_off_penalty + assignment_penalty + weekday_cost + edge_day_penalty + total_workers_penalty
                
                candidate_days.append((day, total_cost))
            
            # Ordenar días candidatos por costo (menor primero)
            candidate_days.sort(key=lambda x: x[1])
            
            if candidate_days:
                selected_day, cost = candidate_days[0]
                
                # Asignar día libre
                worker.add_day_off(selected_day)
                workers_with_days_off.add(worker.id)
                
                # Actualizar distribución
                worker_type = 'tech_count' if worker.is_technologist else 'eng_count'
                days_off_distribution[selected_day][worker_type] += 1
                days_off_distribution[selected_day]['workers'].append(worker.id)
                
                print(f"    Día libre asignado a {worker.get_formatted_id()} el {selected_day.strftime('%d/%m/%Y')} (distribución equilibrada)")
            else:
                print(f"    ⚠️ No se encontró día libre para {worker.get_formatted_id()} en semana del {week_start.strftime('%d/%m/%Y')}")
                free_days = get_week_workload(schedule, effective_start, effective_end, worker, date_index)
                
                if free_days:
                    # Liberar el día con menor impacto
                    free_day, shift_to_remove, liberation_cost = free_days[0]
                    
                    # Liberar este día
                    liberate_day_for_worker(schedule, worker, free_day, shift_to_remove, date_index)
                    
                    # Asignar día libre
                    worker.add_day_off(free_day)
                    workers_with_days_off.add(worker.id)
                    print(f"    ⚠️ Liberado turno {shift_to_remove} del {free_day.strftime('%d/%m/%Y')} para {worker.get_formatted_id()}")
    
    # Verificación final
    print("  Verificando asignación final de días libres...")
    workers_without_days = []
    
    for worker in all_workers:
        days_off_by_week = []
        
        for week_start, week_end, effective_start, effective_end in weeks:
            days_off_in_week = [d for d in worker.days_off 
                              if effective_start <= d <= effective_end]
            days_off_by_week.append(len(days_off_in_week))
        
        if 0 in days_off_by_week:
            weeks_without = days_off_by_week.count(0)
            workers_without_days.append((worker, weeks_without))
            print(f"    ⚠️ {worker.get_formatted_id()} sin día libre en {weeks_without} semana(s)")
    
    if not workers_without_days:
        print("    ✅ Todos los trabajadores tienen al menos un día libre por semana")
    
    # Si hay trabajadores sin días libres en alguna semana, intentar una última solución
    if workers_without_days:
        print("  Fase de emergencia: Intentando última corrección para días libres faltantes...")
        for worker, weeks_without in sorted(workers_without_days, key=lambda x: x[1], reverse=True):
            # Identificar semanas sin día libre
            weeks_missing = []
            for i, (week_start, week_end, effective_start, effective_end) in enumerate(weeks):
                days_off_in_week = [d for d in worker.days_off 
                                  if effective_start <= d <= effective_end]
                if not days_off_in_week:
                    weeks_missing.append((i, effective_start, effective_end))
            
            for week_idx, eff_start, eff_end in weeks_missing:
                # Buscar el día con menor carga para liberarlo
                free_days = get_week_workload(schedule, eff_start, eff_end, worker, date_index, emergency=True)
                
                if free_days:
                    # Liberar el día con menor impacto, incluso si es crítico
                    free_day, shift_to_remove, _ = free_days[0]
                    
                    # Liberar este día
                    liberate_day_for_worker(schedule, worker, free_day, shift_to_remove, date_index)
                    
                    # Asignar día libre
                    worker.add_day_off(free_day)
                    print(f"    ⚠️ EMERGENCIA: Liberado turno {shift_to_remove} del {free_day.strftime('%d/%m/%Y')} para {worker.get_formatted_id()}")
                    break


def get_week_workload(schedule, start_date, end_date, worker, date_index, emergency=False):
    """
    Analiza la semana para identificar qué día sería mejor liberar para el trabajador.
    
    Args:
        schedule: Horario actual
        start_date: Fecha de inicio de la semana
        end_date: Fecha final de la semana
        worker: Trabajador a analizar
        date_index: Índice de fechas para acceso rápido
        emergency: Indica si es una situación de emergencia
        
    Returns:
        list: Lista de tuplas (día, turno, costo) ordenadas por costo de liberación
    """
    shifts_to_evaluate = []
    
    # Calcular el promedio de turnos por tipo manualmente
    shift_counts = worker.get_shift_types_count()
    total_shifts = sum(shift_counts.values())
    avg_shifts_per_type = total_shifts / len(shift_counts) if len(shift_counts) > 0 else 0
    
    for d, s in worker.shifts:
        if start_date <= d <= end_date:
            # Obtener día del horario usando el índice
            day_data = date_index.get(d)
            
            if day_data:
                shift_data = day_data["shifts"][s]
                
                # Contar cuántos otros trabajadores están asignados
                if worker.is_technologist:
                    other_workers = len(shift_data["technologists"]) - 1  # -1 para excluir al trabajador actual
                else:
                    # Para ingenieros siempre hay 1 por turno (el mismo)
                    other_workers = 0
                
                # Calcular costo de liberación más sofisticado
                
                # 1. Factor de día (fin de semana es más costoso)
                weekend_factor = 3 if d.weekday() >= 5 else 1
                
                # 2. Factor de turno (noche es más costoso)
                shift_factor = 3 if s == "Noche" else (2 if s == "Tarde" else 1)
                
                # 3. Factor de cobertura (pocos trabajadores = más costoso)
                min_workers = TECHS_PER_SHIFT[s] if worker.is_technologist else ENG_PER_SHIFT
                worker_factor = 5 if other_workers <= min_workers - 1 else (
                               3 if other_workers <= min_workers else 1)
                
                # 4. Factor de experiencia/equilibrio (si este trabajador es esencial)
                curr_shifts = shift_counts.get(s, 0)
                expertise_factor = 3 if curr_shifts < avg_shifts_per_type * 0.7 else 1
                
                # 5. Factor de proximidad (no liberar días consecutivos)
                adjacency_penalty = 0
                for offset in [-1, 1]:  # Verificar día anterior y siguiente
                    adjacent_day = d + timedelta(days=offset)
                    if adjacent_day in worker.days_off:
                        adjacency_penalty += 2
                
                # 6. Día festivo (más costoso)
                holiday_factor = 2 if is_colombian_holiday(d) else 1
                
                # Calcular costo total
                if emergency:
                    # En emergencia, ignorar algunos factores para garantizar un día libre
                    liberation_cost = weekend_factor + worker_factor + holiday_factor
                else:
                    liberation_cost = (weekend_factor * shift_factor * worker_factor * 
                                     expertise_factor * holiday_factor + adjacency_penalty)
                    
                shifts_to_evaluate.append((d, s, liberation_cost))
    
    # Ordenar por costo (menor primero)
    shifts_to_evaluate.sort(key=lambda x: x[2])
    
    return shifts_to_evaluate


def liberate_day_for_worker(schedule, worker, day, shift_type, date_index):
    """
    Libera un día asignado a un trabajador e intenta reemplazarlo si es necesario.
    
    Args:
        schedule: Horario a modificar
        worker: Trabajador a liberar
        day: Fecha a liberar
        shift_type: Tipo de turno a liberar
        date_index: Índice de fechas para acceso rápido
        
    Returns:
        bool: True si se pudo reemplazar al trabajador, False en caso contrario
    """
    # Obtener día del horario
    day_data = date_index.get(day)
    
    if not day_data:
        return False
    
    shift_data = day_data["shifts"][shift_type]
    
    # Quitar al trabajador
    if worker.is_technologist:
        if worker.id in shift_data["technologists"]:
            shift_data["technologists"].remove(worker.id)
    else:
        if shift_data["engineer"] == worker.id:
            shift_data["engineer"] = None
    
    # Quitar del registro del trabajador
    worker.shifts = [(d, s) for d, s in worker.shifts 
                   if not (d == day and s == shift_type)]
    
    # Intentar reemplazar si es necesario
    if worker.is_technologist:
        required = TECHS_PER_SHIFT[shift_type]
        current = len(shift_data["technologists"])
        
        if current < required:
            # Buscar reemplazo entre tecnólogos
            available_replacements = [t for t in schedule.get_technologists() 
                                    if t.id != worker.id and 
                                       not any(d == day for d, _ in t.shifts) and 
                                       day not in t.days_off]
            
            # Ordenar por menos turnos primero
            available_replacements.sort(key=lambda t: (t.get_shift_count(), 
                                                     t.get_shift_types_count().get(shift_type, 0)))
            
            # Asignar el primero disponible
            if available_replacements:
                replacement = available_replacements[0]
                schedule.assign_worker(replacement, day, shift_type)
                return True
    else:
        # Es ingeniero, siempre intentar reemplazar
        available_replacements = [e for e in schedule.get_engineers() 
                               if e.id != worker.id and 
                                  not any(d == day for d, _ in e.shifts) and 
                                  day not in e.days_off]
        
        # Ordenar por menos turnos primero
        available_replacements.sort(key=lambda e: (e.get_shift_count(), 
                                                e.get_shift_types_count().get(shift_type, 0)))
        
        # Asignar el primero disponible
        if available_replacements:
            replacement = available_replacements[0]
            schedule.assign_worker(replacement, day, shift_type)
            return True
    
    return False


def verify_weekly_days_off(schedule, technologists, engineers):
    """
    Verifica que todos los trabajadores tengan al menos un día libre por semana.
    
    Args:
        schedule: Horario a verificar
        technologists: Lista de tecnólogos
        engineers: Lista de ingenieros
        
    Returns:
        bool: True si todos cumplen, False en caso contrario
    """
    print("Verificación final de días libres semanales...")
    
    all_workers = technologists + engineers
    start_date = schedule.start_date
    end_date = schedule.end_date
    
    # Definir semanas
    first_date = start_date
    while first_date.weekday() != 0:  # Retroceder hasta el lunes
        first_date -= timedelta(days=1)
    
    weeks = []
    current_monday = first_date
    while current_monday <= end_date:
        week_days = []
        for i in range(7):
            day = current_monday + timedelta(days=i)
            if start_date <= day <= end_date:
                week_days.append(day)
        if week_days:
            weeks.append((current_monday, week_days))
        current_monday += timedelta(days=7)
    
    # Verificar cada trabajador y semana
    all_compliant = True
    violations = []
    
    for worker in all_workers:
        for i, (week_start, week_days) in enumerate(weeks):
            # Verificar días libres en esta semana
            days_off_in_week = [day for day in worker.days_off if day in week_days]
            
            # Si no hay días libres en esta semana, es una violación
            if not days_off_in_week:
                all_compliant = False
                violations.append((worker, i+1, week_days))
                print(f"  ❌ VIOLACIÓN: {worker.get_formatted_id()} no tiene día libre en semana {i+1} ({week_start.strftime('%d/%m/%Y')})")
    
    if all_compliant:
        print("  ✅ Todos los trabajadores tienen al menos un día libre por semana")
    else:
        print(f"  ⚠️ Se encontraron {len(violations)} violaciones de días libres semanales")
    
    return all_compliant


###########################################################################
# FUNCIONES DE BALANCEO DE CARGA Y EQUIDAD                               #
###########################################################################

def balance_workload(schedule, technologists, engineers, date_index=None):
    """
    Equilibra la carga de trabajo entre trabajadores.
    
    Args:
        schedule: Horario a modificar
        technologists: Lista de tecnólogos
        engineers: Lista de ingenieros
        date_index: Índice de fechas para acceso rápido
    """
    print("Balanceando carga de trabajo...")
    
    # Usar índice para acceso O(1)
    if date_index is None:
        date_index = create_date_index(schedule)
    
    # Realizar múltiples pasadas para un mejor equilibrio
    for i in range(2):  # Realizar 2 pasadas
        print(f"  Pasada de balance {i+1}...")
        
        # Balancear tecnólogos
        balance_worker_group(schedule, technologists, date_index)
        
        # Balancear ingenieros
        balance_worker_group(schedule, engineers, date_index)
        
    # Balanceo específico de turnos premium
    balance_premium_shifts(schedule, technologists, date_index)
    balance_premium_shifts(schedule, engineers, date_index)


def balance_worker_group(schedule, workers, date_index=None):
    """
    Equilibra la carga de trabajo dentro de un grupo de trabajadores.
    
    Args:
        schedule: Horario a modificar
        workers: Lista de trabajadores del mismo tipo
        date_index: Índice de fechas para acceso rápido
    """
    # Usar índice para acceso O(1)
    if date_index is None:
        date_index = create_date_index(schedule)
        
    group_type = "Tecnólogos" if workers[0].is_technologist else "Ingenieros"
    print(f"  Balanceando grupo: {group_type}")
    
    # Calcular la duración del período en días
    period_duration = (schedule.end_date - schedule.start_date).days + 1
    
    # Analizar distribución actual de turnos
    shifts_per_worker = {w.id: w.get_shift_count() for w in workers}
    min_shifts = min(shifts_per_worker.values()) if shifts_per_worker else 0
    max_shifts = max(shifts_per_worker.values()) if shifts_per_worker else 0
    
    # Calcular estadísticas del grupo para umbral dinámico
    avg_shifts_per_worker = sum(shifts_per_worker.values()) / len(workers) if workers else 0
    
    # Calcular turnos promedio por tipo y trabajador
    avg_shifts_per_type = avg_shifts_per_worker / len(SHIFT_TYPES)
    
    # Calcular umbral de desequilibrio dinámico basado en la duración y promedio
    # Fórmula: Base + Factor * (Duración / 30)
    base_threshold = 1.5  # Umbral mínimo
    scale_factor = 0.5    # Factor de escala por mes
    
    # Calcular umbral dinámico (aumenta con la duración del período)
    dynamic_threshold = base_threshold + scale_factor * (period_duration / 30)
    
    # Ajustar umbral basado en el promedio de turnos por tipo
    # Para períodos cortos con pocos turnos, el umbral puede ser muy bajo
    min_threshold = max(1, avg_shifts_per_type * 0.25)  # Mínimo 1 o 25% del promedio
    
    # Elegir el umbral final (el mayor entre el dinámico y el mínimo)
    final_threshold = max(dynamic_threshold, min_threshold)
    
    print(f"    Umbral de desequilibrio para período de {period_duration} días: {final_threshold:.1f}")
    
    # Equilibrar turnos totales
    if max_shifts - min_shifts > 1:
        print(f"    Diferencia actual de turnos totales: {min_shifts}-{max_shifts}")
        
        # Identificar trabajadores con más y menos turnos
        workers_with_most = [w for w in workers if w.get_shift_count() == max_shifts]
        workers_with_least = [w for w in workers if w.get_shift_count() == min_shifts]
        
        # Intentar transferencias
        transfers_made = 0
        max_transfers = 8
        
        for from_worker in workers_with_most:
            if transfers_made >= max_transfers:
                break
                
            for to_worker in workers_with_least:
                if transfers_made >= max_transfers:
                    break
                    
                # Intentar transferir un turno
                if transfer_shift_safely(schedule, from_worker, to_worker, date_index):
                    transfers_made += 1
                    print(f"      Turno transferido de {from_worker.get_formatted_id()} a {to_worker.get_formatted_id()}")
    
    # Analizar y corregir desequilibrios de tipos de turno usando el umbral dinámico
    desequilibrios_corregidos = 0
    
    for worker in workers:
        counts = worker.get_shift_types_count()
        if not counts:
            continue
            
        max_type = max(counts, key=counts.get)
        min_type = min(counts, key=counts.get)
        
        # Calcular desequilibrio relativo (%)
        min_count = counts.get(min_type, 0)
        max_count = counts.get(max_type, 0)
        
        # Evitar división por cero
        if min_count > 0:
            imbalance_percent = (max_count - min_count) / min_count * 100
        else:
            # Si un tipo tiene 0 turnos, el desequilibrio es máximo
            imbalance_percent = 100
            
        # Usar tanto el umbral absoluto como un umbral relativo
        absolute_imbalance = max_count - min_count
        should_balance = absolute_imbalance > final_threshold
        
        # Para períodos largos, también considerar el desequilibrio porcentual
        if period_duration > 14:  # Más de dos semanas
            should_balance = should_balance or (imbalance_percent > 40)  # 40% de desequilibrio
            
        if should_balance:
            print(f"    Desequilibrio de tipos en {worker.get_formatted_id()}: " +
                  f"{min_type}={min_count}, {max_type}={max_count} " +
                  f"(Δ={absolute_imbalance:.1f}, {imbalance_percent:.1f}%)")
            
            # Intentar equilibrar con cualquier otro trabajador
            for other_worker in workers:
                if other_worker.id == worker.id:
                    continue
                
                other_counts = other_worker.get_shift_types_count()
                
                # Si el otro tiene más del tipo que este tiene menos y viceversa
                if other_counts.get(min_type, 0) > counts.get(min_type, 0) and counts.get(max_type, 0) > other_counts.get(max_type, 0):
                    # Intentar intercambiar un turno de cada tipo
                    if exchange_shifts_by_type(schedule, worker, other_worker, min_type, max_type, date_index):
                        desequilibrios_corregidos += 1
                        print(f"      Intercambio de tipos entre {worker.get_formatted_id()} y {other_worker.get_formatted_id()}")
                        break
    
    print(f"    Desequilibrios corregidos: {desequilibrios_corregidos}")


def balance_premium_shifts(schedule, workers, date_index=None):
    """
    Función para balancear específicamente los turnos premium.
    
    Args:
        schedule: Horario a modificar
        workers: Lista de trabajadores del mismo tipo
        date_index: Índice de fechas para acceso rápido
    """
    # Usar índice para acceso O(1)
    if date_index is None:
        date_index = create_date_index(schedule)
        
    print(f"  Balanceando turnos premium para {workers[0].get_formatted_id()[0]}'s...")
    
    # Contar turnos premium por trabajador
    premium_counts = {}
    for worker in workers:
        premium_count = 0
        premium_value = 0.0
        
        for date, shift_type in worker.shifts:
            is_weekend = date.weekday() >= 5
            is_night = shift_type == "Noche"
            is_holiday = is_colombian_holiday(date)
            
            if is_weekend or is_night or is_holiday:
                premium_count += 1
                premium_value += calculate_compensation(date, shift_type)
        
        premium_counts[worker.id] = (premium_count, premium_value)
    
    # Encontrar trabajadores con más y menos turnos premium
    min_premium = min(premium_counts.values(), key=lambda x: x[1]) if premium_counts else (0, 0)
    max_premium = max(premium_counts.values(), key=lambda x: x[1]) if premium_counts else (0, 0)
    
    # Calcular diferencia
    min_value = min_premium[1]
    max_value = max_premium[1]
    diff_percent = (max_value - min_value) / min_value * 100 if min_value > 0 else 0
    
    print(f"    Diferencia en valor premium: {diff_percent:.1f}%")
    
    # Si la diferencia es significativa, intentar equilibrar
    if diff_percent > 15:
        workers_with_most = [w for w in workers if premium_counts[w.id][1] > (min_value * 1.15)]
        workers_with_least = [w for w in workers if premium_counts[w.id][1] < (max_value * 0.85)]
        
        transfers_made = 0
        max_transfers = 5
        
        for from_worker in workers_with_most:
            if transfers_made >= max_transfers:
                break
                
            for to_worker in workers_with_least:
                if transfers_made >= max_transfers:
                    break
                    
                # Intentar transferir un turno premium específicamente
                if transfer_premium_shift(schedule, from_worker, to_worker, date_index):
                    transfers_made += 1
                    print(f"      Turno premium transferido de {from_worker.get_formatted_id()} a {to_worker.get_formatted_id()}")


def transfer_shift_safely(schedule, from_worker, to_worker, date_index=None):
    """
    Transfiere un turno entre trabajadores sin generar violaciones.
    
    Args:
        schedule: Horario a modificar
        from_worker: Trabajador origen
        to_worker: Trabajador destino
        date_index: Índice de fechas para acceso rápido
        
    Returns:
        bool: True si se realizó la transferencia, False en caso contrario
    """
    # Usar índice para acceso O(1)
    if date_index is None:
        date_index = create_date_index(schedule)
        
    # Ordenar turnos del trabajador con más turnos (descendente por fecha)
    shifts = sorted(from_worker.shifts, key=lambda x: x[0], reverse=True)
    
    # Probar cada turno, empezando por los más recientes
    for date, shift_type in shifts:
        # Verificar si el trabajador destino puede tomar este turno
        if date in to_worker.days_off:
            continue
            
        if any(d == date for d, _ in to_worker.shifts):
            continue
        
        # Verificar restricciones críticas
        night_to_day = check_night_to_day_transition(to_worker, date, shift_type)
        consecutive = check_consecutive_shifts(to_worker, date, shift_type)
        adequate_rest = check_adequate_rest(to_worker, date, shift_type)
        
        if night_to_day or consecutive or not adequate_rest:
            continue
        
        # Encontrar el turno en el horario usando el índice
        day_data = date_index.get(date)
        
        if day_data:
            shift_data = day_data["shifts"][shift_type]
            
            # Quitar trabajador origen
            if from_worker.is_technologist:
                if from_worker.id in shift_data["technologists"]:
                    shift_data["technologists"].remove(from_worker.id)
            else:
                if shift_data["engineer"] == from_worker.id:
                    shift_data["engineer"] = None
            
            # Quitar del registro del trabajador
            from_worker.shifts = [(d, s) for d, s in from_worker.shifts 
                                if not (d == date and s == shift_type)]
            
            # Asignar al trabajador destino
            schedule.assign_worker(to_worker, date, shift_type)
            
            return True
    
    return False


def exchange_shifts_by_type(schedule, worker1, worker2, type1, type2, date_index=None):
    """
    Intercambia turnos de diferentes tipos entre dos trabajadores.
    
    Args:
        schedule: Horario a modificar
        worker1: Primer trabajador
        worker2: Segundo trabajador
        type1: Tipo de turno a intercambiar para worker1
        type2: Tipo de turno a intercambiar para worker2
        date_index: Índice de fechas para acceso rápido
        
    Returns:
        bool: True si se realizó el intercambio, False en caso contrario
    """
    # Usar índice para acceso O(1)
    if date_index is None:
        date_index = create_date_index(schedule)
        
    # Buscar un turno de type1 que worker2 pueda realizar
    type1_shifts = [(d, s) for d, s in worker2.shifts if s == type1]
    
    for date1, _ in type1_shifts:
        # Verificar si worker1 puede realizar este turno
        if date1 in worker1.days_off:
            continue
            
        if any(d == date1 and s != type1 for d, s in worker1.shifts):
            continue
        
        # Verificar restricciones para worker1
        night_to_day1 = check_night_to_day_transition(worker1, date1, type1)
        consecutive1 = check_consecutive_shifts(worker1, date1, type1)
        adequate_rest1 = check_adequate_rest(worker1, date1, type1)
        
        if night_to_day1 or consecutive1 or not adequate_rest1:
            continue
        
        # Buscar un turno de type2 que worker1 pueda ceder a worker2
        type2_shifts = [(d, s) for d, s in worker1.shifts if s == type2]
        
        for date2, _ in type2_shifts:
            # Verificar si worker2 puede realizar este turno
            if date2 in worker2.days_off:
                continue
                
            if any(d == date2 and s != type2 for d, s in worker2.shifts):
                continue
            
            # Verificar restricciones para worker2
            night_to_day2 = check_night_to_day_transition(worker2, date2, type2)
            consecutive2 = check_consecutive_shifts(worker2, date2, type2)
            adequate_rest2 = check_adequate_rest(worker2, date2, type2)
            
            if night_to_day2 or consecutive2 or not adequate_rest2:
                continue
            
            # Realizar el intercambio usando el índice
            
            # 1. Quitar worker2 de su turno type1
            day_data1 = date_index.get(date1)
            if day_data1:
                shift_data1 = day_data1["shifts"][type1]
                if worker2.is_technologist:
                    if worker2.id in shift_data1["technologists"]:
                        shift_data1["technologists"].remove(worker2.id)
                else:
                    if shift_data1["engineer"] == worker2.id:
                        shift_data1["engineer"] = None
            
            # 2. Quitar worker1 de su turno type2
            day_data2 = date_index.get(date2)
            if day_data2:
                shift_data2 = day_data2["shifts"][type2]
                if worker1.is_technologist:
                    if worker1.id in shift_data2["technologists"]:
                        shift_data2["technologists"].remove(worker1.id)
                else:
                    if shift_data2["engineer"] == worker1.id:
                        shift_data2["engineer"] = None
            
            # 3. Actualizar registros de trabajadores
            worker1.shifts = [(d, s) for d, s in worker1.shifts if not (d == date2 and s == type2)]
            worker2.shifts = [(d, s) for d, s in worker2.shifts if not (d == date1 and s == type1)]
            
            # 4. Asignar nuevos turnos
            schedule.assign_worker(worker1, date1, type1)
            schedule.assign_worker(worker2, date2, type2)
            
            return True
    
    return False


def transfer_premium_shift(schedule, from_worker, to_worker, date_index=None):
    """
    Transfiere un turno premium (fin de semana o noche) entre trabajadores.
    Versión mejorada que prioriza mejor los turnos más valiosos y usa el índice.
    
    Args:
        schedule: Horario a modificar
        from_worker: Trabajador origen
        to_worker: Trabajador destino
        date_index: Índice de fechas para acceso rápido
        
    Returns:
        bool: True si se realizó la transferencia, False en caso contrario
    """
    # Usar índice para acceso O(1)
    if date_index is None:
        date_index = create_date_index(schedule)
    
    # Identificar turnos premium del trabajador origen
    premium_shifts = []
    for date, shift_type in from_worker.shifts:
        is_weekend = date.weekday() >= 5  # 5=Sábado, 6=Domingo
        is_night = shift_type == "Noche"
        is_holiday = is_colombian_holiday(date)  # Añadir verificación de festivos
        
        if is_weekend or is_night or is_holiday:
            premium_shifts.append((date, shift_type))
    
    # Calcular valor exacto de compensación para ordenar mejor
    def premium_value(shift):
        date, shift_type = shift
        return calculate_compensation(date, shift_type)
    
    # Ordenar por valor real de compensación (descendente)
    premium_shifts.sort(key=premium_value, reverse=True)
    
    # Probar cada turno premium
    for date, shift_type in premium_shifts:
        # Verificar si el trabajador destino puede tomar este turno
        if date in to_worker.days_off:
            continue
            
        if any(d == date for d, _ in to_worker.shifts):
            continue
        
        # Relajar algunas restricciones para aumentar probabilidad de transferencia exitosa
        night_to_day = check_night_to_day_transition(to_worker, date, shift_type)
        consecutive = check_consecutive_shifts(to_worker, date, shift_type)
        
        # Restricciones críticas que nunca deben relajarse
        if night_to_day or consecutive:
            continue
        
        # Verificar si esta transferencia realmente mejorará la equidad
        # Proyectar las nuevas ganancias después de la transferencia
        compensation_value = calculate_compensation(date, shift_type)
        from_worker_new_earnings = from_worker.earnings - compensation_value
        to_worker_new_earnings = to_worker.earnings + compensation_value
        
        # Verificar que la transferencia mejore la equidad y no invierta la situación
        if from_worker_new_earnings < to_worker_new_earnings:
            continue
        
        # Encontrar el turno en el horario usando el índice
        day_data = date_index.get(date)
        
        if day_data:
            shift_data = day_data["shifts"][shift_type]
            
            # Quitar trabajador origen
            if from_worker.is_technologist:
                if from_worker.id in shift_data["technologists"]:
                    shift_data["technologists"].remove(from_worker.id)
            else:
                if shift_data["engineer"] == from_worker.id:
                    shift_data["engineer"] = None
            
            # Quitar del registro del trabajador
            from_worker.shifts = [(d, s) for d, s in from_worker.shifts 
                                if not (d == date and s == shift_type)]
            
            # Asignar al trabajador destino
            schedule.assign_worker(to_worker, date, shift_type)
            
            # Actualizar las ganancias
            from_worker.earnings = from_worker_new_earnings
            to_worker.earnings = to_worker_new_earnings
            
            return True
    
    return False


def optimize_fairness(schedule, technologists, engineers, date_index=None):
    """
    Realiza una optimización final para maximizar la equidad.
    Versión mejorada con umbral de diferencia mínimo y más transferencias.
    
    Args:
        schedule: Horario a optimizar
        technologists: Lista de tecnólogos
        engineers: Lista de ingenieros
        date_index: Índice de fechas para acceso rápido
    """
    print("Realizando optimización final para equidad...")
    
    # Usar índice para acceso O(1)
    if date_index is None:
        date_index = create_date_index(schedule)
    
    # Calcular ganancias por trabajador
    for worker in technologists + engineers:
        worker.earnings = sum(calculate_compensation(d, s) for d, s in worker.shifts)
    
    # Analizar distribución de ganancias
    tech_earnings = [t.earnings for t in technologists]
    eng_earnings = [e.earnings for e in engineers]
    
    tech_min = min(tech_earnings) if tech_earnings else 0
    tech_max = max(tech_earnings) if tech_earnings else 0
    tech_diff_percent = (tech_max - tech_min) / tech_min * 100 if tech_min > 0 else 0
    
    eng_min = min(eng_earnings) if eng_earnings else 0
    eng_max = max(eng_earnings) if eng_earnings else 0
    eng_diff_percent = (eng_max - eng_min) / eng_min * 100 if eng_min > 0 else 0
    
    print(f"  Diferencia de ganancias en tecnólogos: {tech_diff_percent:.1f}%")
    print(f"  Diferencia de ganancias en ingenieros: {eng_diff_percent:.1f}%")
    
    # Umbral reducido al 3% para una distribución casi perfecta
    EQUITY_THRESHOLD = 3.0
    
    # Si la diferencia supera el umbral, intentar equilibrar
    if tech_diff_percent > EQUITY_THRESHOLD:
        print(f"  Optimizando equidad de ganancias en tecnólogos (objetivo: <{EQUITY_THRESHOLD}%)...")
        
        # Realizar múltiples pasadas para un balance perfecto
        max_passes = 3  # Máximo 3 pasadas para evitar bucles excesivos
        current_pass = 0
        
        while tech_diff_percent > EQUITY_THRESHOLD and current_pass < max_passes:
            current_pass += 1
            print(f"    Pasada de optimización {current_pass}, diferencia actual: {tech_diff_percent:.1f}%")
            
            # Ordenar tecnólogos por ganancias
            techs_by_earnings = sorted(technologists, key=lambda t: t.earnings)
            
            # Considerar más trabajadores para las transferencias (enfoque %)
            poorest_count = max(4, int(len(techs_by_earnings) * 0.40))  # 40% con menos ganancias
            richest_count = max(4, int(len(techs_by_earnings) * 0.40))  # 40% con más ganancias
            
            poorest = techs_by_earnings[:poorest_count]
            richest = techs_by_earnings[-richest_count:]
            
            # Aumentar el número máximo de transferencias basado en la magnitud del problema
            base_transfers = 15
            diff_factor = min(3.0, tech_diff_percent / EQUITY_THRESHOLD)  # Factor basado en la gravedad
            max_transfers = int(base_transfers * diff_factor)
            
            print(f"      Permitiendo hasta {max_transfers} transferencias para esta pasada")
            transfers = 0
            
            # Estrategia de priorización mejorada
            # Emparejar el más rico con el más pobre primero
            for rich_idx, rich in enumerate(reversed(richest)):
                if transfers >= max_transfers:
                    break
                    
                for poor_idx, poor in enumerate(poorest):
                    if transfers >= max_transfers:
                        break
                    
                    # Calcular ganancia relativa de la transferencia
                    earnings_gap = rich.earnings - poor.earnings
                    relative_gap = earnings_gap / tech_min * 100 if tech_min > 0 else 0
                    
                    # Solo proceder con transferencias significativas
                    min_relative_gap = 1.0  # 1% mínimo
                    
                    if relative_gap < min_relative_gap:
                        continue
                    
                    # Intentar transferir múltiples turnos si la diferencia es muy grande
                    max_transfers_per_pair = 1
                    if relative_gap > 8.0:
                        max_transfers_per_pair = 3
                    elif relative_gap > 5.0:
                        max_transfers_per_pair = 2
                    
                    pair_transfers = 0
                    while pair_transfers < max_transfers_per_pair and transfers < max_transfers:
                        if transfer_premium_shift(schedule, rich, poor, date_index):
                            transfers += 1
                            pair_transfers += 1
                            
                            # Recalcular ganancias
                            rich.earnings = sum(calculate_compensation(d, s) for d, s in rich.shifts)
                            poor.earnings = sum(calculate_compensation(d, s) for d, s in poor.shifts)
                            
                            print(f"      Transferido turno premium de {rich.get_formatted_id()} ({rich.earnings:.2f}) " + 
                                  f"a {poor.get_formatted_id()} ({poor.earnings:.2f})")
                        else:
                            # Si no se pudo transferir, pasar al siguiente par
                            break
            
            # Verificar si hubo mejora
            if transfers == 0:
                print("      No se pudieron realizar más transferencias. Finalizando optimización.")
                break
                
            # Recalcular estadísticas para próxima pasada
            tech_earnings = [t.earnings for t in technologists]
            tech_min = min(tech_earnings) if tech_earnings else 0
            tech_max = max(tech_earnings) if tech_earnings else 0
            old_diff = tech_diff_percent
            tech_diff_percent = (tech_max - tech_min) / tech_min * 100 if tech_min > 0 else 0
            
            improvement = old_diff - tech_diff_percent
            print(f"      Mejora: {improvement:.2f}%, nueva diferencia: {tech_diff_percent:.2f}%")
            
            # Si la mejora es muy pequeña, no continuar
            if improvement < 0.2:  # Menos de 0.2% de mejora
                print("      Mejora insignificante. Finalizando optimización.")
                break
    
    # Similar para ingenieros con umbral reducido
    if eng_diff_percent > EQUITY_THRESHOLD:
        print(f"  Optimizando equidad de ganancias en ingenieros (objetivo: <{EQUITY_THRESHOLD}%)...")
        
        # Similar a tecnólogos, múltiples pasadas
        max_passes = 3
        current_pass = 0
        
        while eng_diff_percent > EQUITY_THRESHOLD and current_pass < max_passes:
            current_pass += 1
            print(f"    Pasada de optimización {current_pass}, diferencia actual: {eng_diff_percent:.1f}%")
            
            # Ordenar ingenieros por ganancias
            engs_by_earnings = sorted(engineers, key=lambda e: e.earnings)
            
            # Para ingenieros, como son pocos, considerar a todos
            poorest = engs_by_earnings[:len(engs_by_earnings)//2]  # Primera mitad
            richest = engs_by_earnings[len(engs_by_earnings)//2:]  # Segunda mitad
            
            # Permitir más transferencias para grupos pequeños

            max_transfers = 8
            transfers = 0
            
            for rich in richest:
                if transfers >= max_transfers:
                    break
                    
                for poor in poorest:
                    if transfers >= max_transfers:
                        break
                    
                    # Calcular si vale la pena la transferencia
                    earnings_gap = rich.earnings - poor.earnings
                    relative_gap = earnings_gap / eng_min * 100 if eng_min > 0 else 0
                    
                    if relative_gap < 1.0:  # Ignorar diferencias mínimas
                        continue
                    
                    # Intentar hasta 2 transferencias por par si la diferencia es grande
                    max_transfers_per_pair = 1
                    if relative_gap > 5.0:
                        max_transfers_per_pair = 2
                    
                    pair_transfers = 0
                    while pair_transfers < max_transfers_per_pair and transfers < max_transfers:
                        if transfer_premium_shift(schedule, rich, poor, date_index):
                            transfers += 1
                            pair_transfers += 1
                            
                            # Recalcular ganancias
                            rich.earnings = sum(calculate_compensation(d, s) for d, s in rich.shifts)
                            poor.earnings = sum(calculate_compensation(d, s) for d, s in poor.shifts)
                            
                            print(f"      Transferido turno premium de {rich.get_formatted_id()} ({rich.earnings:.2f}) " +
                                 f"a {poor.get_formatted_id()} ({poor.earnings:.2f})")
                        else:
                            break
            
            # Verificar si hubo mejora
            if transfers == 0:
                break
                
            # Recalcular estadísticas para próxima pasada
            eng_earnings = [e.earnings for e in engineers]
            eng_min = min(eng_earnings) if eng_earnings else 0
            eng_max = max(eng_earnings) if eng_earnings else 0
            old_diff = eng_diff_percent
            eng_diff_percent = (eng_max - eng_min) / eng_min * 100 if eng_min > 0 else 0
            
            improvement = old_diff - eng_diff_percent
            print(f"      Mejora: {improvement:.2f}%, nueva diferencia: {eng_diff_percent:.2f}%")
            
            if improvement < 0.3:  # Menos de 0.3% de mejora para ingenieros
                break
    
    # Reportar equidad final
    tech_earnings = [t.earnings for t in technologists]
    eng_earnings = [e.earnings for e in engineers]
    
    tech_min = min(tech_earnings) if tech_earnings else 0
    tech_max = max(tech_earnings) if tech_earnings else 0
    tech_diff_percent = (tech_max - tech_min) / tech_min * 100 if tech_min > 0 else 0
    
    eng_min = min(eng_earnings) if eng_earnings else 0
    eng_max = max(eng_earnings) if eng_earnings else 0
    eng_diff_percent = (eng_max - eng_min) / eng_min * 100 if eng_min > 0 else 0
    
    print(f"  Equidad final: Tecnólogos {tech_diff_percent:.2f}%, Ingenieros {eng_diff_percent:.2f}%")
    
    # Calcular estadísticas detalladas
    tech_avg = sum(tech_earnings) / len(tech_earnings) if tech_earnings else 0
    eng_avg = sum(eng_earnings) / len(eng_earnings) if eng_earnings else 0
    
    tech_std_dev = (sum((e - tech_avg) ** 2 for e in tech_earnings) / len(tech_earnings)) ** 0.5 if tech_earnings else 0
    eng_std_dev = (sum((e - eng_avg) ** 2 for e in eng_earnings) / len(eng_earnings)) ** 0.5 if eng_earnings else 0
    
    print(f"  Estadísticas de compensación Tecnólogos: " +
          f"Min={tech_min:.2f}, Max={tech_max:.2f}, Promedio={tech_avg:.2f}, Desv={tech_std_dev:.2f}")
    print(f"  Estadísticas de compensación Ingenieros: " +
          f"Min={eng_min:.2f}, Max={eng_max:.2f}, Promedio={eng_avg:.2f}, Desv={eng_std_dev:.2f}")


###########################################################################
# FUNCIONES DE VALIDACIÓN Y CORRECCIÓN                                    #
###########################################################################

def fix_schedule_issues(schedule, technologists, engineers, date_index=None):
    """
    Verifica y corrige problemas de cantidad de personal, garantizando cobertura.
    
    Args:
        schedule: Horario a modificar
        technologists: Lista de tecnólogos
        engineers: Lista de ingenieros
        date_index: Índice de fechas para acceso rápido
    """
    # Usar índice para acceso O(1)
    if date_index is None:
        date_index = create_date_index(schedule)
    
    # Primero validar para identificar problemas
    violations = validate_schedule(schedule)
    tech_count_issues = [v for v in violations if "tecnólogos cuando deberían ser" in v]
    eng_missing_issues = [v for v in violations if "Falta ingeniero" in v]
    
    if not (tech_count_issues or eng_missing_issues):
        return  # No hay problemas de personal, terminar
    
    print(f"Encontrados {len(tech_count_issues) + len(eng_missing_issues)} problemas de personal. Corrigiendo...")
    
    # Ordenar los problemas para resolver primero los más críticos
    tech_count_issues.sort(key=lambda issue: extract_tech_count(issue))
    
    # 1. Corregir primero problemas de ingeniero faltante - absolutamente crítico
    for issue in eng_missing_issues:
        correct_engineer_issue(issue, schedule, engineers, date_index)
        
    # 2. Corregir problemas de cantidad de tecnólogos
    for issue in tech_count_issues:
        correct_technologist_issue(issue, schedule, technologists, date_index)


def extract_tech_count(issue):
    """
    Extrae el conteo de tecnólogos de un mensaje de violación.
    
    Args:
        issue: Mensaje de violación
        
    Returns:
        int: Número de tecnólogos actual en el mensaje
    """
    match = re.search(r'(\d+) tecnólogos cuando', issue)
    return int(match.group(1)) if match else 999  # Valor alto para ordenar correctamente


def correct_engineer_issue(issue, schedule, engineers, date_index):
    """
    Corrige un problema de ingeniero faltante.
    
    Args:
        issue: Mensaje de violación
        schedule: Horario a modificar
        engineers: Lista de ingenieros
        date_index: Índice de fechas para acceso rápido
    """
    try:
        # Extraer fecha y turno
        parts = issue.split()
        if len(parts) < 4:
            print(f"Formato de mensaje inesperado: {issue}")
            return
            
        date_str = parts[2]
        shift_type = parts[3].replace(":", "")
        
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            print(f"Formato de fecha incorrecto en: {issue}")
            return
            
        print(f"Corrigiendo falta de ingeniero: {date_str} {shift_type}...")
        
        # Clasificar ingenieros por restricciones
        engs_no_restrictions = []
        engs_with_restrictions = []
        engs_with_day_off = []
        
        for eng in engineers:
            # Si ya tiene asignación ese día, no considerarlo
            if any(d == date for d, _ in eng.shifts):
                continue
                
            has_day_off = date in eng.days_off
            night_to_day = check_night_to_day_transition(eng, date, shift_type)
            consecutive = check_consecutive_shifts(eng, date, shift_type)
            adequate_rest = check_adequate_rest(eng, date, shift_type)
            
            if has_day_off:
                engs_with_day_off.append(eng)
            elif night_to_day or consecutive or not adequate_rest:
                engs_with_restrictions.append(eng)
            else:
                engs_no_restrictions.append(eng)
        
        # Ordenar cada grupo por número de turnos
        engs_no_restrictions.sort(key=lambda e: (e.get_shift_count(), e.get_shift_types_count().get(shift_type, 0)))
        engs_with_restrictions.sort(key=lambda e: (e.get_shift_count(), e.get_shift_types_count().get(shift_type, 0)))
        engs_with_day_off.sort(key=lambda e: (len(e.days_off), -e.get_shift_count()))
        
        # Intentar asignar en orden de prioridad
        selected_eng = None
        
        if engs_no_restrictions:
            selected_eng = engs_no_restrictions[0]
        elif engs_with_restrictions:
            selected_eng = engs_with_restrictions[0]
        elif engs_with_day_off:
            selected_eng = engs_with_day_off[0]
            # Quitar el día libre
            selected_eng.days_off.remove(date)
            print(f"    ⚠️ CRÍTICO: {selected_eng.get_formatted_id()} pierde día libre para cubrir turno esencial")
        else:
            # Si todos los ingenieros ya están asignados ese día, elige uno para reasignar
            selected_eng = find_engineer_to_reassign(schedule, date, shift_type, engineers, date_index)
        
        if selected_eng:
            # Asignar al ingeniero seleccionado
            schedule.assign_worker(selected_eng, date, shift_type)
            print(f"    Asignado {selected_eng.get_formatted_id()} a {date_str} {shift_type}")
    
    except Exception as e:
        print(f"Error al procesar problema de ingeniero: {issue}")
        print(f"Detalles del error: {str(e)}")


def find_engineer_to_reassign(schedule, date, shift_type, engineers, date_index):
    """
    Encuentra un ingeniero para reasignar si todos están ocupados.
    
    Args:
        schedule: Horario a modificar
        date: Fecha del turno
        shift_type: Tipo de turno
        engineers: Lista de ingenieros
        date_index: Índice de fechas para acceso rápido
        
    Returns:
        Engineer: Ingeniero seleccionado o None
    """
    for eng in engineers:
        # Ver si tiene turno ese día y si es de menor prioridad
        current_shifts = [(d, s) for d, s in eng.shifts if d == date]
        if current_shifts:
            current_shift_type = current_shifts[0][1]
            
            # Calcular prioridades de turno (Noche > Tarde > Mañana)
            shift_priority = {"Noche": 3, "Tarde": 2, "Mañana": 1}
            current_priority = shift_priority.get(current_shift_type, 0)
            needed_priority = shift_priority.get(shift_type, 0)
            
            # Si el turno actual es de menor prioridad que el necesario
            if current_priority < needed_priority:
                # Eliminar su asignación actual
                eng.shifts = [(d, s) for d, s in eng.shifts if not (d == date and s == current_shift_type)]
                
                # Actualizar el horario
                day_data = date_index.get(date)
                if day_data:
                    shift_data = day_data["shifts"][current_shift_type]
                    if shift_data["engineer"] == eng.id:
                        shift_data["engineer"] = None
                
                # Buscar ingeniero para el turno que quedó libre
                for backup_eng in engineers:
                    if backup_eng.id != eng.id and not any(d == date for d, _ in backup_eng.shifts):
                        # Asignar el turno libre al backup
                        schedule.assign_worker(backup_eng, date, current_shift_type)
                        print(f"    Reasignado: {backup_eng.get_formatted_id()} a {date.strftime('%d/%m/%Y')} {current_shift_type}")
                        break
                return eng
                
            # Si es el turno de mañana y necesitamos noche, otra estrategia
            elif current_shift_type == "Mañana" and shift_type == "Noche":
                # Eliminar su asignación actual
                eng.shifts = [(d, s) for d, s in eng.shifts if not (d == date and s == current_shift_type)]
                
                # Actualizar el horario
                day_data = date_index.get(date)
                if day_data:
                    shift_data = day_data["shifts"][current_shift_type]
                    if shift_data["engineer"] == eng.id:
                        shift_data["engineer"] = None
                
                # Buscar ingeniero para el turno que quedó libre
                for backup_eng in engineers:
                    if backup_eng.id != eng.id and not any(d == date for d, _ in backup_eng.shifts):
                        # Asignar el turno libre al backup
                        schedule.assign_worker(backup_eng, date, current_shift_type)
                        print(f"    Reasignado: {backup_eng.get_formatted_id()} a {date.strftime('%d/%m/%Y')} {current_shift_type}")
                        break
                return eng
    
    # No se encontró ningún ingeniero adecuado para reasignar
    print(f"    ⚠️ CRÍTICO: No se pudo encontrar ingeniero para reasignar en {date.strftime('%d/%m/%Y')} {shift_type}")
    return None


def correct_technologist_issue(issue, schedule, technologists, date_index):
    """
    Corrige un problema de cantidad de tecnólogos.
    
    Args:
        issue: Mensaje de violación
        schedule: Horario a modificar
        technologists: Lista de tecnólogos
        date_index: Índice de fechas para acceso rápido
    """
    try:
        # Extraer fecha y turno
        parts = issue.split()
        if len(parts) < 4:
            print(f"Formato de mensaje inesperado: {issue}")
            return
            
        date_str = parts[2]
        shift_type = parts[3].replace(":", "")
        
        # Extraer conteos actuales y requeridos
        current_match = re.search(r'(\d+) tecnólogos cuando', issue)
        required_match = re.search(r'deberían ser (\d+)', issue)
        
        if not (current_match and required_match):
            print(f"No se pudieron extraer conteos de: {issue}")
            return
            
        current_count = int(current_match.group(1))
        required_count = int(required_match.group(1))
        
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            print(f"Formato de fecha incorrecto en: {issue}")
            return
            
        print(f"Corrigiendo turno: {date_str} {shift_type}, actual={current_count}, requerido={required_count}")
        
        # Obtener el día del horario
        day_data = date_index.get(date)
        
        if not day_data:
            print(f"  Error: No se encontró el día {date_str} en el horario.")
            return
        
        shift_data = day_data["shifts"][shift_type]
        
        if current_count < required_count:
            # Necesitamos añadir tecnólogos
            needed = required_count - current_count
            print(f"  Añadiendo {needed} tecnólogos a {date_str} {shift_type}")
            
            # Obtener tecnólogos ya asignados
            assigned_techs = [t for t in technologists if t.id in shift_data["technologists"]]
            
            # Encontrar tecnólogos disponibles con diferentes niveles de restricciones
            available_no_restrictions = []
            available_with_restrictions = []
            available_with_day_off = []
            
            for tech in technologists:
                # Si ya está asignado a este turno, ignorar
                if tech.id in shift_data["technologists"]:
                    continue
                
                # Si ya tiene otro turno ese día, ignorar
                if any(d == date for d, _ in tech.shifts):
                    continue
                
                # Verificar restricciones
                has_day_off = date in tech.days_off
                night_to_day = check_night_to_day_transition(tech, date, shift_type)
                consecutive = check_consecutive_shifts(tech, date, shift_type)
                adequate_rest = check_adequate_rest(tech, date, shift_type)
                
                if has_day_off:
                    available_with_day_off.append(tech)
                elif night_to_day or consecutive or not adequate_rest:
                    available_with_restrictions.append(tech)
                else:
                    available_no_restrictions.append(tech)
            
            # Ordenar cada grupo por criterios optimizados
            is_premium = date.weekday() >= 5 or shift_type == "Noche"
            
            if is_premium:
                # Para turnos premium, priorizar equidad económica
                available_no_restrictions.sort(key=lambda t: getattr(t, 'earnings', t.get_shift_count()))
                available_with_restrictions.sort(key=lambda t: getattr(t, 'earnings', t.get_shift_count()))
            else:
                # Para turnos normales, priorizar distribución de carga
                available_no_restrictions.sort(key=lambda t: (t.get_shift_count(), 
                                                           t.get_shift_types_count().get(shift_type, 0)))
                available_with_restrictions.sort(key=lambda t: (t.get_shift_count(),
                                                            t.get_shift_types_count().get(shift_type, 0)))
            
            # Ordenar por días libres y carga
            available_with_day_off.sort(key=lambda t: (-len(t.days_off), t.get_shift_count()))
            
            # Seleccionar tecnólogos para añadir
            to_add = []
            remaining = needed
            
            # Primero del grupo sin restricciones
            to_add.extend(available_no_restrictions[:remaining])
            remaining -= len(to_add)
            
            # Si necesitamos más, del grupo con restricciones
            if remaining > 0:
                to_add.extend(available_with_restrictions[:remaining])
                remaining -= len(available_with_restrictions[:remaining])
            
            # Si todavía faltan, usar incluso tecnólogos con día libre
            if remaining > 0:
                print(f"  ⚠️ CRÍTICO: Faltan {remaining} tecnólogos para un turno esencial. Usando días libres.")
                
                crisis_techs = available_with_day_off[:remaining]
                
                for tech in crisis_techs:
                    # Quitar día libre
                    if date in tech.days_off:
                        tech.days_off.remove(date)
                        print(f"    ⚠️ CRÍTICO: {tech.get_formatted_id()} pierde día libre para cubrir turno esencial")
                    to_add.append(tech)
            
            # Asignar tecnólogos adicionales
            for tech in to_add:
                schedule.assign_worker(tech, date, shift_type)
                print(f"    Añadido {tech.get_formatted_id()} a {date_str} {shift_type}")
                
        elif current_count > required_count:
            # Necesitamos quitar tecnólogos
            to_remove = current_count - required_count
            print(f"  Quitando {to_remove} tecnólogos de {date_str} {shift_type}")
            
            # Obtener todos los tecnólogos asignados
            assigned_techs = [t for t in technologists if t.id in shift_data["technologists"]]
            
            # Ordenar por compensación (descendente) para mejorar equidad económica
            # y por número de turnos (descendente) para distribuir mejor la carga
            assigned_techs.sort(key=lambda t: (getattr(t, 'earnings', 0), -t.get_shift_count()), reverse=True)
            
            # Quitar los que tienen más ganancias o más turnos
            for i in range(to_remove):
                if i < len(assigned_techs):
                    tech = assigned_techs[i]
                    
                    # Quitar del horario
                    shift_data["technologists"].remove(tech.id)
                    
                    # Quitar del registro del trabajador
                    tech.shifts = [(d, s) for d, s in tech.shifts 
                                  if not (d == date and s == shift_type)]
                    
                    print(f"    Quitado {tech.get_formatted_id()} de {date_str} {shift_type}")
    
    except Exception as e:
        print(f"Error al procesar problema de tecnólogos: {issue}")
        print(f"Detalles del error: {str(e)}")


def resolve_constraint_violations(schedule, technologists, engineers, date_index=None):
    """
    Resuelve violaciones de restricciones en el horario.
    
    Args:
        schedule: Horario a modificar
        technologists: Lista de tecnólogos
        engineers: Lista de ingenieros
        date_index: Índice de fechas para acceso rápido
    """
    # Usar índice para acceso O(1)
    if date_index is None:
        date_index = create_date_index(schedule)
    
    # Obtener todas las violaciones
    violations = validate_schedule(schedule)
    
    # Filtrar violaciones de restricciones (no de cantidad de personal)
    constraint_violations = [v for v in violations 
                           if "no tiene descanso adecuado" in v or 
                              "tiene transición de noche a día" in v or
                              "tiene turnos consecutivos" in v]
    
    if not constraint_violations:
        return  # No hay violaciones de restricciones
    
    print(f"Resolviendo {len(constraint_violations)} violaciones de restricciones...")
    
    # Agrupar violaciones por trabajador
    violations_by_worker = {}
    for violation in constraint_violations:
        worker_id = violation.split()[0]  # Primer elemento es el ID
        if worker_id not in violations_by_worker:
            violations_by_worker[worker_id] = []
        violations_by_worker[worker_id].append(violation)
    
    # Resolver violaciones trabajador por trabajador
    for worker_id, worker_violations in violations_by_worker.items():
        print(f"  Resolviendo violaciones para {worker_id}...")
        
        # Encontrar el trabajador
        worker = None
        for w in technologists + engineers:
            if w.get_formatted_id() == worker_id:
                worker = w
                break
        
        if not worker:
            continue
        
        # Agrupar violaciones por fecha
        violations_by_date = {}
        for violation in worker_violations:
            # Extraer las fechas de la violación
            try:
                if "transición de noche a día" in violation:
                    parts = violation.split(": ")[1].split(" -> ")
                    date1_str = parts[0].split()[0]
                    date2_str = parts[1].split()[0]
                    date1 = datetime.strptime(date1_str, "%Y-%m-%d")
                    date2 = datetime.strptime(date2_str, "%Y-%m-%d")
                    
                    # La violación está principalmente en el segundo turno
                    if date2 not in violations_by_date:
                        violations_by_date[date2] = []
                    violations_by_date[date2].append(violation)
                elif "no tiene descanso adecuado" in violation:
                    parts = violation.split("entre ")[1].split(" y ")
                    date1_str = parts[0].split()[0]
                    date2_str = parts[1].split()[0]
                    date1 = datetime.strptime(date1_str, "%Y-%m-%d")
                    date2 = datetime.strptime(date2_str, "%Y-%m-%d")
                    
                    # La violación está en ambos turnos pero es más fácil corregir en el segundo
                    if date2 not in violations_by_date:
                        violations_by_date[date2] = []
                    violations_by_date[date2].append(violation)
                elif "tiene turnos consecutivos" in violation:
                    date_str = re.search(r'\d{4}-\d{2}-\d{2}', violation).group(0)
                    date = datetime.strptime(date_str, "%Y-%m-%d")
                    
                    if date not in violations_by_date:
                        violations_by_date[date] = []
                    violations_by_date[date].append(violation)
            except Exception as e:
                print(f"    Error al procesar violación: {violation}")
                print(f"    Detalles: {str(e)}")
                continue
        
        # Resolver cada fecha con violaciones
        for date, date_violations in violations_by_date.items():
            print(f"    Resolviendo violaciones el {date.strftime('%Y-%m-%d')}...")
            
            # Determinar qué turno debemos cambiar
            shifts_to_change = []
            for violation in date_violations:
                try:
                    if "transición de noche a día" in violation:
                        # Cambiar el turno de mañana
                        shifts_to_change.append("Mañana")
                    elif "no tiene descanso adecuado" in violation:
                        # Extraer el segundo turno
                        shift_type = re.search(r'y (\w+)\.', violation).group(1)
                        shifts_to_change.append(shift_type)
                    elif "tiene turnos consecutivos" in violation:
                        # Extraer los turnos consecutivos
                        shifts = re.findall(r'(Mañana|Tarde|Noche)', violation)
                        if len(shifts) >= 2:
                            shifts_to_change.extend(shifts)
                except Exception as e:
                    print(f"      Error al extraer turno de violación: {violation}")
                    print(f"      Detalles: {str(e)}")
                    continue
            
            # Eliminar duplicados
            shifts_to_change = list(set(shifts_to_change))
            
            # Para cada turno a cambiar
            for shift_type in shifts_to_change:
                # Obtener el día usando el índice
                day_data = date_index.get(date)
                
                if day_data:
                    shift_data = day_data["shifts"][shift_type]
                    
                    # Verificar si el trabajador está asignado a este turno
                    is_assigned = False
                    if worker.is_technologist:
                        is_assigned = worker.id in shift_data["technologists"]
                    else:
                        is_assigned = shift_data["engineer"] == worker.id
                    
                    if is_assigned:
                        # Quitar al trabajador
                        if worker.is_technologist:
                            shift_data["technologists"].remove(worker.id)
                        else:
                            shift_data["engineer"] = None
                        
                        # Quitar del registro del trabajador
                        worker.shifts = [(d, s) for d, s in worker.shifts 
                                       if not (d == date and s == shift_type)]
                        
                        print(f"      Quitado {worker.get_formatted_id()} de {date.strftime('%Y-%m-%d')} {shift_type}")
                        
                        # Añadir un reemplazo que no cause nuevas violaciones
                        replace_worker(schedule, date, shift_type, worker, 
                                      technologists if worker.is_technologist else engineers, date_index)
    
    # Verificar nuevamente para reportar progreso
    remaining_violations = validate_schedule(schedule)
    constraint_violations = [v for v in remaining_violations 
                           if "no tiene descanso adecuado" in v or 
                              "tiene transición de noche a día" in v or
                              "tiene turnos consecutivos" in v]
    
    if constraint_violations:
        print(f"  ⚠️ Quedan {len(constraint_violations)} violaciones de restricciones después de correcciones")
    else:
        print("  ✓ Todas las violaciones de restricciones resueltas exitosamente")


def replace_worker(schedule, date, shift_type, removed_worker, available_workers, date_index=None):
    """
    Encuentra un trabajador de reemplazo para un turno sin generar nuevas violaciones.
    
    Args:
        schedule: Horario a modificar
        date: Fecha del turno
        shift_type: Tipo de turno
        removed_worker: Trabajador que se quitó
        available_workers: Lista de trabajadores disponibles
        date_index: Índice de fechas para acceso rápido
        
    Returns:
        bool: True si se reemplazó con éxito, False en caso contrario
    """
    # Usar índice para acceso O(1)
    if date_index is None:
        date_index = create_date_index(schedule)
    
    # Obtener día y turno usando el índice
    day_data = date_index.get(date)
    
    if not day_data:
        return False
    
    shift_data = day_data["shifts"][shift_type]
    
    # Determinar cuántos trabajadores se necesitan
    if removed_worker.is_technologist:
        current = len(shift_data["technologists"])
        required = TECHS_PER_SHIFT[shift_type]
        needed = required - current
    else:
        current = 1 if shift_data["engineer"] is not None else 0
        needed = 1 - current
    
    if needed <= 0:
        return True  # No necesitamos reemplazo
    
    # Encontrar reemplazos que no causen violaciones
    suitable_replacements = []
    for worker in available_workers:
        # No considerar al trabajador que acabamos de quitar
        if worker.id == removed_worker.id:
            continue
            
        # Verificar si ya está asignado a este turno
        if worker.is_technologist:
            if worker.id in shift_data["technologists"]:
                continue
        else:
            if shift_data["engineer"] == worker.id:
                continue
        
        # Verificar si tiene otro turno ese día
        if any(d == date for d, _ in worker.shifts):
            continue
        
        # Verificar si es un día libre
        if date in worker.days_off:
            continue
        
        # Verificar restricciones críticas
        night_to_day = check_night_to_day_transition(worker, date, shift_type)
        consecutive = check_consecutive_shifts(worker, date, shift_type)
        adequate_rest = check_adequate_rest(worker, date, shift_type)
        
        if not night_to_day and not consecutive and adequate_rest:
            suitable_replacements.append(worker)
    
    # Si no hay reemplazos adecuados, relajar la restricción de descanso adecuado
    if not suitable_replacements:
        for worker in available_workers:
            if worker.id == removed_worker.id:
                continue
                
            if worker.is_technologist:
                if worker.id in shift_data["technologists"]:
                    continue
            else:
                if shift_data["engineer"] == worker.id:
                    continue
            
            if any(d == date for d, _ in worker.shifts):
                continue
            
            if date in worker.days_off:
                continue
            
            # Solo verificar restricciones críticas absolutas
            night_to_day = check_night_to_day_transition(worker, date, shift_type)
            consecutive = check_consecutive_shifts(worker, date, shift_type)
            
            if not night_to_day and not consecutive:
                suitable_replacements.append(worker)
    
    # Ordenar por número de turnos (menos turnos primero)
    suitable_replacements.sort(key=lambda w: (w.get_shift_count(), 
                                           w.get_shift_types_count().get(shift_type, 0)))
    
    # Seleccionar y asignar
    if suitable_replacements:
        replacement = suitable_replacements[0]
        schedule.assign_worker(replacement, date, shift_type)
        print(f"      Añadido {replacement.get_formatted_id()} como reemplazo")
        return True
    else:
        print(f"      ⚠️ No se encontró reemplazo adecuado para {date.strftime('%Y-%m-%d')} {shift_type}")

        return False
    
    