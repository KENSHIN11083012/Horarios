"""
Módulo especializado para la gestión de días libres.
"""

from datetime import datetime, timedelta
from utils.date_utils import date_range, get_week_start, get_week_end
from config import is_colombian_holiday
from config.settings import TECHS_PER_SHIFT, ENG_PER_SHIFT
from algorithms.common import create_date_index

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
                for shift_type in ["Mañana", "Tarde", "Noche"]:
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