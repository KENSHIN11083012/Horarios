"""
Módulo para análisis detallado de horarios, enfocado en días de descanso y equidad de remuneraciones.
"""

import math
from datetime import datetime, timedelta
import pandas as pd
import matplotlib.pyplot as plt
from collections import defaultdict
from config.settings import COMPENSATION_RATES

def analyze_schedule(schedule, output_file=None):
    """
    Realiza un análisis completo del horario y genera un reporte detallado.
    
    Args:
        schedule: Objeto Schedule con el horario
        output_file: Ruta del archivo donde guardar el reporte (opcional)
        
    Returns:
        dict: Resultados del análisis
    """
    # Inicializar contenedor de resultados
    results = {
        "days_off_analysis": analyze_days_off(schedule),
        "compensation_analysis": analyze_compensation(schedule),
        "shift_distribution": analyze_shift_distribution(schedule)
    }
    
    # Generar reporte si se solicitó
    if output_file:
        generate_report(results, schedule, output_file)
    
    return results

def analyze_days_off(schedule):
    """
    Analiza los días de descanso para cada trabajador.
    
    Verifica:
    - Un día libre por semana
    - Días libres después de turnos nocturnos
    - Distribución de días libres en la semana
    
    Returns:
        dict: Resultados del análisis de días libres
    """
    from utils.date_utils import get_week_start, get_week_end, date_range
    
    results = {
        "workers_without_weekly_day_off": [],
        "workers_with_days_off_after_night": [],
        "day_off_distribution": defaultdict(int),
        "worker_day_off_details": {}
    }
    
    # Obtener todas las semanas que intersectan con el período
    weeks = []
    current_week_start = get_week_start(schedule.start_date)
    end_date_week_start = get_week_start(schedule.end_date)
    
    while current_week_start <= end_date_week_start:
        week_end = get_week_end(current_week_start)
        
        # Solo incluir semanas que se superpongan con el período
        if not (week_end < schedule.start_date or current_week_start > schedule.end_date):
            effective_start = max(current_week_start, schedule.start_date)
            effective_end = min(week_end, schedule.end_date)
            weeks.append((current_week_start, week_end, effective_start, effective_end))
        
        current_week_start += timedelta(days=7)
    
    # Analizar cada trabajador
    for worker in schedule.get_all_workers():
        worker_id = worker.get_formatted_id()
        days_off_details = []
        after_night_count = 0
        
        # Analizar días libres por semana
        for week_start, week_end, effective_start, effective_end in weeks:
            week_label = f"{effective_start.strftime('%d/%m')} - {effective_end.strftime('%d/%m')}"
            
            # Obtener días libres en esta semana (solo considerar los días en el período)
            days_off_in_week = [d for d in worker.days_off if effective_start <= d <= effective_end]
            
            # Obtener noches trabajadas en la semana
            night_shifts = [(d, s) for d, s in worker.shifts 
                          if s == "Noche" and effective_start <= d <= effective_end]
            
            # Verificar si días libres son después de noche
            for day_off in days_off_in_week:
                # Registrar día de la semana
                results["day_off_distribution"][day_off.strftime("%A")] += 1
                
                # Verificar si es después de turno nocturno
                prev_day = day_off - timedelta(days=1)
                after_night = any(d == prev_day and s == "Noche" for d, s in worker.shifts)
                
                if after_night:
                    after_night_count += 1
                
                days_off_details.append({
                    "week": week_label,
                    "date": day_off.strftime("%Y-%m-%d"),
                    "weekday": day_off.strftime("%A"),
                    "after_night_shift": after_night
                })
            
            # Verificar si no hay días libres en la semana (solo si hay al menos 3 días en el período)
            # Esto evitará contar semanas parciales muy cortas al inicio o fin
            days_in_period = (effective_end - effective_start).days + 1
            
            if days_in_period >= 3 and not days_off_in_week:
                results["workers_without_weekly_day_off"].append({
                    "worker_id": worker_id,
                    "week": week_label,
                    "effective_days": days_in_period
                })
        
        # Registrar si el trabajador tiene días libres después de turnos nocturnos
        if after_night_count > 0:
            results["workers_with_days_off_after_night"].append({
                "worker_id": worker_id,
                "count": after_night_count
            })
        
        # Guardar detalles de días libres para este trabajador
        results["worker_day_off_details"][worker_id] = days_off_details
    
    return results

