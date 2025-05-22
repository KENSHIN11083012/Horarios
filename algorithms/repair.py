"""
Módulo especializado para la reparación de horarios con problemas.
"""

import re
from datetime import datetime, timedelta
from core.constraints import check_night_to_day_transition, check_consecutive_shifts, check_adequate_rest
from config.settings import TECHS_PER_SHIFT, ENG_PER_SHIFT
from algorithms.common import create_date_index

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
    from core.constraints import validate_schedule
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
            from config import is_colombian_holiday
            is_premium = date.weekday() >= 5 or shift_type == "Noche" or is_colombian_holiday(date)
            
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
    from core.constraints import validate_schedule
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
    from core.constraints import validate_schedule
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