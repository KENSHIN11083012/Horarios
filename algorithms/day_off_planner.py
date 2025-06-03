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
    CORRECCIÓN PRINCIPAL: Asegura días libres semanales con algoritmo más agresivo
    
    CAMBIOS BASADOS EN DIAGNÓSTICO:
    1. Umbral ajustado: 5+ días para requerir día libre (antes 3+)
    2. Algoritmo MÁS AGRESIVO: Garantiza al menos 1 día libre por semana
    3. Manejo especial de semanas problemáticas (inicio/fin de mes)
    """
    print("🔧 APLICANDO CORRECCIÓN DE DÍAS LIBRES...")
    
    if date_index is None:
        date_index = create_date_index(schedule)
    
    # Obtener semanas con criterio corregido
    weeks = get_corrected_weeks(schedule.start_date, schedule.end_date)
    all_workers = technologists + engineers
    
    print(f"  📅 Procesando {len(weeks)} semanas efectivas")
    print(f"  👥 Analizando {len(all_workers)} trabajadores")
    
    # ESTADÍSTICAS INICIALES
    initial_problems = count_initial_problems(all_workers, weeks)
    print(f"  ⚠️  Problemas iniciales detectados: {initial_problems}")
    
    # FASE 1: Asignación inmediata de días críticos
    phase1_assigned = assign_critical_days_off(all_workers, weeks, schedule)
    
    # FASE 2: Completar días libres faltantes con algoritmo agresivo  
    phase2_assigned = complete_missing_days_off(all_workers, weeks, schedule, date_index)
    
    # FASE 3: Validación y corrección final
    phase3_fixes = final_validation_and_emergency_fixes(all_workers, weeks, schedule, date_index)
    
    # ESTADÍSTICAS FINALES
    final_problems = count_final_problems(all_workers, weeks)
    
    print(f"\n📊 RESULTADO DE LA CORRECCIÓN:")
    print(f"  📉 Problemas: {initial_problems} → {final_problems}")
    print(f"  ✅ Asignados Fase 1: {phase1_assigned}")
    print(f"  ✅ Asignados Fase 2: {phase2_assigned}")
    print(f"  🚨 Correcciones Fase 3: {phase3_fixes}")
    
    if final_problems == 0:
        print("  🎉 ¡ÉXITO TOTAL! Todos los trabajadores tienen día libre semanal")
    elif final_problems < initial_problems * 0.2:
        print(f"  🎯 ¡GRAN MEJORA! Reducción del {((initial_problems-final_problems)/initial_problems)*100:.1f}%")
    else:
        print(f"  ⚠️  Aún quedan {final_problems} casos por resolver")
    
    return final_problems

def get_corrected_weeks(start_date, end_date):
    """
    Obtiene semanas con criterio CORREGIDO basado en diagnóstico
    CAMBIO: Solo semanas con 5+ días efectivos (antes 3+)
    """
    weeks = []
    current_week_start = get_week_start(start_date)
    end_week_start = get_week_start(end_date)
    
    while current_week_start <= end_week_start:
        week_end = get_week_end(current_week_start)
        
        if not (week_end < start_date or current_week_start > end_date):
            effective_start = max(current_week_start, start_date)
            effective_end = min(week_end, end_date)
            effective_days = (effective_end - effective_start).days + 1
            
            # CRITERIO CORREGIDO: 5+ días para evitar problemas en semanas cortas
            if effective_days >= 5:
                weeks.append({
                    'start': current_week_start,
                    'end': week_end,
                    'effective_start': effective_start,
                    'effective_end': effective_end,
                    'effective_days': effective_days,
                    'label': f"{effective_start.strftime('%d/%m')} - {effective_end.strftime('%d/%m')}",
                    'is_short': effective_days < 7
                })
        
        current_week_start += timedelta(days=7)
    
    return weeks

def count_initial_problems(workers, weeks):
    """Cuenta problemas iniciales para comparación"""
    problems = 0
    for worker in workers:
        for week in weeks:
            if not has_day_off_in_week(worker, week):
                problems += 1
    return problems

def count_final_problems(workers, weeks):
    """Cuenta problemas finales para validación"""
    problems = 0
    for worker in workers:
        for week in weeks:
            if not has_day_off_in_week(worker, week):
                problems += 1
    return problems

def assign_critical_days_off(workers, weeks, schedule):
    """
    FASE 1: Asignación inmediata de días críticos
    Prioriza trabajadores con menos días libres totales
    """
    print("  🚨 Fase 1: Asignando días libres críticos...")
    
    # Identificar trabajadores más necesitados (como T9, T10 del diagnóstico)
    critical_workers = []
    for worker in workers:
        total_days_off = len(worker.days_off)
        weeks_without_days = sum(1 for week in weeks if not has_day_off_in_week(worker, week))
        
        if total_days_off <= 2 or weeks_without_days >= 3:
            critical_workers.append((worker, weeks_without_days, total_days_off))
    
    # Ordenar por criticidad (más semanas sin días libres primero)
    critical_workers.sort(key=lambda x: (x[1], -x[2]), reverse=True)
    
    assignments = 0
    for worker, weeks_needed, current_days in critical_workers:
        print(f"    🆘 CRÍTICO: {worker.get_formatted_id()} - {weeks_needed} semanas sin día libre")
        
        # Asignar días libres para este trabajador crítico
        for week in weeks:
            if not has_day_off_in_week(worker, week):
                assigned_date = assign_best_day_off(worker, week, schedule)
                if assigned_date:
                    worker.add_day_off(assigned_date)
                    assignments += 1
                    print(f"      ✅ Asignado: {assigned_date.strftime('%d/%m/%Y')}")
    
    return assignments

def assign_best_day_off(worker, week, schedule):
    """
    Encuentra el mejor día para asignar como día libre
    Prioriza días con menos carga de trabajo general
    """
    # Evaluar cada día de la semana
    candidate_days = []
    
    for date in date_range(week['effective_start'], week['effective_end']):
        # Si ya tiene turno o día libre, skip
        if has_shift_on_date(worker, date) or date in worker.days_off:
            continue
        
        # Calcular "score" del día (menor = mejor)
        score = calculate_day_score(date, week)
        candidate_days.append((date, score))
    
    if candidate_days:
        # Seleccionar el día con menor score (mejor opción)
        candidate_days.sort(key=lambda x: x[1])
        return candidate_days[0][0]
    
    return None

def calculate_day_score(date, week):
    """
    Calcula score para un día como candidato a día libre
    MENOR SCORE = MEJOR CANDIDATO
    """
    score = 0
    
    # Preferir días laborables en semanas completas
    if not week['is_short']:
        if date.weekday() < 5:  # Lunes a viernes
            score += 0
        else:  # Fin de semana
            score += 5
    else:
        # En semanas cortas, cualquier día es bueno
        score += 0
    
    # Evitar festivos si es posible
    if is_colombian_holiday(date):
        score += 3
    
    # Preferir días en medio de la semana
    if date.weekday() in [1, 2, 3]:  # Martes, miércoles, jueves
        score -= 2
    
    return score

def complete_missing_days_off(workers, weeks, schedule, date_index):
    """
    FASE 2: Completar días libres faltantes con algoritmo agresivo
    """
    print("  🔄 Fase 2: Completando días libres faltantes...")
    
    assignments = 0
    
    for week in weeks:
        week_label = week['label']
        workers_needing_day_off = [w for w in workers if not has_day_off_in_week(w, week)]
        
        if not workers_needing_day_off:
            continue
        
        print(f"    📅 Semana {week_label}: {len(workers_needing_day_off)} trabajadores necesitan día libre")
        
        for worker in workers_needing_day_off:
            success = False
            
            # ESTRATEGIA 1: Día naturalmente libre
            for date in date_range(week['effective_start'], week['effective_end']):
                if (not has_shift_on_date(worker, date) and 
                    date not in worker.days_off):
                    worker.add_day_off(date)
                    assignments += 1
                    print(f"      ✅ {worker.get_formatted_id()}: {date.strftime('%d/%m')}")
                    success = True
                    break
            
            # ESTRATEGIA 2: Liberar turno de menor impacto
            if not success:
                liberated_date = liberate_shift_for_day_off(worker, week, schedule, date_index)
                if liberated_date:
                    worker.add_day_off(liberated_date)
                    assignments += 1
                    print(f"      🔄 {worker.get_formatted_id()}: {liberated_date.strftime('%d/%m')} (liberado)")
                    success = True
    
    return assignments

def liberate_shift_for_day_off(worker, week, schedule, date_index):
    """
    Libera un turno del trabajador para crear un día libre
    """
    # Encontrar turnos en la semana
    shifts_in_week = [(d, s) for d, s in worker.shifts 
                     if week['effective_start'] <= d <= week['effective_end']]
    
    if not shifts_in_week:
        return None
    
    # Evaluar cada turno por facilidad de liberación
    liberation_candidates = []
    for date, shift_type in shifts_in_week:
        difficulty = calculate_liberation_difficulty(worker, date, shift_type, schedule, date_index)
        liberation_candidates.append((date, shift_type, difficulty))
    
    # Ordenar por facilidad (menor dificultad primero)
    liberation_candidates.sort(key=lambda x: x[2])
    
    # Intentar liberar el más fácil
    for date, shift_type, difficulty in liberation_candidates:
        if difficulty < 30:  # Solo si es relativamente fácil
            if execute_shift_liberation(worker, date, shift_type, schedule, date_index):
                return date
    
    return None

def calculate_liberation_difficulty(worker, date, shift_type, schedule, date_index):
    """
    Calcula la dificultad de liberar un turno específico
    MENOR VALOR = MÁS FÁCIL DE LIBERAR
    """
    difficulty = 0
    
    # Dificultad por tipo de turno
    if shift_type == "Noche":
        difficulty += 20  # Más difícil liberar turnos nocturnos
    elif shift_type == "Tarde":
        difficulty += 10
    
    # Dificultad por día
    if date.weekday() >= 5:  # Fin de semana
        difficulty += 15
    
    if is_colombian_holiday(date):
        difficulty += 10
    
    # Dificultad por cobertura
    day_data = date_index.get(date)
    if day_data:
        shift_data = day_data["shifts"][shift_type]
        
        if worker.is_technologist:
            current_coverage = len(shift_data["technologists"])
            required_coverage = TECHS_PER_SHIFT[shift_type]
            
            if current_coverage <= required_coverage:
                difficulty += 25  # Muy difícil si está en cobertura mínima
            elif current_coverage == required_coverage + 1:
                difficulty += 10  # Moderadamente difícil
        else:
            difficulty += 30  # Muy difícil liberar ingenieros
    
    return difficulty

def execute_shift_liberation(worker, date, shift_type, schedule, date_index):
    """
    Ejecuta la liberación de un turno
    """
    # Quitar del horario
    day_data = date_index.get(date)
    if not day_data:
        return False
    
    shift_data = day_data["shifts"][shift_type]
    
    if worker.is_technologist:
        if worker.id in shift_data["technologists"]:
            shift_data["technologists"].remove(worker.id)
    else:
        if shift_data["engineer"] == worker.id:
            shift_data["engineer"] = None
    
    # Quitar del trabajador
    worker.shifts = [(d, s) for d, s in worker.shifts 
                    if not (d == date and s == shift_type)]
    
    # Buscar reemplazo (opcional)
    find_replacement_if_possible(schedule, date, shift_type, worker, date_index)
    
    return True

def find_replacement_if_possible(schedule, date, shift_type, removed_worker, date_index):
    """
    Busca reemplazo si es posible, pero no es obligatorio
    """
    if removed_worker.is_technologist:
        candidates = schedule.get_technologists()
    else:
        candidates = schedule.get_engineers()
    
    # Buscar candidatos disponibles
    available = [c for c in candidates 
                if (c.id != removed_worker.id and
                    not has_shift_on_date(c, date) and
                    date not in c.days_off)]
    
    if available:
        # Seleccionar el que tenga menos turnos
        replacement = min(available, key=lambda w: w.get_shift_count())
        schedule.assign_worker(replacement, date, shift_type)
        print(f"        🔄 Reemplazo: {replacement.get_formatted_id()}")
        return True
    
    return False

def final_validation_and_emergency_fixes(workers, weeks, schedule, date_index):
    """
    FASE 3: Validación final y correcciones de emergencia
    """
    print("  🚨 Fase 3: Validación final y correcciones de emergencia...")
    
    fixes = 0
    remaining_problems = []
    
    for worker in workers:
        for week in weeks:
            if not has_day_off_in_week(worker, week):
                remaining_problems.append((worker, week))
    
    if not remaining_problems:
        print("    ✅ No se necesitan correcciones de emergencia")
        return 0
    
    print(f"    ⚠️  {len(remaining_problems)} casos requieren corrección de emergencia")
    
    for worker, week in remaining_problems:
        # ÚLTIMO RECURSO: Forzar día libre quitando turno sin reemplazo
        emergency_date = force_emergency_day_off(worker, week, schedule, date_index)
        if emergency_date:
            worker.add_day_off(emergency_date)
            fixes += 1
            print(f"      🚨 EMERGENCIA: {worker.get_formatted_id()} - {emergency_date.strftime('%d/%m')}")
    
    return fixes

def force_emergency_day_off(worker, week, schedule, date_index):
    """
    ÚLTIMO RECURSO: Fuerza un día libre quitando cualquier turno
    """
    # Buscar cualquier turno en la semana para quitar
    shifts_in_week = [(d, s) for d, s in worker.shifts 
                     if week['effective_start'] <= d <= week['effective_end']]
    
    if shifts_in_week:
        # Quitar el primer turno encontrado
        date, shift_type = shifts_in_week[0]
        execute_shift_liberation(worker, date, shift_type, schedule, date_index)
        return date
    else:
        # Si no tiene turnos, asignar primer día disponible
        for date in date_range(week['effective_start'], week['effective_end']):
            if date not in worker.days_off:
                return date
    
    return None

# Funciones auxiliares
def has_day_off_in_week(worker, week):
    """Verifica si el trabajador tiene día libre en la semana"""
    return any(week['effective_start'] <= d <= week['effective_end'] 
              for d in worker.days_off)

def has_shift_on_date(worker, date):
    """Verifica si el trabajador tiene turno en la fecha"""
    return any(d == date for d, _ in worker.shifts)