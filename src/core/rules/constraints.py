"""
Implementaciones concretas de restricciones de dominio.

Este módulo contiene todas las reglas de restricción específicas
que deben cumplirse en la asignación de turnos.
"""

from datetime import datetime, timedelta
from typing import List, Tuple
from ..models import Worker, ShiftType
from .interfaces import ConstraintRule


class AdequateRestConstraint(ConstraintRule):
    """
    Restricción de descanso adecuado entre turnos.
    
    Asegura que haya al menos 2 espacios de turno entre asignaciones
    para permitir descanso adecuado.
    """
    
    @property
    def name(self) -> str:
        return "adequate_rest"
    
    @property
    def description(self) -> str:
        return "Verifica que haya descanso adecuado (mínimo 2 turnos) entre asignaciones"
    
    def can_assign(self, worker: Worker, date: datetime, shift_type: ShiftType) -> bool:
        """
        Verifica que haya descanso adecuado entre el nuevo turno y los existentes.
        
        Utiliza un sistema de posiciones temporales donde cada día tiene 3 espacios
        (Mañana=0, Tarde=1, Noche=2) y requiere al menos 2 espacios libres entre turnos.
        """
        shift_indices = {"Mañana": 0, "Tarde": 1, "Noche": 2}
        
        # Calcular posición temporal del nuevo turno
        reference_date = datetime(2025, 1, 1)  # Fecha de referencia fija
        current_date_idx = (date - reference_date).days
        current_shift_idx = shift_indices[shift_type.value]
        new_pos = current_date_idx * 3 + current_shift_idx
        
        # Verificar contra todos los turnos existentes
        for work_date, work_shift in worker.shifts:
            date_idx = (work_date - reference_date).days
            shift_idx = shift_indices[work_shift]
            existing_pos = date_idx * 3 + shift_idx
            
            # Calcular diferencia temporal
            diff = abs(new_pos - existing_pos)
            
            # Si la diferencia es 1 o 2 espacios, no hay descanso adecuado
            if 0 < diff <= 2:
                return False
        
        return True
    
    def get_violation_message(self, worker: Worker, date: datetime, shift_type: ShiftType) -> str:
        return f"{worker.get_formatted_id()} no tiene descanso adecuado para {date.strftime('%Y-%m-%d')} {shift_type.value}"


class RelaxedRestConstraint(ConstraintRule):
    """
    Restricción de descanso relajada para casos críticos.
    
    Versión más permisiva que permite menos descanso (mínimo 1 turno)
    para situaciones donde la cobertura es crítica.
    """
    
    @property
    def name(self) -> str:
        return "relaxed_rest"
    
    @property
    def description(self) -> str:
        return "Verifica descanso mínimo relajado (mínimo 1 turno) para casos críticos"
    
    def can_assign(self, worker: Worker, date: datetime, shift_type: ShiftType) -> bool:
        """
        Verifica descanso mínimo relajado - solo rechaza turnos exactamente consecutivos.
        """
        shift_indices = {"Mañana": 0, "Tarde": 1, "Noche": 2}
        
        reference_date = datetime(2025, 1, 1)
        current_date_idx = (date - reference_date).days
        current_shift_idx = shift_indices[shift_type.value]
        new_pos = current_date_idx * 3 + current_shift_idx
        
        for work_date, work_shift in worker.shifts:
            date_idx = (work_date - reference_date).days
            shift_idx = shift_indices[work_shift]
            existing_pos = date_idx * 3 + shift_idx
            
            diff = abs(new_pos - existing_pos)
            
            # Solo rechazar turnos exactamente consecutivos (diferencia de 1)
            if diff == 1:
                return False
        
        return True
    
    def get_violation_message(self, worker: Worker, date: datetime, shift_type: ShiftType) -> str:
        return f"{worker.get_formatted_id()} tiene turnos consecutivos con {date.strftime('%Y-%m-%d')} {shift_type.value}"


class NightToDayTransitionConstraint(ConstraintRule):
    """
    Restricción que previene la transición directa de turno nocturno a matutino.
    
    Evita que un trabajador tenga turno de noche seguido de turno de mañana
    al día siguiente, lo cual sería físicamente demandante.
    """
    
    @property
    def name(self) -> str:
        return "night_to_day_transition"
    
    @property
    def description(self) -> str:
        return "Previene transición directa de turno nocturno a matutino al día siguiente"
    
    def can_assign(self, worker: Worker, date: datetime, shift_type: ShiftType) -> bool:
        """
        Verifica si la asignación crearía una transición noche-día.
        """
        # Solo aplica para turnos de mañana
        if shift_type != ShiftType.MORNING:
            return True
        
        # Verificar si trabajó turno nocturno el día anterior
        prev_date = date - timedelta(days=1)
        return not any(d == prev_date and s == "Noche" for d, s in worker.shifts)
    
    def get_violation_message(self, worker: Worker, date: datetime, shift_type: ShiftType) -> str:
        prev_date = date - timedelta(days=1)
        return (f"{worker.get_formatted_id()} tiene transición noche a día: "
               f"{prev_date.strftime('%Y-%m-%d')} Noche -> {date.strftime('%Y-%m-%d')} {shift_type.value}")


