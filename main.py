import sys
import random
from datetime import datetime
import calendar
from core.worker import Worker
from core.schedule import Schedule
from algorithms.generator import generate_schedule
from utils.exporter import export_to_csv
from config.settings import NUM_TECHNOLOGISTS, NUM_ENGINEERS

def main():
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
    schedule = generate_schedule(start_date, end_date, technologists, engineers)
    
    # Exportar a CSV
    output_filename = f"horario_{start_date.strftime('%m_%Y')}.csv"
    export_to_csv(schedule, output_filename)
    print(f"\nHorario generado y guardado en: {output_filename}")
    
    # Mostrar estadísticas básicas
    print("\n=== ESTADÍSTICAS ===")
    print_worker_stats(technologists, "TECNÓLOGOS")
    print_worker_stats(engineers, "INGENIEROS")

def print_worker_stats(workers, title):
    """Muestra estadísticas simples de los trabajadores."""
    print(f"\n{title}:")
    for worker in workers:
        shifts = worker.get_shift_types_count()
        print(f"{worker.get_formatted_id()}: {worker.get_shift_count()} turnos " +
              f"(M:{shifts['Mañana']}, T:{shifts['Tarde']}, N:{shifts['Noche']}), " +
              f"Ganancias: {worker.earnings:.2f}")

if __name__ == "__main__":
    main()