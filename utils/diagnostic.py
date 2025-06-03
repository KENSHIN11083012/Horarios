"""
Script de diagnóstico para analizar problemas específicos de días libres
"""

def analyze_days_off_failures(schedule):
    """
    Analiza en detalle por qué fallan los días libres semanales
    """
    from datetime import timedelta
    from utils.date_utils import get_week_start, get_week_end, date_range
    
    print("=== DIAGNÓSTICO DETALLADO DE DÍAS LIBRES ===")
    
    # Obtener todas las semanas
    weeks = []
    current_date = get_week_start(schedule.start_date)
    
    while current_date <= schedule.end_date:
        week_end = get_week_end(current_date)
        
        if not (week_end < schedule.start_date or current_date > schedule.end_date):
            effective_start = max(current_date, schedule.start_date)
            effective_end = min(week_end, schedule.end_date)
            effective_days = (effective_end - effective_start).days + 1
            weeks.append({
                'start': current_date,
                'end': week_end,
                'effective_start': effective_start,
                'effective_end': effective_end,
                'effective_days': effective_days,
                'label': f"{effective_start.strftime('%d/%m')} - {effective_end.strftime('%d/%m')}"
            })
        
        current_date += timedelta(days=7)
    
    print(f"Total de semanas analizadas: {len(weeks)}")
    
    # Analizar cada trabajador
    problematic_workers = {}
    
    for worker in schedule.get_all_workers():
        worker_id = worker.get_formatted_id()
        worker_problems = []
        
        for i, week in enumerate(weeks):
            # Días libres en esta semana
            days_off_in_week = [d for d in worker.days_off 
                              if week['effective_start'] <= d <= week['effective_end']]
            
            # Turnos en esta semana
            shifts_in_week = [(d, s) for d, s in worker.shifts 
                            if week['effective_start'] <= d <= week['effective_end']]
            
            # Solo considerar problemático si la semana tiene al menos 4 días efectivos
            if week['effective_days'] >= 4 and not days_off_in_week:
                worker_problems.append({
                    'week_num': i + 1,
                    'week_label': week['label'],
                    'effective_days': week['effective_days'],
                    'shifts_count': len(shifts_in_week),
                    'shifts_detail': shifts_in_week,
                    'days_off_count': len(days_off_in_week)
                })
        
        if worker_problems:
            problematic_workers[worker_id] = {
                'total_problems': len(worker_problems),
                'problems': worker_problems,
                'total_days_off': len(worker.days_off),
                'total_shifts': len(worker.shifts)
            }
    
    # Reportar hallazgos
    print(f"\nTrabajadores con problemas: {len(problematic_workers)}")
    
    for worker_id, data in sorted(problematic_workers.items()):
        print(f"\n{worker_id}:")
        print(f"  - Problemas en {data['total_problems']} semanas")
        print(f"  - Total días libres: {data['total_days_off']}")
        print(f"  - Total turnos: {data['total_shifts']}")
        
        for problem in data['problems']:
            print(f"    Semana {problem['week_num']} ({problem['week_label']}): "
                  f"{problem['shifts_count']} turnos, {problem['effective_days']} días efectivos")
    
    # Análisis de patrones
    print(f"\n=== ANÁLISIS DE PATRONES ===")
    
    # Semanas más problemáticas
    week_problems = {}
    for worker_data in problematic_workers.values():
        for problem in worker_data['problems']:
            week_label = problem['week_label']
            if week_label not in week_problems:
                week_problems[week_label] = 0
            week_problems[week_label] += 1
    
    print("Semanas con más problemas:")
    for week, count in sorted(week_problems.items(), key=lambda x: x[1], reverse=True):
        print(f"  {week}: {count} trabajadores afectados")
    
    # Trabajadores más afectados
    print("\nTrabajadores más afectados:")
    sorted_workers = sorted(problematic_workers.items(), 
                          key=lambda x: x[1]['total_problems'], reverse=True)
    
    for worker_id, data in sorted_workers[:10]:
        print(f"  {worker_id}: {data['total_problems']} semanas problemáticas")
    
    return problematic_workers, weeks

def recommend_fixes(problematic_workers, weeks):
    """
    Recomienda correcciones específicas basadas en el diagnóstico
    """
    print(f"\n=== RECOMENDACIONES DE CORRECCIÓN ===")
    
    # Detectar si el problema es principalmente en semanas cortas
    short_week_problems = 0
    full_week_problems = 0
    
    for worker_data in problematic_workers.values():
        for problem in worker_data['problems']:
            if problem['effective_days'] < 7:
                short_week_problems += 1
            else:
                full_week_problems += 1
    
    print(f"Problemas en semanas cortas (<7 días): {short_week_problems}")
    print(f"Problemas en semanas completas: {full_week_problems}")
    
    if short_week_problems > full_week_problems:
        print("\n🎯 PROBLEMA PRINCIPAL: Lógica de semanas parciales")
        print("SOLUCIÓN: Ajustar umbral mínimo de días para requerir día libre")
        print("RECOMENDACIÓN: Solo requerir día libre si la semana tiene ≥5 días efectivos")
    
    elif full_week_problems > short_week_problems * 2:
        print("\n🎯 PROBLEMA PRINCIPAL: Algoritmo de asignación de días libres")
        print("SOLUCIÓN: Refactorizar la lógica de ensure_weekly_days_off()")
        print("RECOMENDACIÓN: Priorizar días libres antes que optimización de turnos")
    
    else:
        print("\n🎯 PROBLEMA MIXTO: Múltiples causas")
        print("SOLUCIÓN: Enfoque combinado")
    
    # Recomendar estrategia específica
    print(f"\n📋 ESTRATEGIA RECOMENDADA:")
    print("1. Modificar umbral de semanas cortas (5+ días en lugar de 4+)")
    print("2. Implementar asignación más agresiva de días libres")
    print("3. Priorizar días libres sobre balance de turnos")
    print("4. Validar resultado después de cada asignación")

# Función para usar en el main.py existente
def add_diagnostic_to_main():
    """
    Código para añadir al final de main() existente
    """
    return """
    # AÑADIR AL FINAL DE main() ANTES DE print("Proceso completado con éxito.")
    
    print("\\n=== DIAGNÓSTICO DETALLADO ===")
    from utils.diagnostic import analyze_days_off_failures, recommend_fixes
    problematic_workers, weeks = analyze_days_off_failures(schedule)
    recommend_fixes(problematic_workers, weeks)
    """

if __name__ == "__main__":
    print("Ejecutar este diagnóstico después de generar un horario")
    print("Código para añadir a main.py:")
    print(add_diagnostic_to_main())