def analyze_compensation(schedule):
    """
    Analiza la equidad en remuneraciones entre trabajadores.
    
    Returns:
        dict: Resultados del análisis de compensación
    """
    from config import is_colombian_holiday
    
    # Calcular compensación para cada trabajador
    compensations = []
    compensation_details = {}
    
    # Separar por tipo de trabajador
    techs = schedule.get_technologists()
    engs = schedule.get_engineers()
    
    # Analizar tecnólogos
    tech_comps = []
    for tech in techs:
        comp = calculate_worker_compensation(tech, schedule)
        tech_comps.append(comp)
        compensations.append(comp)
        compensation_details[tech.get_formatted_id()] = comp
    
    # Analizar ingenieros
    eng_comps = []
    for eng in engs:
        comp = calculate_worker_compensation(eng, schedule)
        eng_comps.append(comp)
        compensations.append(comp)
        compensation_details[eng.get_formatted_id()] = comp
    
    # Calcular estadísticas
    all_comp_values = [c["total"] for c in compensations]
    tech_comp_values = [c["total"] for c in tech_comps]
    eng_comp_values = [c["total"] for c in eng_comps]
    
    # Calcular desviación estándar, min, max, promedio
    results = {
        "all_workers": {
            "min": min(all_comp_values),
            "max": max(all_comp_values),
            "avg": sum(all_comp_values) / len(all_comp_values),
            "std_dev": calculate_std_dev(all_comp_values),
            "range": max(all_comp_values) - min(all_comp_values),
            "range_percentage": (max(all_comp_values) - min(all_comp_values)) / min(all_comp_values) * 100 if min(all_comp_values) > 0 else 0
        },
        "technologists": {
            "min": min(tech_comp_values),
            "max": max(tech_comp_values),
            "avg": sum(tech_comp_values) / len(tech_comp_values),
            "std_dev": calculate_std_dev(tech_comp_values),
            "range": max(tech_comp_values) - min(tech_comp_values),
            "range_percentage": (max(tech_comp_values) - min(tech_comp_values)) / min(tech_comp_values) * 100 if min(tech_comp_values) > 0 else 0
        },
        "engineers": {
            "min": min(eng_comp_values),
            "max": max(eng_comp_values),
            "avg": sum(eng_comp_values) / len(eng_comp_values),
            "std_dev": calculate_std_dev(eng_comp_values),
            "range": max(eng_comp_values) - min(eng_comp_values),
            "range_percentage": (max(eng_comp_values) - min(eng_comp_values)) / min(eng_comp_values) * 100 if min(eng_comp_values) > 0 else 0
        },
        "details": compensation_details
    }
    
    return results

