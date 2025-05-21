"""
Módulo para la visualización del horario en formato HTML.
"""
from datetime import datetime, timedelta

def generate_html_visualization(schedule, output_filename):
    """
    Genera una visualización HTML del horario con colores específicos para cada turno.
    
    Args:
        schedule: Objeto Schedule con el horario
        output_filename: Nombre del archivo HTML de salida
    """
    from config.settings import SHIFT_TYPES
    
    # Definir colores para cada turno
    shift_colors = {
        "Mañana": "#4CAF50",  # Verde
        "Tarde": "#F44336",   # Rojo
        "Noche": "#607D8B"    # Gris
    }
    
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Horario de Turnos</title>
        <style>
            body { 
                font-family: Arial, sans-serif; 
                margin: 20px; 
                background-color: #f5f5f5;
            }
            h1, h2 { 
                color: #333; 
                text-align: center;
            }
            table { 
                border-collapse: collapse; 
                width: 100%; 
                margin-bottom: 30px; 
                background-color: white;
                box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            }
            th, td { 
                border: 1px solid #ddd; 
                padding: 12px 8px; 
                text-align: center; 
            }
            th { 
                background-color: #f2f2f2; 
                font-weight: bold;
            }
            .morning { 
                background-color: #4CAF50; 
                color: white; 
            }
            .afternoon { 
                background-color: #F44336; 
                color: white; 
            }
            .night { 
                background-color: #607D8B; 
                color: white; 
            }
            .tech-tag { 
                display: inline-block;
                padding: 3px 8px;
                margin: 2px;
                border-radius: 4px;
                background-color: #2196F3;
                color: white;
                font-weight: normal;
            }
            .eng-tag {
                display: inline-block;
                padding: 3px 8px;
                margin: 2px;
                border-radius: 4px;
                background-color: #FF9800;
                color: white;
                font-weight: normal;
            }
            .section {
                margin-bottom: 40px;
            }
            .stat-table td:last-child, .stat-table th:last-child {
                font-weight: bold;
            }
            .date-column {
                min-width: 120px;
                font-weight: bold;
            }
            .header-row {
                position: sticky;
                top: 0;
                background-color: #f2f2f2;
                z-index: 10;
            }
        </style>
    </head>
    <body>
        <h1>Horario de Turnos</h1>
        
        <div class="section">
            <h2>Programación Detallada</h2>
            <table>
                <tr class="header-row">
                    <th>Fecha</th>
                    <th>Turno</th>
                    <th>Horario</th>
                    <th>Tecnólogos</th>
                    <th>Ingeniero</th>
                </tr>
    """
    
    # Agrupar por fecha para mejorar visualización
    date_groups = {}
    for day in schedule.days:
        date_str = day["date"].strftime("%d/%m/%Y")
        if date_str not in date_groups:
            date_groups[date_str] = []
        date_groups[date_str].append(day)
    
    # Agregar filas de datos
    for date_str, days in sorted(date_groups.items()):
        for day in days:
            formatted_date = day["date"].strftime("%d de %B")
            # Añadir nombre de día de la semana
            day_name = day["date"].strftime("%A")
            is_weekend = day["date"].weekday() >= 5  # 5=Sábado, 6=Domingo
            
            # Traducir nombre del día a español
            day_names_es = {
                "Monday": "Lunes",
                "Tuesday": "Martes",
                "Wednesday": "Miércoles",
                "Thursday": "Jueves",
                "Friday": "Viernes",
                "Saturday": "Sábado",
                "Sunday": "Domingo"
            }
            day_name_es = day_names_es.get(day_name, day_name)
            
            # Formato final de fecha
            formatted_date = f"{formatted_date} ({day_name_es})"
            
            # Resaltar fin de semana
            date_style = "font-weight: bold; color: #E91E63;" if is_weekend else ""
            
            for shift_type in SHIFT_TYPES:
                shift = day["shifts"][shift_type]
                
                # Determinar clase CSS según tipo de turno
                css_class = ""
                if shift_type == "Mañana":
                    css_class = "morning"
                elif shift_type == "Tarde":
                    css_class = "afternoon"
                elif shift_type == "Noche":
                    css_class = "night"
                
                # Tecnólogos con formato de etiquetas
                tech_tags = ""
                for tech_id in shift["technologists"]:
                    tech_tags += f'<span class="tech-tag">T{tech_id}</span> '
                
                # Ingeniero con formato de etiqueta
                eng_tag = ""
                if shift["engineer"] is not None:
                    eng_tag = f'<span class="eng-tag">I{shift["engineer"]}</span>'
                
                # Agregar fila
                html += f"""
                <tr class="{css_class}">
                    <td class="date-column" style="{date_style}">{formatted_date}</td>
                    <td>{shift_type}</td>
                    <td>{shift["hours"]}</td>
                    <td>{tech_tags}</td>
                    <td>{eng_tag}</td>
                </tr>
                """
    
    # Agregar sección de estadísticas
    html += """
        </table>
        </div>
        
        <div class="section">
            <h2>Estadísticas por Trabajador</h2>
            <table class="stat-table">
                <tr class="header-row">
                    <th>ID</th>
                    <th>Turnos Mañana</th>
                    <th>Turnos Tarde</th>
                    <th>Turnos Noche</th>
                    <th>Turnos Totales</th>
                    <th>Compensación</th>
                </tr>
    """
    
    # Agregar estadísticas de trabajadores
    # Primero tecnólogos
    for worker in sorted(schedule.get_technologists(), key=lambda w: w.id):
        shift_counts = worker.get_shift_types_count()
        worker_id = worker.get_formatted_id()
        
        html += f"""
        <tr>
            <td><span class="tech-tag">{worker_id}</span></td>
            <td>{shift_counts["Mañana"]}</td>
            <td>{shift_counts["Tarde"]}</td>
            <td>{shift_counts["Noche"]}</td>
            <td>{worker.get_shift_count()}</td>
            <td>{worker.earnings:.2f}</td>
        </tr>
        """
    
    # Luego ingenieros
    for worker in sorted(schedule.get_engineers(), key=lambda w: w.id):
        shift_counts = worker.get_shift_types_count()
        worker_id = worker.get_formatted_id()
        
        html += f"""
        <tr>
            <td><span class="eng-tag">{worker_id}</span></td>
            <td>{shift_counts["Mañana"]}</td>
            <td>{shift_counts["Tarde"]}</td>
            <td>{shift_counts["Noche"]}</td>
            <td>{worker.get_shift_count()}</td>
            <td>{worker.earnings:.2f}</td>
        </tr>
        """
    
    # Resumen de turnos totales
    total_morning = sum(w.get_shift_types_count()["Mañana"] for w in schedule.get_all_workers())
    total_afternoon = sum(w.get_shift_types_count()["Tarde"] for w in schedule.get_all_workers())
    total_night = sum(w.get_shift_types_count()["Noche"] for w in schedule.get_all_workers())
    total_shifts = total_morning + total_afternoon + total_night
    
    html += f"""
        <tr style="font-weight: bold; background-color: #f9f9f9;">
            <td>TOTALES</td>
            <td>{total_morning}</td>
            <td>{total_afternoon}</td>
            <td>{total_night}</td>
            <td>{total_shifts}</td>
            <td>-</td>
        </tr>
    """
    
    # Cerrar HTML
    html += """
            </table>
        </div>
        
        <footer style="text-align: center; margin-top: 30px; color: #777; font-size: 12px;">
            <p>Generado el """ + datetime.now().strftime("%d/%m/%Y %H:%M:%S") + """</p>
        </footer>
    </body>
    </html>
    """
    
    # Escribir a archivo
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(html)
    
    return output_filename