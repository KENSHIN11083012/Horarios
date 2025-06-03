"""
Schedule model - Dominio puro para representar horarios.

Este módulo contiene la lógica de dominio pura para horarios,
sin dependencias externas ni lógica de infraestructura.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass
from .worker import Worker, WorkerType


@dataclass
class ShiftAssignment:
    """Representa la asignación de personal a un turno específico."""
    technologist_ids: List[int]
    engineer_id: Optional[int]
    
    def __post_init__(self):
        """Validación post-inicialización."""
        if not isinstance(self.technologist_ids, list):
            raise ValueError("technologist_ids debe ser una lista")
        if self.engineer_id is not None and not isinstance(self.engineer_id, int):
            raise ValueError("engineer_id debe ser un entero o None")


@dataclass
class DaySchedule:
    """Representa un día completo con todos sus turnos."""
    date: datetime
    shifts: Dict[str, ShiftAssignment]
    
    def __post_init__(self):
        """Validación post-inicialización."""
        if not isinstance(self.date, datetime):
            raise ValueError("date debe ser un objeto datetime")
        if not isinstance(self.shifts, dict):
            raise ValueError("shifts debe ser un diccionario")


class Schedule:
    """
    Representa un horario completo para un período específico.
    
    Esta clase maneja la estructura de datos principal para el horario,
    incluyendo todos los días del período, los turnos disponibles y
    las asignaciones de trabajadores a cada turno.
    
    Attributes:
        start_date: Fecha de inicio del período del horario
        end_date: Fecha de fin del período del horario
        workers: Lista de todos los trabajadores disponibles
        days: Lista de días con sus turnos y asignaciones
    """
    
    def __init__(self, start_date: datetime, end_date: datetime, workers: List[Worker]):
        """
        Inicializa un nuevo horario para el período especificado.
        
        Args:
            start_date: Fecha de inicio del período
            end_date: Fecha de fin del período
            workers: Lista de objetos Worker (tecnólogos e ingenieros)
            
        Raises:
            ValueError: Si las fechas son inválidas o si workers está vacío
        """
        self._validate_dates(start_date, end_date)
        self._validate_workers(workers)
        
        self.start_date = start_date
        self.end_date = end_date
        self.workers = workers.copy()  # Copia defensiva
        self.days: List[DaySchedule] = []
        
        # Inicializar estructura de días
        self._initialize_days()
        
        # Crear caché de días para acceso rápido O(1)
        self._day_cache: Dict[datetime, DaySchedule] = {
            day.date: day for day in self.days
        }
    
    def _validate_dates(self, start_date: datetime, end_date: datetime):
        """Valida que las fechas sean correctas."""
        if not isinstance(start_date, datetime) or not isinstance(end_date, datetime):
            raise ValueError("start_date y end_date deben ser objetos datetime")
        if start_date > end_date:
            raise ValueError("start_date debe ser anterior o igual a end_date")
    
    def _validate_workers(self, workers: List[Worker]):
        """Valida la lista de trabajadores."""
        if not workers:
            raise ValueError("Debe proporcionar al menos un trabajador")
        if not all(isinstance(w, Worker) for w in workers):
            raise ValueError("Todos los elementos deben ser instancias de Worker")
        
        # Verificar IDs únicos por tipo
        tech_ids = [w.id for w in workers if w.is_technologist]
        eng_ids = [w.id for w in workers if w.is_engineer]
        
        if len(tech_ids) != len(set(tech_ids)):
            raise ValueError("IDs de tecnólogos duplicados")
        if len(eng_ids) != len(set(eng_ids)):
            raise ValueError("IDs de ingenieros duplicados")
    
    def _initialize_days(self):
        """Inicializa la estructura de días del horario."""
        from ...infrastructure.config.constants import SHIFT_TYPES
        
        current_date = self.start_date
        while current_date <= self.end_date:
            shifts = {
                shift_type: ShiftAssignment(technologist_ids=[], engineer_id=None)
                for shift_type in SHIFT_TYPES
            }
            day = DaySchedule(date=current_date, shifts=shifts)
            self.days.append(day)
            current_date += timedelta(days=1)
    
    def assign_worker(self, worker: Worker, date: datetime, shift_type: str) -> bool:
        """
        Asigna un trabajador a un turno específico.
        
        Args:
            worker: Objeto Worker a asignar
            date: Fecha del turno
            shift_type: Tipo de turno ('Mañana', 'Tarde', 'Noche')
            
        Returns:
            bool: True si la asignación fue exitosa, False en caso contrario
            
        Raises:
            ValueError: Si el tipo de turno no es válido o el worker no pertenece al horario
        """
        # Validaciones
        if worker not in self.workers:
            raise ValueError("El trabajador no pertenece a este horario")
        
        day_schedule = self._day_cache.get(date)
        if not day_schedule:
            return False  # Fecha fuera del rango del horario
        
        from ...infrastructure.config.constants import SHIFT_TYPES
        if shift_type not in SHIFT_TYPES:
            raise ValueError(f"Tipo de turno inválido: {shift_type}")
        
        shift_assignment = day_schedule.shifts[shift_type]
        
        if worker.is_technologist:
            # Verificar duplicados
            if worker.id in shift_assignment.technologist_ids:
                return False  # Ya está asignado
            
            shift_assignment.technologist_ids.append(worker.id)
        else:  # Es ingeniero
            if shift_assignment.engineer_id is not None:
                # Ya hay un ingeniero, reemplazar
                old_engineer = self.get_worker_by_id(shift_assignment.engineer_id, WorkerType.ENGINEER)
                if old_engineer:
                    old_engineer.remove_shift(date, shift_type)
            
            shift_assignment.engineer_id = worker.id
        
        # Registrar en el trabajador
        worker.add_shift(date, shift_type)
        return True
    
    def remove_worker_from_shift(self, worker: Worker, date: datetime, shift_type: str) -> bool:
        """
        Elimina a un trabajador de un turno específico.
        
        Args:
            worker: Objeto Worker a remover
            date: Fecha del turno
            shift_type: Tipo de turno
            
        Returns:
            bool: True si la eliminación fue exitosa, False en caso contrario
        """
        day_schedule = self._day_cache.get(date)
        if not day_schedule:
            return False
        
        from ...infrastructure.config.constants import SHIFT_TYPES
        if shift_type not in SHIFT_TYPES:
            return False
        
        shift_assignment = day_schedule.shifts[shift_type]
        removed = False
        
        if worker.is_technologist:
            if worker.id in shift_assignment.technologist_ids:
                shift_assignment.technologist_ids.remove(worker.id)
                removed = True
        else:  # Es ingeniero
            if shift_assignment.engineer_id == worker.id:
                shift_assignment.engineer_id = None
                removed = True
        
        # Actualizar el trabajador si se eliminó del horario
        if removed:
            worker.remove_shift(date, shift_type)
        
        return removed
    
    def get_workers_in_shift(self, date: datetime, shift_type: str) -> Tuple[List[Worker], Optional[Worker]]:
        """
        Retorna los trabajadores asignados a un turno específico.
        
        Args:
            date: Fecha del turno
            shift_type: Tipo de turno
            
        Returns:
            Tuple: (Lista de tecnólogos, Ingeniero o None)
        """
        day_schedule = self._day_cache.get(date)
        if not day_schedule:
            return [], None
        
        from ...infrastructure.config.constants import SHIFT_TYPES
        if shift_type not in SHIFT_TYPES:
            return [], None
        
        shift_assignment = day_schedule.shifts[shift_type]
        
        # Obtener tecnólogos
        technologists = []
        for tech_id in shift_assignment.technologist_ids:
            worker = self.get_worker_by_id(tech_id, WorkerType.TECHNOLOGIST)
            if worker:
                technologists.append(worker)
        
        # Obtener ingeniero
        engineer = None
        if shift_assignment.engineer_id is not None:
            engineer = self.get_worker_by_id(shift_assignment.engineer_id, WorkerType.ENGINEER)
        
        return technologists, engineer
    
    def get_shift_coverage(self, date: datetime, shift_type: str) -> Dict:
        """
        Evalúa la cobertura de un turno respecto a los requisitos.
        
        Args:
            date: Fecha del turno
            shift_type: Tipo de turno
            
        Returns:
            Dict: Información de cobertura con claves 'complete', 'technologists', 'engineer'
        """
        from ...infrastructure.config.settings import TECHS_PER_SHIFT, ENG_PER_SHIFT
        
        day_schedule = self._day_cache.get(date)
        if not day_schedule:
            return self._empty_coverage()
        
        from ...infrastructure.config.constants import SHIFT_TYPES
        if shift_type not in SHIFT_TYPES:
            return self._empty_coverage()
        
        shift_assignment = day_schedule.shifts[shift_type]
        
        techs_required = TECHS_PER_SHIFT.get(shift_type, 0)
        techs_assigned = len(shift_assignment.technologist_ids)
        eng_required = ENG_PER_SHIFT
        eng_assigned = 1 if shift_assignment.engineer_id is not None else 0
        
        return {
            "complete": (techs_assigned >= techs_required and eng_assigned >= eng_required),
            "technologists": {"required": techs_required, "assigned": techs_assigned},
            "engineer": {"required": eng_required, "assigned": eng_assigned}
        }
    
    def _empty_coverage(self) -> Dict:
        """Retorna estructura de cobertura vacía."""
        return {
            "complete": False,
            "technologists": {"required": 0, "assigned": 0},
            "engineer": {"required": 0, "assigned": 0}
        }
    
    def get_worker_by_id(self, worker_id: int, worker_type: WorkerType) -> Optional[Worker]:
        """
        Busca un trabajador por ID y tipo.
        
        Args:
            worker_id: ID del trabajador
            worker_type: Tipo de trabajador
            
        Returns:
            Worker o None: Trabajador encontrado o None
        """
        for worker in self.workers:
            if worker.id == worker_id and worker.worker_type == worker_type:
                return worker
        return None
    
    def get_technologists(self) -> List[Worker]:
        """Retorna solo los tecnólogos disponibles."""
        return [w for w in self.workers if w.is_technologist]
    
    def get_engineers(self) -> List[Worker]:
        """Retorna solo los ingenieros disponibles."""
        return [w for w in self.workers if w.is_engineer]
    
    def get_all_workers(self) -> List[Worker]:
        """Retorna todos los trabajadores (copia defensiva)."""
        return self.workers.copy()
    
    def get_day_schedule(self, date: datetime) -> Optional[DaySchedule]:
        """
        Retorna el horario de un día específico.
        
        Args:
            date: Fecha a buscar
            
        Returns:
            DaySchedule o None: Horario del día si existe, None en caso contrario
        """
        return self._day_cache.get(date)
    
    def get_shift_assignment(self, date: datetime, shift_type: str) -> Optional[ShiftAssignment]:
        """
        Retorna la asignación de un turno específico.
        
        Args:
            date: Fecha del turno
            shift_type: Tipo de turno
            
        Returns:
            ShiftAssignment o None: Asignación del turno si existe, None en caso contrario
        """
        day_schedule = self._day_cache.get(date)
        if day_schedule and shift_type in day_schedule.shifts:
            return day_schedule.shifts[shift_type]
        return None
    
    def get_total_shifts(self) -> int:
        """Retorna el número total de turnos en el horario."""
        from ...infrastructure.config.constants import SHIFT_TYPES
        return len(self.days) * len(SHIFT_TYPES)
    
    def get_period_duration_days(self) -> int:
        """Retorna la duración del período en días."""
        return (self.end_date - self.start_date).days + 1
    
    def is_date_in_range(self, date: datetime) -> bool:
        """Verifica si una fecha está dentro del rango del horario."""
        return self.start_date <= date <= self.end_date
    
    def get_dates_in_range(self) -> List[datetime]:
        """Retorna todas las fechas del período como lista."""
        dates = []
        current_date = self.start_date
        while current_date <= self.end_date:
            dates.append(current_date)
            current_date += timedelta(days=1)
        return dates
    
    def verify_data_integrity(self) -> List[str]:
        """
        Verifica la integridad de los datos del horario.
        
        Returns:
            List[str]: Lista de errores encontrados
        """
        errors = []
        
        # Verificar que todos los trabajadores asignados existan
        for day in self.days:
            for shift_type, assignment in day.shifts.items():
                # Verificar tecnólogos
                for tech_id in assignment.technologist_ids:
                    if not self.get_worker_by_id(tech_id, WorkerType.TECHNOLOGIST):
                        errors.append(f"Tecnólogo {tech_id} no encontrado en {day.date.strftime('%Y-%m-%d')} {shift_type}")
                
                # Verificar ingeniero
                if assignment.engineer_id is not None:
                    if not self.get_worker_by_id(assignment.engineer_id, WorkerType.ENGINEER):
                        errors.append(f"Ingeniero {assignment.engineer_id} no encontrado en {day.date.strftime('%Y-%m-%d')} {shift_type}")
        
        # Verificar consistencia con los registros de trabajadores
        for worker in self.workers:
            for shift_date, shift_type in worker.shifts:
                if not self.is_date_in_range(shift_date):
                    errors.append(f"{worker.get_formatted_id()} tiene turno fuera del rango: {shift_date.strftime('%Y-%m-%d')}")
                    continue
                
                assignment = self.get_shift_assignment(shift_date, shift_type)
                if not assignment:
                    errors.append(f"Asignación no encontrada para {worker.get_formatted_id()} en {shift_date.strftime('%Y-%m-%d')} {shift_type}")
                    continue
                
                # Verificar que el trabajador esté en la asignación
                if worker.is_technologist:
                    if worker.id not in assignment.technologist_ids:
                        errors.append(f"Inconsistencia: {worker.get_formatted_id()} no está en asignación {shift_date.strftime('%Y-%m-%d')} {shift_type}")
                else:
                    if assignment.engineer_id != worker.id:
                        errors.append(f"Inconsistencia: {worker.get_formatted_id()} no está en asignación {shift_date.strftime('%Y-%m-%d')} {shift_type}")
        
        return errors
    
    def get_summary_stats(self) -> Dict:
        """Retorna estadísticas resumen del horario."""
        total_shifts = self.get_total_shifts()
        complete_shifts = 0
        total_tech_assignments = 0
        total_eng_assignments = 0
        
        for day in self.days:
            for shift_type, assignment in day.shifts.items():
                coverage = self.get_shift_coverage(day.date, shift_type)
                if coverage["complete"]:
                    complete_shifts += 1
                total_tech_assignments += len(assignment.technologist_ids)
                if assignment.engineer_id is not None:
                    total_eng_assignments += 1
        
        return {
            "period": f"{self.start_date.strftime('%Y-%m-%d')} - {self.end_date.strftime('%Y-%m-%d')}",
            "duration_days": self.get_period_duration_days(),
            "total_workers": len(self.workers),
            "technologists": len(self.get_technologists()),
            "engineers": len(self.get_engineers()),
            "total_shifts": total_shifts,
            "complete_shifts": complete_shifts,
            "completion_percentage": (complete_shifts / total_shifts * 100) if total_shifts > 0 else 0,
            "tech_assignments": total_tech_assignments,
            "eng_assignments": total_eng_assignments
        }
    
    def __str__(self) -> str:
        """Representación string del horario."""
        stats = self.get_summary_stats()
        return (f"Schedule({stats['period']}, {stats['total_workers']} workers, "
               f"{stats['completion_percentage']:.1f}% complete)")
    
    def __repr__(self) -> str:
        """Representación detallada del horario."""
        stats = self.get_summary_stats()
        return f"Schedule(start={self.start_date}, end={self.end_date}, workers={len(self.workers)}, days={len(self.days)})"