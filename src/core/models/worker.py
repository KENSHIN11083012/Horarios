"""
Modelo de dominio para trabajadores (Tecnólogos e Ingenieros).
Núcleo del dominio - puro, sin dependencias externas.
"""

from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Optional
from enum import Enum
from dataclasses import dataclass, field


class WorkerType(Enum):
    """Tipos de trabajador disponibles."""
    TECHNOLOGIST = "technologist"
    ENGINEER = "engineer"


class ShiftType(Enum):
    """Tipos de turno disponibles."""
    MORNING = "Mañana"
    AFTERNOON = "Tarde" 
    NIGHT = "Noche"


@dataclass
class Shift:
    """Representa un turno asignado a un trabajador."""
    date: datetime
    shift_type: ShiftType
    compensation: float = 0.0


@dataclass
class Worker:
    """
    Modelo de dominio para un trabajador (tecnólogo o ingeniero).
    
    Responsabilidades:
    - Mantener información del trabajador
    - Gestionar turnos asignados
    - Gestionar días libres
    - Calcular estadísticas personales
    """
    
    id: int
    worker_type: WorkerType
    shifts: List[Shift] = field(default_factory=list)
    days_off: List[datetime] = field(default_factory=list)
    total_earnings: float = 0.0
    
    @property
    def is_technologist(self) -> bool:
        """Indica si el trabajador es tecnólogo."""
        return self.worker_type == WorkerType.TECHNOLOGIST
    
    @property
    def is_engineer(self) -> bool:
        """Indica si el trabajador es ingeniero."""
        return self.worker_type == WorkerType.ENGINEER
    
    @property
    def formatted_id(self) -> str:
        """Retorna el ID formateado con prefijo."""
        prefix = "T" if self.is_technologist else "I"
        return f"{prefix}{self.id}"
    
    def add_shift(self, date: datetime, shift_type: ShiftType, compensation: float = 0.0) -> None:
        """
        Añade un turno al trabajador.
        
        Args:
            date: Fecha del turno
            shift_type: Tipo de turno
            compensation: Compensación por el turno
        """
        shift = Shift(date, shift_type, compensation)
        self.shifts.append(shift)
        self.total_earnings += compensation
    
    def remove_shift(self, date: datetime, shift_type: ShiftType) -> bool:
        """
        Remueve un turno específico del trabajador.
        
        Args:
            date: Fecha del turno
            shift_type: Tipo de turno
            
        Returns:
            bool: True si se removió exitosamente, False si no se encontró
        """
        for i, shift in enumerate(self.shifts):
            if shift.date == date and shift.shift_type == shift_type:
                removed_shift = self.shifts.pop(i)
                self.total_earnings -= removed_shift.compensation
                return True
        return False
    
    def add_day_off(self, date: datetime) -> None:
        """Añade un día libre."""
        if date not in self.days_off:
            self.days_off.append(date)
    
    def remove_day_off(self, date: datetime) -> bool:
        """
        Remueve un día libre.
        
        Returns:
            bool: True si se removió, False si no existía
        """
        if date in self.days_off:
            self.days_off.remove(date)
            return True
        return False
    
    def has_shift_on_date(self, date: datetime) -> bool:
        """Verifica si tiene algún turno en una fecha específica."""
        return any(shift.date.date() == date.date() for shift in self.shifts)
    
    def get_shift_on_date(self, date: datetime) -> Optional[Shift]:
        """Obtiene el turno en una fecha específica si existe."""
        for shift in self.shifts:
            if shift.date.date() == date.date():
                return shift
        return None
    
    def has_day_off(self, date: datetime) -> bool:
        """Verifica si tiene día libre en una fecha específica."""
        return any(day_off.date() == date.date() for day_off in self.days_off)
    
    def get_shifts_by_type(self, shift_type: ShiftType) -> List[Shift]:
        """Obtiene todos los turnos de un tipo específico."""
        return [shift for shift in self.shifts if shift.shift_type == shift_type]
    
    def get_shifts_in_period(self, start_date: datetime, end_date: datetime) -> List[Shift]:
        """Obtiene todos los turnos en un período específico."""
        return [shift for shift in self.shifts 
                if start_date.date() <= shift.date.date() <= end_date.date()]
    
    def get_shift_count(self) -> int:
        """Retorna el número total de turnos asignados."""
        return len(self.shifts)
    
    def get_shift_count_by_type(self) -> Dict[ShiftType, int]:
        """Retorna un diccionario con el conteo por tipo de turno."""
        counts = {shift_type: 0 for shift_type in ShiftType}
        for shift in self.shifts:
            counts[shift.shift_type] += 1
        return counts
    
    def get_total_compensation(self) -> float:
        """Calcula la compensación total de todos los turnos."""
        return sum(shift.compensation for shift in self.shifts)
    
    def get_workload_in_week(self, week_start: datetime) -> List[Shift]:
        """Obtiene la carga de trabajo en una semana específica."""
        week_end = week_start + timedelta(days=6)
        return self.get_shifts_in_period(week_start, week_end)
    
    def get_days_off_in_week(self, week_start: datetime) -> List[datetime]:
        """Obtiene los días libres en una semana específica."""
        week_end = week_start + timedelta(days=6)
        return [day_off for day_off in self.days_off 
                if week_start.date() <= day_off.date() <= week_end.date()]
    
    def can_work_shift(self, date: datetime, shift_type: ShiftType, 
                      constraints_checker=None) -> bool:
        """
        Verifica si el trabajador puede trabajar en un turno específico.
        
        Args:
            date: Fecha del turno
            shift_type: Tipo de turno
            constraints_checker: Verificador de restricciones opcional
            
        Returns:
            bool: True si puede trabajar, False en caso contrario
        """
        # Verificaciones básicas
        if self.has_shift_on_date(date):
            return False
            
        if self.has_day_off(date):
            return False
        
        # Si se proporciona un verificador de restricciones, usarlo
        if constraints_checker:
            return constraints_checker.can_work_shift(self, date, shift_type)
        
        # Verificaciones básicas de restricciones
        return self._basic_constraints_check(date, shift_type)
    
    def _basic_constraints_check(self, date: datetime, shift_type: ShiftType) -> bool:
        """Verificaciones básicas de restricciones sin dependencias externas."""
        # Verificar transición noche a día
        prev_day = date - timedelta(days=1)
        prev_shift = self.get_shift_on_date(prev_day)
        if prev_shift and prev_shift.shift_type == ShiftType.NIGHT and shift_type == ShiftType.MORNING:
            return False
        
        # Verificar turnos consecutivos en el mismo día
        # (Esta verificación sería más compleja en un escenario real)
        
        return True
    
    def calculate_workload_balance_score(self) -> float:
        """
        Calcula un puntaje de balance de carga de trabajo (0-1).
        
        Returns:
            float: Puntaje donde 1.0 = perfectamente balanceado
        """
        shift_counts = self.get_shift_count_by_type()
        count_values = list(shift_counts.values())
        
        if not count_values or all(count == 0 for count in count_values):
            return 1.0  # Sin turnos = perfectamente balanceado
        
        max_count = max(count_values)
        min_count = min(count_values)
        
        if max_count == 0:
            return 1.0
        
        # Calcular balance: 1.0 = perfectamente balanceado, 0.0 = muy desbalanceado
        balance_ratio = min_count / max_count if max_count > 0 else 1.0
        return balance_ratio
    
    def get_recent_shifts(self, reference_date: datetime, days_back: int = 7) -> List[Shift]:
        """
        Obtiene los turnos recientes desde una fecha de referencia.
        
        Args:
            reference_date: Fecha de referencia
            days_back: Número de días hacia atrás a considerar
            
        Returns:
            List[Shift]: Lista de turnos recientes
        """
        start_date = reference_date - timedelta(days=days_back)
        return [shift for shift in self.shifts 
                if start_date.date() <= shift.date.date() < reference_date.date()]
    
    def has_consecutive_days_off(self, min_consecutive: int = 2) -> bool:
        """
        Verifica si tiene días libres consecutivos.
        
        Args:
            min_consecutive: Número mínimo de días consecutivos
            
        Returns:
            bool: True si tiene al menos min_consecutive días libres seguidos
        """
        if len(self.days_off) < min_consecutive:
            return False
        
        # Ordenar días libres
        sorted_days = sorted(self.days_off, key=lambda d: d.date())
        
        consecutive_count = 1
        max_consecutive = 1
        
        for i in range(1, len(sorted_days)):
            if (sorted_days[i].date() - sorted_days[i-1].date()).days == 1:
                consecutive_count += 1
                max_consecutive = max(max_consecutive, consecutive_count)
            else:
                consecutive_count = 1
        
        return max_consecutive >= min_consecutive
    
    def get_statistics(self) -> Dict[str, any]:
        """
        Obtiene estadísticas completas del trabajador.
        
        Returns:
            Dict: Estadísticas del trabajador
        """
        shift_counts = self.get_shift_count_by_type()
        
        return {
            "worker_id": self.formatted_id,
            "worker_type": self.worker_type.value,
            "total_shifts": self.get_shift_count(),
            "shift_distribution": {st.value: count for st, count in shift_counts.items()},
            "total_compensation": self.get_total_compensation(),
            "total_days_off": len(self.days_off),
            "workload_balance_score": self.calculate_workload_balance_score(),
            "has_weekend_rest": self.has_consecutive_days_off(2),
            "average_compensation_per_shift": (
                self.get_total_compensation() / self.get_shift_count() 
                if self.get_shift_count() > 0 else 0.0
            )
        }
    
    def __str__(self) -> str:
        """Representación en string del trabajador."""
        return f"{self.formatted_id} ({self.worker_type.value}) - {self.get_shift_count()} turnos"
    
    def __repr__(self) -> str:
        """Representación para debugging."""
        return (f"Worker(id={self.id}, type={self.worker_type.value}, "
                f"shifts={len(self.shifts)}, days_off={len(self.days_off)})")
    
    def __eq__(self, other) -> bool:
        """Comparación de igualdad basada en ID y tipo."""
        if not isinstance(other, Worker):
            return False
        return self.id == other.id and self.worker_type == other.worker_type
    
    def __hash__(self) -> int:
        """Hash basado en ID y tipo para uso en sets y diccionarios."""
        return hash((self.id, self.worker_type))