class ConsecutiveShiftsConstraint(ConstraintRule):
    """
    Restricción que previene turnos consecutivos en el mismo día.
    
    Evita que un trabajador tenga múltiples turnos consecutivos
    en el mismo día (ej: Mañana y Tarde).
    """
    
    @property
    def name(self) -> str:
        return "consecutive_shifts_same_day"
    
    @property
    def description(self) -> str:
        return "Previene turnos consecutivos en el mismo día"
    
    def can_assign(self, worker: Worker, date: datetime, shift_type: ShiftType) -> bool:
        """
        Verifica si la asignación crearía turnos consecutivos el mismo día.
        """
        shift_indices = {"Mañana": 0, "Tarde": 1, "Noche": 2}
        current_idx = shift_indices[shift_type.value]
        
        # Verificar otros turnos en el mismo día
        for work_date, work_shift in worker.shifts:
            if work_date == date:
                existing_idx = shift_indices[work_shift]
                # Si la diferencia es exactamente 1, son consecutivos
                if abs(current_idx - existing_idx) == 1:
                    return False
        
        return True
    
    def get_violation_message(self, worker: Worker, date: datetime, shift_type: ShiftType) -> str:
        existing_shifts = [s for d, s in worker.shifts if d == date]
        return (f"{worker.get_formatted_id()} tiene turnos consecutivos el "
               f"{date.strftime('%Y-%m-%d')}: {shift_type.value} con {existing_shifts}")


class DayOffRespectConstraint(ConstraintRule):
    """
    Restricción que respeta los días libres asignados.
    
    Evita asignar turnos en días que han sido designados
    como días libres para el trabajador.
    """
    
    @property
    def name(self) -> str:
        return "day_off_respect"
    
    @property
    def description(self) -> str:
        return "Respeta los días libres asignados a los trabajadores"
    
    def can_assign(self, worker: Worker, date: datetime, shift_type: ShiftType) -> bool:
        """
        Verifica que la fecha no sea un día libre del trabajador.
        """
        return not worker.has_day_off_on_date(date)
    
    def get_violation_message(self, worker: Worker, date: datetime, shift_type: ShiftType) -> str:
        return f"{worker.get_formatted_id()} tiene día libre el {date.strftime('%Y-%m-%d')}"


class SingleShiftPerDayConstraint(ConstraintRule):
    """
    Restricción que limita a un turno por trabajador por día.
    
    Asegura que ningún trabajador tenga múltiples turnos
    asignados en el mismo día.
    """
    
    @property
    def name(self) -> str:
        return "single_shift_per_day"
    
    @property
    def description(self) -> str:
        return "Limita a un turno por trabajador por día"
    
    def can_assign(self, worker: Worker, date: datetime, shift_type: ShiftType) -> bool:
        """
        Verifica que el trabajador no tenga ya un turno ese día.
        """
        return not worker.has_shift_on_date(date)
    
    def get_violation_message(self, worker: Worker, date: datetime, shift_type: ShiftType) -> str:
        existing_shift = worker.get_shift_on_date(date)
        return (f"{worker.get_formatted_id()} ya tiene turno {existing_shift} "
               f"el {date.strftime('%Y-%m-%d')}")


class MaxConsecutiveDaysConstraint(ConstraintRule):
    """
    Restricción que limita días consecutivos de trabajo.
    
    Evita que un trabajador tenga demasiados días consecutivos
    de trabajo sin descanso.
    """
    
    def __init__(self, max_consecutive_days: int = 5):
        """
        Inicializa la restricción con el límite de días consecutivos.
        
        Args:
            max_consecutive_days: Máximo número de días consecutivos permitidos
        """
        self.max_consecutive_days = max_consecutive_days
    
    @property
    def name(self) -> str:
        return f"max_consecutive_days_{self.max_consecutive_days}"
    
    @property
    def description(self) -> str:
        return f"Limita a máximo {self.max_consecutive_days} días consecutivos de trabajo"
    
    def can_assign(self, worker: Worker, date: datetime, shift_type: ShiftType) -> bool:
        """
        Verifica que asignar este turno no exceda el límite de días consecutivos.
        """
        # Obtener fechas de trabajo ordenadas
        work_dates = sorted(set(d for d, _ in worker.shifts))
        
        # Simular la nueva asignación
        if date not in work_dates:
            work_dates.append(date)
            work_dates.sort()
        
        # Encontrar secuencias consecutivas
        if not work_dates:
            return True
        
        consecutive_count = 1
        max_consecutive = 1
        
        for i in range(1, len(work_dates)):
            if (work_dates[i] - work_dates[i-1]).days == 1:
                consecutive_count += 1
                max_consecutive = max(max_consecutive, consecutive_count)
            else:
                consecutive_count = 1
        
        return max_consecutive <= self.max_consecutive_days
    
    def get_violation_message(self, worker: Worker, date: datetime, shift_type: ShiftType) -> str:
        return (f"{worker.get_formatted_id()} excedería {self.max_consecutive_days} "
               f"días consecutivos incluyendo {date.strftime('%Y-%m-%d')}")


