"""
Clase para la gestión del horario completo.
"""

from datetime import timedelta
from config.settings import SHIFT_TYPES, SHIFT_HOURS

class Schedule:
    """
    Representa un horario completo para un período específico.
    
    Attributes:
        start_date (datetime): Fecha de inicio del horario
        end_date (datetime): Fecha de fin del horario
        workers (list): Lista de todos los trabajadores
        days (list): Lista de días con sus turnos y asignaciones
    """
    
    def __init__(self, start_date, end_date, workers):
        self.start_date = start_date
        self.end_date = end_date
        self.workers = workers
        self.days = []
        
        # Inicializar estructura de datos para todos los días
        from utils.date_utils import date_range
        for current_date in date_range(start_date, end_date):
            day_data = {
                "date": current_date,
                "shifts": {
                    shift_type: {
                        "hours": SHIFT_HOURS[shift_type],
                        "technologists": [],
                        "engineer": None
                    } for shift_type in SHIFT_TYPES
                }
            }
            self.days.append(day_data)
    
    def assign_worker(self, worker, date, shift_type):
        """Asigna un trabajador a un turno específico."""
        for day in self.days:
            if day["date"] == date:
                if worker.is_technologist:
                    day["shifts"][shift_type]["technologists"].append(worker.id)
                else:
                    day["shifts"][shift_type]["engineer"] = worker.id
                
                worker.add_shift(date, shift_type)
                return True
        return False
    
    def get_all_workers(self):
        """Retorna todos los trabajadores."""
        return self.workers
    
    def get_technologists(self):
        """Retorna solo los tecnólogos."""
        return [w for w in self.workers if w.is_technologist]
    
    def get_engineers(self):
        """Retorna solo los ingenieros."""
        return [w for w in self.workers if not w.is_technologist]
    
    def get_day(self, date):
        """Retorna la información de un día específico."""
        for day in self.days:
            if day["date"] == date:
                return day
        return None