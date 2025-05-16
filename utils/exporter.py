"""
Exportación de horarios a diferentes formatos.
"""

import csv
from config.settings import SHIFT_TYPES
from utils.date_utils import format_date

def export_to_csv(schedule, output_filename):
    """
    Exporta un horario a un archivo CSV.
    
    Args:
        schedule: Objeto Schedule con el horario
        output_filename: Nombre del archivo CSV de salida
        
    Returns:
        str: Ruta del archivo generado
    """
    with open(output_filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        
        # Escribir encabezados
        writer.writerow([
            "Fecha", "Turno", "Horario", "Tecnólogos asignados", 
            "Ingeniero asignado", "Notas"
        ])
        
        # Escribir datos
        for day in schedule.days:
            date_str = format_date(day["date"])
            
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