def calculate_worker_compensation(worker, schedule):
    """
    Calcula compensación detallada para un trabajador.
    
    Returns:
        dict: Detalles de compensación
    """
    from config import is_colombian_holiday
    
    # Inicializar contadores
    regular_count = 0
    night_count = 0
    weekend_day_count = 0
    weekend_night_count = 0
    holiday_day_count = 0
    holiday_night_count = 0
    
    # Registrar cada turno
    for date, shift_type in worker.shifts:
        is_night = (shift_type == "Noche")
        is_weekend = date.weekday() >= 5  # 5=Sábado, 6=Domingo
        is_holiday = is_colombian_holiday(date)
        
        if is_holiday:
            if is_night:
                holiday_night_count += 1
            else:
                holiday_day_count += 1
        elif is_weekend:
            if is_night:
                weekend_night_count += 1
            else:
                weekend_day_count += 1
        else:
            if is_night:
                night_count += 1
            else:
                regular_count += 1
    
    # Calcular compensación según tasas
    regular_comp = regular_count * COMPENSATION_RATES["DIURNO"]
    night_comp = night_count * COMPENSATION_RATES["NOCTURNO"]
    weekend_day_comp = weekend_day_count * COMPENSATION_RATES["FIN_DE_SEMANA_DIURNO"]
    weekend_night_comp = weekend_night_count * COMPENSATION_RATES["FIN_DE_SEMANA_NOCTURNO"]
    
    # Para festivos, usar tasas de fin de semana con 25% adicional
    holiday_day_comp = holiday_day_count * COMPENSATION_RATES["FIN_DE_SEMANA_DIURNO"] * 1.25
    holiday_night_comp = holiday_night_count * COMPENSATION_RATES["FIN_DE_SEMANA_NOCTURNO"] * 1.25
    
    # Calcular total
    total_comp = (regular_comp + night_comp + weekend_day_comp + 
                 weekend_night_comp + holiday_day_comp + holiday_night_comp)
    
    # Crear detalle
    return {
        "worker_id": worker.get_formatted_id(),
        "total_shifts": worker.get_shift_count(),
        "regular": {"count": regular_count, "compensation": regular_comp},
        "night": {"count": night_count, "compensation": night_comp},
        "weekend_day": {"count": weekend_day_count, "compensation": weekend_day_comp},
        "weekend_night": {"count": weekend_night_count, "compensation": weekend_night_comp},
        "holiday_day": {"count": holiday_day_count, "compensation": holiday_day_comp},
        "holiday_night": {"count": holiday_night_count, "compensation": holiday_night_comp},
        "total": total_comp
    }

def analyze_shift_distribution(schedule):
    """
    Analiza la distribución de tipos de turnos por trabajador.
    
    Returns:
        dict: Resultados del análisis de distribución
    """
    worker_distributions = {}
    shift_counts = {"Mañana": 0, "Tarde": 0, "Noche": 0}
    
    # Analizar cada trabajador
    for worker in schedule.get_all_workers():
        worker_id = worker.get_formatted_id()
        
        # Obtener distribución por tipo
        counts = worker.get_shift_types_count()
        worker_distributions[worker_id] = counts
        
        # Actualizar totales
        for shift_type, count in counts.items():
            shift_counts[shift_type] += count
    
    return {
        "per_worker": worker_distributions,
        "totals": shift_counts
    }

def calculate_std_dev(values):
    """Calcula la desviación estándar de una lista de valores."""
    if not values:
        return 0
    
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    return math.sqrt(variance)

