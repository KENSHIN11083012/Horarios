"""
Exportación de horarios a diferentes formatos.
"""

import csv
from config.settings import SHIFT_TYPES

def export_to_csv(schedule, output_filename):
    """
    Exporta un horario a un archivo CSV estándar.
    
    Args:
        schedule: Objeto Schedule con el horario
        output_filename: Nombre del archivo CSV de salida
    """
    with open(output_filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        
        # Escribir encabezados
        writer.writerow([
            "Fecha", "Turno", "Horario", "Tecnólogos asignados", "Ingeniero asignado", "Notas"
        ])
        
        # Escribir datos
        for day in schedule.days:
            date_str = day["date"].strftime("%d de %B de %Y")
            
            for shift_type in SHIFT_TYPES:
                shift = day["shifts"][shift_type]
                
                # Formatear tecnólogos asignados
                tech_str = " ".join([f"T{t}" for t in shift["technologists"]])
                
                # Formatear ingeniero asignado
                eng_str = f"I{shift['engineer']}" if shift['engineer'] is not None else ""
                
                # Escribir fila
                writer.writerow([
                    date_str,
                    shift_type,
                    shift["hours"],
                    tech_str,
                    eng_str,
                    "Turnos"  # Notas estándar
                ])
    
    return output_filename

def export_to_notion_csv(schedule, output_filename):
    """
    Exporta un horario a un archivo CSV compatible con Notion.
    
    Args:
        schedule: Objeto Schedule con el horario
        output_filename: Nombre del archivo CSV de salida
    """
    with open(output_filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        
        # Escribir encabezados
        writer.writerow([
            "Fecha", "Turno", "Horario", "Tecnólogos asignados", "Ingeniero asignado", "Notas"
        ])
        
        # Escribir datos
        for day in schedule.days:
            # Formato de fecha para Notion (YYYY-MM-DD)
            date_str = day["date"].strftime("%Y-%m-%d")
            
            for shift_type in SHIFT_TYPES:
                shift = day["shifts"][shift_type]
                
                # Formatear tecnólogos como multi-select para Notion
                # Cada ID debe estar en su propia celda separada por comas
                techs = shift["technologists"]
                tech_str = ", ".join([f"T{t}" for t in techs])
                
                # Formato de ingeniero
                eng_str = f"I{shift['engineer']}" if shift['engineer'] is not None else ""
                
                # Escribir fila
                writer.writerow([
                    date_str,  # Fecha en formato YYYY-MM-DD para Notion
                    shift_type,
                    shift["hours"],
                    tech_str,  # Tecnólogos separados por comas
                    eng_str,
                    "Turnos"
                ])
    
    return output_filename