class WorkloadBalanceConstraint(ConstraintRule):
    """
    Restricción suave que considera el balance de carga de trabajo.
    
    No es una restricción absoluta, sino que evalúa si asignar
    un turno crearía un desequilibrio significativo de carga.
    """
    
    def __init__(self, max_imbalance_percentage: float = 50.0):
        """
        Inicializa la restricción con el umbral de desequilibrio.
        
        Args:
            max_imbalance_percentage: Máximo porcentaje de desequilibrio permitido
        """
        self.max_imbalance_percentage = max_imbalance_percentage
    
    @property
    def name(self) -> str:
        return f"workload_balance_{self.max_imbalance_percentage}"
    
    @property
    def description(self) -> str:
        return f"Mantiene balance de carga dentro del {self.max_imbalance_percentage}%"
    
    def can_assign(self, worker: Worker, date: datetime, shift_type: ShiftType) -> bool:
        """
        Verifica que la asignación no cree un desequilibrio excesivo.
        
        Esta es una restricción suave - en casos críticos puede ser ignorada.
        """
        # Para implementación completa necesitaríamos acceso a todos los trabajadores
        # del mismo tipo para comparar cargas. Por ahora, permite todas las asignaciones.
        # TODO: Implementar lógica completa cuando se tenga acceso al contexto completo
        return True
    
    def get_violation_message(self, worker: Worker, date: datetime, shift_type: ShiftType) -> str:
        return (f"{worker.get_formatted_id()} tendría desequilibrio de carga excesivo "
               f"con {date.strftime('%Y-%m-%d')} {shift_type.value}")


class ShiftTypeBalanceConstraint(ConstraintRule):
    """
    Restricción que promueve balance entre tipos de turno.
    
    Evalúa si un trabajador está siendo asignado desproporcionalmente
    a un tipo específico de turno.
    """
    
    def __init__(self, max_type_imbalance: int = 6):
        """
        Inicializa la restricción con el umbral de desequilibrio por tipo.
        
        Args:
            max_type_imbalance: Máxima diferencia permitida entre tipos de turno
        """
        self.max_type_imbalance = max_type_imbalance
    
    @property
    def name(self) -> str:
        return f"shift_type_balance_{self.max_type_imbalance}"
    
    @property
    def description(self) -> str:
        return f"Mantiene balance entre tipos de turno (máx diferencia: {self.max_type_imbalance})"
    
    def can_assign(self, worker: Worker, date: datetime, shift_type: ShiftType) -> bool:
        """
        Verifica que asignar este turno no cree desequilibrio excesivo de tipos.
        """
        shift_counts = worker.get_shift_types_count()
        
        # Simular la nueva asignación
        shift_counts[shift_type.value] = shift_counts.get(shift_type.value, 0) + 1
        
        if not shift_counts:
            return True
        
        max_count = max(shift_counts.values())
        min_count = min(shift_counts.values())
        
        return (max_count - min_count) <= self.max_type_imbalance
    
    def get_violation_message(self, worker: Worker, date: datetime, shift_type: ShiftType) -> str:
        shift_counts = worker.get_shift_types_count()
        return (f"{worker.get_formatted_id()} tendría desequilibrio de tipos de turno "
               f"excesivo con {shift_type.value} el {date.strftime('%Y-%m-%d')} "
               f"(actual: {shift_counts})")


# Lista de restricciones estándar que se aplican por defecto
DEFAULT_CONSTRAINTS = [
    AdequateRestConstraint(),
    NightToDayTransitionConstraint(),
    ConsecutiveShiftsConstraint(),
    DayOffRespectConstraint(),
    SingleShiftPerDayConstraint(),
    MaxConsecutiveDaysConstraint(max_consecutive_days=5),
    ShiftTypeBalanceConstraint(max_type_imbalance=6)
]

# Lista de restricciones relajadas para casos críticos
RELAXED_CONSTRAINTS = [
    RelaxedRestConstraint(),
    NightToDayTransitionConstraint(),  # Esta sigue siendo crítica
    DayOffRespectConstraint(),  # Esta también sigue siendo crítica
    SingleShiftPerDayConstraint(),  # Esta también es absoluta
    MaxConsecutiveDaysConstraint(max_consecutive_days=7),  # Más permisiva
    ShiftTypeBalanceConstraint(max_type_imbalance=8)  # Más permisiva
]