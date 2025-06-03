#!/usr/bin/env python3
"""
Generador de Horarios para Centro de Control

Uso:
    python main.py <mes> <año>
    
Ejemplo:
    python main.py 5 2025
"""

import sys
import random
from datetime import datetime
import calendar

from core.worker import Worker
from algorithms.generator import generate_schedule
from utils.exporter import export_to_notion_csv
from utils.visualization import generate_html_visualization
from config.settings import NUM_TECHNOLOGISTS, NUM_ENGINEERS
from core.constraints import validate_schedule
from utils.analysis import analyze_schedule

#Borrar despues

from utils.diagnostic import analyze_days_off_failures, recommend_fixes


def main():
    """Función principal del generador de horarios."""
    if len(sys.argv) < 3:
        print("Uso: python main.py <mes> <año>")
        print("Ejemplo: python main.py 5 2025")
        sys.exit(1)
    
    # Procesar argumentos
    try:
        month = int(sys.argv[1])
        year = int(sys.argv[2])
        
        if month < 1 or month > 12:
            raise ValueError("El mes debe estar entre 1 y 12")
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    # Fijar semilla para reproducibilidad
    random.seed(42)
    
    # Obtener primer y último día del mes
    _, last_day = calendar.monthrange(year, month)
    start_date = datetime(year, month, 1)
    end_date = datetime(year, month, last_day)
    
    print(f"Generando horario para {start_date.strftime('%B %Y')}...")
    
    # Crear trabajadores
    print(f"Inicializando {NUM_TECHNOLOGISTS} tecnólogos y {NUM_ENGINEERS} ingenieros")
    technologists = [Worker(i+1, is_technologist=True) for i in range(NUM_TECHNOLOGISTS)]
    engineers = [Worker(i+1, is_technologist=False) for i in range(NUM_ENGINEERS)]
    
    # Generar horario
    print("Generando horario...")
    schedule = generate_schedule(start_date, end_date, technologists, engineers)
    
    # Última validación
    print("\nVerificación final del horario:")
    violations = validate_schedule(schedule)
    if violations:
        print(f"¡ADVERTENCIA! Se encontraron {len(violations)} problemas en el horario:")
        for v in violations[:10]:
            print(f"  - {v}")
    else:
        print("El horario cumple con todas las reglas requeridas.")
    
    # Exportar para Notion
    notion_filename = f"horario_{start_date.strftime('%m_%Y')}_notion.csv"
    export_to_notion_csv(schedule, notion_filename)
    print(f"\nHorario para Notion generado en: {notion_filename}")
    
    # Generar visualización HTML
    html_filename = f"horario_{start_date.strftime('%m_%Y')}.html"
    generate_html_visualization(schedule, html_filename)
    print(f"Visualización HTML generada en: {html_filename}")
    
    # Generar análisis detallado
    print("\nGenerando análisis detallado de días libres y remuneraciones...")
    analysis_filename = f"analisis_{start_date.strftime('%m_%Y')}.html"
    analysis_results = analyze_schedule(schedule, analysis_filename)
    print(f"Análisis detallado generado en: {analysis_filename}")
    
    # Resumir hallazgos principales
    comp_analysis = analysis_results["compensation_analysis"]["technologists"]
    days_off_analysis = analysis_results["days_off_analysis"]
    
    print("\n=== RESUMEN DE ANÁLISIS DETALLADO ===")
    print(f"Equidad de compensaciones (tecnólogos):")
    print(f"  Rango: {comp_analysis['min']:.2f} - {comp_analysis['max']:.2f}")
    print(f"  Diferencia: {comp_analysis['range_percentage']:.1f}%")
    
    missing_days = days_off_analysis["workers_without_weekly_day_off"]
    print(f"Días libres semanales:")
    if missing_days:
        print(f"  ⚠ {len(missing_days)} casos donde un trabajador no tiene día libre en una semana")
        
        # Mostrar detalles de casos problemáticos
        if len(missing_days) > 0:
            print("\nDetalle de trabajadores sin día libre semanal:")
            for i, case in enumerate(missing_days[:10], 1):
                print(f"  {i}. {case['worker_id']} - Semana {case['week']} ({case.get('effective_days', 'N/A')} días efectivos)")
            
            if len(missing_days) > 10:
                print(f"  ... y {len(missing_days) - 10} casos más.")
                
            print("\nRecomendaciones:")
            print("  1. Revisar manualmente estos casos en el análisis detallado")
            print("  2. Considerar ajustar el algoritmo de asignación de días libres")
            print("  3. En casos críticos, regenerar el horario con otra semilla aleatoria")
    else:
        print("  ✓ Todos los trabajadores tienen al menos un día libre por semana")
    
    # Analizar distribución de tipos de turno
    shift_distribution = analysis_results["shift_distribution"]["per_worker"]
    
    print("\n=== DISTRIBUCIÓN DE TIPOS DE TURNO ===")
    worker_groups = {
        "Tecnólogos": [w for w in schedule.get_all_workers() if w.is_technologist],
        "Ingenieros": [w for w in schedule.get_all_workers() if not w.is_technologist]
    }
    
    for group_name, workers in worker_groups.items():
        print(f"\n{group_name.upper()}:")
        
        # Calcular promedios
        avg_morning = sum(shift_distribution[w.get_formatted_id()]["Mañana"] for w in workers) / len(workers)
        avg_afternoon = sum(shift_distribution[w.get_formatted_id()]["Tarde"] for w in workers) / len(workers)
        avg_night = sum(shift_distribution[w.get_formatted_id()]["Noche"] for w in workers) / len(workers)
        
        print(f"  Promedio de turnos: Mañana={avg_morning:.1f}, Tarde={avg_afternoon:.1f}, Noche={avg_night:.1f}")
    
    # Mostrar estadísticas detalladas por trabajador
    print("\n=== ESTADÍSTICAS DE TURNOS POR TRABAJADOR ===")
    print_worker_stats(technologists, "TECNÓLOGOS")
    print_worker_stats(engineers, "INGENIEROS")

    # DIAGNÓSTICO DETALLADO DE DÍAS LIBRES
    print("\n" + "="*60)
    print("DIAGNÓSTICO DETALLADO DE DÍAS LIBRES")
    print("="*60)
    
    try:
        
        problematic_workers, weeks = analyze_days_off_failures(schedule)
        recommend_fixes(problematic_workers, weeks)
    except ImportError as e:
        print(f"Error al importar diagnóstico: {e}")
        print("Asegúrate de que utils/diagnostic.py existe")
    except Exception as e:
        print(f"Error en diagnóstico: {e}")
    
    print("="*60)
    
    print("\nProceso completado con éxito.")
    print(f"Consulta el análisis detallado en: {analysis_filename}")

def print_worker_stats(workers, title):
    """Muestra estadísticas simples de los trabajadores."""
    print(f"\n{title}:")
    for worker in workers:
        shifts = worker.get_shift_types_count()
        total_shifts = worker.get_shift_count()
        print(f"{worker.get_formatted_id()}: {total_shifts} turnos " +
              f"(M:{shifts['Mañana']}, T:{shifts['Tarde']}, N:{shifts['Noche']}), " +
              f"Compensación: {worker.earnings:.2f}")

if __name__ == "__main__":
    main()