def generate_report(results, schedule, output_file):
    """
    Genera un reporte HTML detallado con los resultados del análisis.
    
    Args:
        results: Resultados del análisis
        schedule: Objeto Schedule con el horario
        output_file: Ruta del archivo donde guardar el reporte
    """
    # Generar gráficas
    compensation_chart = generate_compensation_chart(results["compensation_analysis"], schedule)
    shift_distribution_chart = generate_shift_distribution_chart(results["shift_distribution"], schedule)
    days_off_chart = generate_days_off_chart(results["days_off_analysis"])
    
    # Construir HTML
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Análisis Detallado del Horario - {schedule.start_date.strftime('%B %Y')}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
            h1, h2, h3 {{ color: #333; }}
            table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            .warning {{ color: #dc3545; }}
            .success {{ color: #28a745; }}
            .section {{ margin-bottom: 30px; }}
            .chart {{ margin: 20px 0; background-color: #f9f9f9; padding: 10px; border-radius: 5px; }}
            .chart-container {{ display: flex; justify-content: center; }}
            .summary {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
            .metric {{ font-weight: bold; }}
            .percentage {{ color: #6c757d; }}
        </style>
    </head>
    <body>
        <h1>Análisis Detallado del Horario - {schedule.start_date.strftime('%B %Y')}</h1>
        
        <div class="summary">
            <h2>Resumen Ejecutivo</h2>
            <p>Este análisis evalúa el cumplimiento de dos aspectos críticos del horario:</p>
            <ol>
                <li><strong>Días de descanso semanal:</strong> Cada trabajador debe tener al menos un día libre por semana, preferiblemente después de un turno nocturno.</li>
                <li><strong>Equidad en remuneraciones:</strong> Todos los trabajadores deben recibir compensaciones aproximadamente equitativas.</li>
            </ol>
        </div>
        
        <div class="section">
            <h2>1. Análisis de Compensaciones</h2>
            
            <h3>Estadísticas de Equidad</h3>
            <table>
                <tr>
                    <th>Grupo</th>
                    <th>Mínima</th>
                    <th>Máxima</th>
                    <th>Promedio</th>
                    <th>Rango</th>
                    <th>Desviación Estándar</th>
                    <th>Diferencia %</th>
                </tr>
                <tr>
                    <td><strong>Tecnólogos</strong></td>
                    <td>{results['compensation_analysis']['technologists']['min']:.2f}</td>
                    <td>{results['compensation_analysis']['technologists']['max']:.2f}</td>
                    <td>{results['compensation_analysis']['technologists']['avg']:.2f}</td>
                    <td>{results['compensation_analysis']['technologists']['range']:.2f}</td>
                    <td>{results['compensation_analysis']['technologists']['std_dev']:.2f}</td>
                    <td class="{'warning' if results['compensation_analysis']['technologists']['range_percentage'] > 15 else 'success'}">
                        {results['compensation_analysis']['technologists']['range_percentage']:.1f}%
                    </td>
                </tr>
                <tr>
                    <td><strong>Ingenieros</strong></td>
                    <td>{results['compensation_analysis']['engineers']['min']:.2f}</td>
                    <td>{results['compensation_analysis']['engineers']['max']:.2f}</td>
                    <td>{results['compensation_analysis']['engineers']['avg']:.2f}</td>
                    <td>{results['compensation_analysis']['engineers']['range']:.2f}</td>
                    <td>{results['compensation_analysis']['engineers']['std_dev']:.2f}</td>
                    <td class="{'warning' if results['compensation_analysis']['engineers']['range_percentage'] > 15 else 'success'}">
                        {results['compensation_analysis']['engineers']['range_percentage']:.1f}%
                    </td>
                </tr>
            </table>
            
            <div class="chart">
                <h3>Distribución de Compensaciones por Trabajador</h3>
                <div class="chart-container">
                    <img src="{compensation_chart}" alt="Gráfico de compensaciones">
                </div>
            </div>
            
            <h3>Detalle de Compensaciones por Trabajador</h3>
            <table>
                <tr>
                    <th>Trabajador</th>
                    <th>Total Turnos</th>
                    <th>Regulares</th>
                    <th>Nocturnos</th>
                    <th>Fin de Semana</th>
                    <th>Fin de Semana Nocturno</th>
                    <th>Festivos</th>
                    <th>Festivos Nocturno</th>
                    <th>Compensación Total</th>
                </tr>
    """
    
    # Añadir filas de trabajadores ordenados por compensación total
    worker_comps = sorted(results["compensation_analysis"]["details"].items(), 
                        key=lambda x: x[1]["total"], reverse=True)
    
    for worker_id, details in worker_comps:
        html += f"""
                <tr>
                    <td>{worker_id}</td>
                    <td>{details['total_shifts']}</td>
                    <td>{details['regular']['count']}</td>
                    <td>{details['night']['count']}</td>
                    <td>{details['weekend_day']['count']}</td>
                    <td>{details['weekend_night']['count']}</td>
                    <td>{details['holiday_day']['count']}</td>
                    <td>{details['holiday_night']['count']}</td>
                    <td class="metric">{details['total']:.2f}</td>
                </tr>
        """
    
    html += """
            </table>
        </div>
        
        <div class="section">
            <h2>2. Análisis de Días de Descanso</h2>
    """
    
    # Añadir sección de semanas sin día libre
    missing_days_off = results["days_off_analysis"]["workers_without_weekly_day_off"]
    if missing_days_off:
        html += f"""
            <div class="warning">
                <h3>⚠️ Advertencia: Semanas sin Día Libre</h3>
                <p>Se encontraron {len(missing_days_off)} casos donde un trabajador no tiene día libre en una semana:</p>
                <ul>
        """
        
        for entry in missing_days_off:
            html += f"<li>{entry['worker_id']} - Semana {entry['week']}</li>"
        
        html += """
                </ul>
            </div>
        """
    else:
        html += """
            <div class="success">
                <h3>✅ Todos los trabajadores tienen al menos un día libre por semana</h3>
            </div>
        """
    
    # Añadir distribución de días libres
    html += f"""
            <div class="chart">
                <h3>Distribución de Días Libres por Día de la Semana</h3>
                <div class="chart-container">
                    <img src="{days_off_chart}" alt="Distribución de días libres">
                </div>
            </div>
            
            <h3>Días Libres Después de Turno Nocturno</h3>
            <p>
                {len(results["days_off_analysis"]["workers_with_days_off_after_night"])} de {len(schedule.get_all_workers())} 
                trabajadores tienen al menos un día libre después de un turno nocturno.
            </p>
    """
    
    # Añadir distribución de turnos
    html += f"""
        </div>
        
        <div class="section">
            <h2>3. Distribución de Turnos</h2>
            
            <div class="chart">
                <h3>Distribución de Tipos de Turno por Trabajador</h3>
                <div class="chart-container">
                    <img src="{shift_distribution_chart}" alt="Distribución de tipos de turno">
                </div>
            </div>
            
            <h3>Detalle de Distribución por Trabajador</h3>
            <table>
                <tr>
                    <th>Trabajador</th>
                    <th>Turnos Mañana</th>
                    <th>Turnos Tarde</th>
                    <th>Turnos Noche</th>
                    <th>Total Turnos</th>
                </tr>
    """
    
    # Añadir filas de distribución por trabajador
    for worker_id, counts in sorted(results["shift_distribution"]["per_worker"].items()):
        total = sum(counts.values())
        html += f"""
                <tr>
                    <td>{worker_id}</td>
                    <td>{counts['Mañana']} <span class="percentage">({counts['Mañana']/total*100:.1f}%)</span></td>
                    <td>{counts['Tarde']} <span class="percentage">({counts['Tarde']/total*100:.1f}%)</span></td>
                    <td>{counts['Noche']} <span class="percentage">({counts['Noche']/total*100:.1f}%)</span></td>
                    <td class="metric">{total}</td>
                </tr>
        """
    
    html += """
            </table>
        </div>
        
        <div class="section">
            <h2>Conclusiones</h2>
    """
    
    # Generar conclusiones automáticas
    tech_range_pct = results['compensation_analysis']['technologists']['range_percentage']
    missing_days = len(results["days_off_analysis"]["workers_without_weekly_day_off"])
    
    if tech_range_pct <= 10 and missing_days == 0:
        html += """
            <p class="success">✅ <strong>El horario cumple con todas las reglas:</strong></p>
            <ul>
                <li>La diferencia de compensación entre trabajadores es menor al 10%, lo que indica buena equidad.</li>
                <li>Todos los trabajadores tienen al menos un día libre cada semana.</li>
                <li>La distribución de tipos de turno es equilibrada entre trabajadores.</li>
            </ul>
        """
    elif tech_range_pct <= 15 and missing_days <= 2:
        html += f"""
            <p>🟡 <strong>El horario cumple la mayoría de las reglas, con algunas observaciones menores:</strong></p>
            <ul>
                <li>La diferencia de compensación entre tecnólogos es de {tech_range_pct:.1f}%.</li>
                <li>Hay {missing_days} casos donde un trabajador no tiene día libre en una semana.</li>
                <li>Se recomienda revisar estos casos específicos para la próxima generación de horarios.</li>
            </ul>
        """
    else:
        html += f"""
            <p class="warning">⚠️ <strong>El horario presenta algunos problemas que deben revisarse:</strong></p>
            <ul>
                <li>La diferencia de compensación entre tecnólogos es alta: {tech_range_pct:.1f}%.</li>
                <li>Hay {missing_days} casos donde un trabajador no tiene día libre en una semana.</li>
                <li>Se recomienda regenerar el horario ajustando los parámetros de equidad y descanso.</li>
            </ul>
        """
    
    html += """
        </div>
    </body>
    </html>
    """
    
    # Guardar reporte
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)

def generate_compensation_chart(comp_analysis, schedule):
    """Genera un gráfico de compensaciones y lo guarda como imagen."""
    import matplotlib
    matplotlib.use('Agg')  # Para generar gráficos sin interfaz
    
    plt.figure(figsize=(12, 6))
    
    workers = []
    compensations = []
    colors = []
    
    # Preparar datos
    for worker_id, details in comp_analysis["details"].items():
        workers.append(worker_id)
        compensations.append(details["total"])
        # Color azul para tecnólogos, naranja para ingenieros
        colors.append('#1f77b4' if worker_id.startswith('T') else '#ff7f0e')
    
    # Ordenar por compensación
    sorted_data = sorted(zip(workers, compensations, colors), key=lambda x: x[1])
    workers, compensations, colors = zip(*sorted_data)
    
    # Calcular promedio
    avg_comp = comp_analysis["all_workers"]["avg"]
    
    # Crear gráfico
    plt.bar(workers, compensations, color=colors)
    plt.axhline(y=avg_comp, color='r', linestyle='-', label=f'Promedio: {avg_comp:.2f}')
    plt.xlabel('Trabajador')
    plt.ylabel('Compensación Total')
    plt.title('Compensación Total por Trabajador')
    plt.xticks(rotation=45)
    plt.legend()
    plt.tight_layout()
    
    # Guardar y retornar ruta
    chart_path = f"compensation_chart_{schedule.start_date.strftime('%Y%m')}.png"
    plt.savefig(chart_path)
    plt.close()
    
    return chart_path

def generate_shift_distribution_chart(shift_analysis, schedule):
    """Genera un gráfico de distribución de turnos y lo guarda como imagen."""
    import matplotlib
    matplotlib.use('Agg')
    
    plt.figure(figsize=(14, 7))
    
    worker_ids = []
    morning_shifts = []
    afternoon_shifts = []
    night_shifts = []
    
    # Preparar datos
    for worker_id, counts in sorted(shift_analysis["per_worker"].items()):
        worker_ids.append(worker_id)
        morning_shifts.append(counts["Mañana"])
        afternoon_shifts.append(counts["Tarde"])
        night_shifts.append(counts["Noche"])
    
    # Crear gráfico de barras apiladas
    bar_width = 0.6
    plt.bar(worker_ids, morning_shifts, bar_width, label='Mañana', color='#4CAF50')
    plt.bar(worker_ids, afternoon_shifts, bar_width, bottom=morning_shifts, label='Tarde', color='#F44336')
    plt.bar(worker_ids, night_shifts, bar_width, bottom=[m+a for m,a in zip(morning_shifts, afternoon_shifts)], 
            label='Noche', color='#607D8B')
    
    plt.xlabel('Trabajador')
    plt.ylabel('Número de Turnos')
    plt.title('Distribución de Tipos de Turno por Trabajador')
    plt.xticks(rotation=45)
    plt.legend()
    plt.tight_layout()
    
    # Guardar y retornar ruta
    chart_path = f"shift_distribution_{schedule.start_date.strftime('%Y%m')}.png"
    plt.savefig(chart_path)
    plt.close()
    
    return chart_path

def generate_days_off_chart(days_off_analysis):
    """Genera un gráfico de distribución de días libres y lo guarda como imagen."""
    import matplotlib
    matplotlib.use('Agg')
    
    plt.figure(figsize=(10, 6))
    
    # Preparar datos
    weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    counts = [days_off_analysis["day_off_distribution"].get(day, 0) for day in weekdays]
    
    # Traducir días a español para visualización
    weekdays_es = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    
    # Crear gráfico
    bars = plt.bar(weekdays_es, counts)
    
    # Colorear barras de fin de semana
    bars[5].set_color('#ff9800')  # Sábado
    bars[6].set_color('#ff9800')  # Domingo
    
    plt.xlabel('Día de la Semana')
    plt.ylabel('Número de Días Libres')
    plt.title('Distribución de Días Libres por Día de la Semana')
    plt.tight_layout()
    
    # Guardar y retornar ruta
    chart_path = "days_off_distribution.png"
    plt.savefig(chart_path)
    plt.close()
    
    return chart_path