"""
Clase Worker para representar tecnólogos e ingenieros.
"""

from datetime import datetime, timedelta
from config.settings import SHIFT_TYPES, NIGHT_SHIFT_RATE, HOLIDAY_RATE, SUNDAY_RATE
from config import is_colombian_holiday

class Worker:
    """
    Representa un trabajador (tecnólogo o ingeniero).
    
    Attributes:
        id (int): Identificador numérico del trabajador
        is_technologist (bool): Indica si es tecnólogo (True) o ingeniero (False)
        prefix (str): Prefijo para mostrar (T para tecnólogos, I para ingenieros)
        shifts (list): Lista de turnos asignados
        earnings (float): Ganancias acumuladas
        days_off (list): Días de descanso asignados
    """
    
    def __init__(self, id, is_technologist=True):
        self.id = id
        self.is_technologist = is_technologist
        self.prefix = "T" if is_technologist else "I"
        self.shifts = []  # Lista de tuplas (fecha, tipo_turno)
        self.earnings = 0.0
        self.days_off = []  # Días de descanso
    
    def can_work_shift(self, date, shift_type):
        """Verifica si el trabajador puede trabajar en un turno específico."""
        from core.constraints import check_consecutive_shifts, check_night_to_day_transition, check_adequate_rest
        
        # Verificar si es día de descanso
        if date in self.days_off:
            return False
        
        # Regla 1: No turnos consecutivos
        if check_consecutive_shifts(self, date, shift_type):
            return False
        
        # Regla 2: No transición de noche a día
        if check_night_to_day_transition(self, date, shift_type):
            return False
        
        # Regla 3: Períodos de descanso adecuados
        if not check_adequate_rest(self, date, shift_type):
            return False
        
        return True
    
    def add_shift(self, date, shift_type):
        """Añade un turno y actualiza las ganancias."""
        self.shifts.append((date, shift_type))
        
        # Calcular compensación según tipo de turno y fecha
        from utils.compensation import calculate_compensation
        self.earnings += calculate_compensation(date, shift_type)
    
    def add_day_off(self, date):
        """Añade un día de descanso."""
        if date not in self.days_off:
            self.days_off.append(date)
    
    def worked_night_shift_on(self, date):
        """Verifica si trabajó turno nocturno en una fecha específica."""
        return any(d == date and s == "Noche" for d, s in self.shifts)
    
    def get_shift_count(self):
        """Retorna el número total de turnos asignados."""
        return len(self.shifts)
    
    def get_shift_types_count(self):
        """Retorna un diccionario con el conteo por tipo de turno."""
        counts = {shift_type: 0 for shift_type in SHIFT_TYPES}
        for _, shift_type in self.shifts:
            counts[shift_type] += 1
        return counts
    
    def get_shifts_in_week(self, week_start):
        """Retorna turnos asignados en una semana específica."""
        from utils.date_utils import get_week_end
        week_end = get_week_end(week_start)
        return [(d, s) for d, s in self.shifts if week_start <= d <= week_end]
    
    def get_days_off_in_week(self, week_start):
        """Retorna días libres en una semana específica."""
        from utils.date_utils import get_week_end
        week_end = get_week_end(week_start)
        return [d for d in self.days_off if week_start <= d <= week_end]
    
    def get_formatted_id(self):
        """Retorna el ID formateado con prefijo."""
        return f"{self.prefix}{self.id}"