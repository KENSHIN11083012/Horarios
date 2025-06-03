"""
Servicio de generación de horarios - Dominio puro.

Este módulo contiene la lógica de dominio para generar horarios,
sin dependencias de infraestructura o aplicación.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass
from enum import Enum

from ..models import Worker, Schedule, ShiftType, WorkerType
from ..rules.interfaces import ConstraintChecker, HolidayProvider
from ..rules.validators import BasicConstraintChecker


class AssignmentStrategy(Enum):
    """Estrategias de asignación disponibles."""
    BALANCED = "balanced"           # Distribución equilibrada estándar
    PROACTIVE = "proactive"         # Minimiza violaciones futuras
    PRIORITY_BASED = "priority"     # Basada en prioridades de turno
    EQUITY_FOCUSED = "equity"       # Enfocada en equidad económica


@dataclass
class GenerationContext:
    """Contexto para la generación de horarios."""
    strategy: AssignmentStrategy
    allow_relaxed_constraints: bool
    prioritize_critical_shifts: bool
    max_violations_allowed: int
    
    @classmethod
    def default(cls) -> 'GenerationContext':
        """Crea un contexto con configuración por defecto."""
        return cls(
            strategy=AssignmentStrategy.PROACTIVE,
            allow_relaxed_constraints=False,
            prioritize_critical_shifts=True,
            max_violations_allowed=0
        )
    
    @classmethod
    def relaxed(cls) -> 'GenerationContext':
        """Crea un contexto con restricciones relajadas."""
        return cls(
            strategy=AssignmentStrategy.PROACTIVE,
            allow_relaxed_constraints=True,
            prioritize_critical_shifts=True,
            max_violations_allowed=5
        )


@dataclass
class AssignmentResult:
    """Resultado de una asignación específica."""
    success: bool
    worker: Optional[Worker]
    violations: List[str]
    impact_score: float
    
    @classmethod
    def failure(cls, violations: List[str]) -> 'AssignmentResult':
        """Crea un resultado de fallo."""
        return cls(
            success=False,
            worker=None,
            violations=violations,
            impact_score=float('inf')
        )
    
    @classmethod
    def success_result(cls, worker: Worker, impact_score: float = 0.0) -> 'AssignmentResult':
        """Crea un resultado exitoso."""
        return cls(
            success=True,
            worker=worker,
            violations=[],
            impact_score=impact_score
        )


class WorkerSelector:
    """
    Selector de trabajadores para turnos específicos.
    
    Encapsula la lógica de selección de trabajadores considerando
    restricciones, balance de carga y optimización.
    """
    
    def __init__(self, constraint_checker: ConstraintChecker):
        """
        Inicializa el selector con un verificador de restricciones.
        
        Args:
            constraint_checker: Verificador de restricciones a usar
        """
        self.constraint_checker = constraint_checker
    
    def select_workers_for_shift(self, 
                                available_workers: List[Worker],
                                num_needed: int,
                                date: datetime,
                                shift_type: ShiftType,
                                schedule: Schedule,
                                context: GenerationContext) -> List[AssignmentResult]:
        """
        Selecciona trabajadores para un turno específico.
        
        Args:
            available_workers: Lista de trabajadores disponibles
            num_needed: Número de trabajadores necesarios
            date: Fecha del turno
            shift_type: Tipo de turno
            schedule: Horario actual
            context: Contexto de generación
            
        Returns:
            List[AssignmentResult]: Resultados de asignación para cada trabajador seleccionado
        """
        if context.strategy == AssignmentStrategy.PROACTIVE:
            return self._select_proactive(available_workers, num_needed, date, shift_type, schedule, context)
        elif context.strategy == AssignmentStrategy.BALANCED:
            return self._select_balanced(available_workers, num_needed, date, shift_type, schedule, context)
        elif context.strategy == AssignmentStrategy.PRIORITY_BASED:
            return self._select_priority_based(available_workers, num_needed, date, shift_type, schedule, context)
        elif context.strategy == AssignmentStrategy.EQUITY_FOCUSED:
            return self._select_equity_focused(available_workers, num_needed, date, shift_type, schedule, context)
        else:
            # Fallback a estrategia balanceada
            return self._select_balanced(available_workers, num_needed, date, shift_type, schedule, context)
    
    def _select_proactive(self, workers: List[Worker], num_needed: int, date: datetime,
                         shift_type: ShiftType, schedule: Schedule, context: GenerationContext) -> List[AssignmentResult]:
        """Selección proactiva que minimiza violaciones futuras."""
        worker_scores = []
        
        for worker in workers:
            # Verificar restricciones actuales
            can_assign, violations = self.constraint_checker.check_all_constraints(
                worker, date, shift_type, schedule
            )
            
            if not can_assign and not context.allow_relaxed_constraints:
                continue
            
            # Calcular impacto futuro
            impact_score = self._calculate_future_impact(worker, date, shift_type, schedule)
            
            # Calcular score combinado
            workload_factor = worker.get_total_shifts() / 30.0  # Normalizar carga
            experience_factor = worker.get_shift_types_count().get(shift_type.value, 0) / 10.0
            
            combined_score = impact_score * 0.6 + workload_factor * 0.3 - experience_factor * 0.1
            
            worker_scores.append((worker, combined_score, impact_score, violations))
        
        # Ordenar por score (menor = mejor)
        worker_scores.sort(key=lambda x: x[1])
        
        # Seleccionar los mejores
        results = []
        for i, (worker, score, impact, violations) in enumerate(worker_scores[:num_needed]):
            results.append(AssignmentResult.success_result(worker, impact))
        
        return results
    
    def _select_balanced(self, workers: List[Worker], num_needed: int, date: datetime,
                        shift_type: ShiftType, schedule: Schedule, context: GenerationContext) -> List[AssignmentResult]:
        """Selección balanceada basada en distribución de carga."""
        eligible_workers = []
        
        for worker in workers:
            can_assign, violations = self.constraint_checker.check_all_constraints(
                worker, date, shift_type, schedule
            )
            
            if can_assign or context.allow_relaxed_constraints:
                # Score basado en carga total y por tipo
                total_shifts = worker.get_total_shifts()
                type_shifts = worker.get_shift_types_count().get(shift_type.value, 0)
                
                balance_score = total_shifts + (type_shifts * 0.5)  # Penalizar especialización excesiva
                eligible_workers.append((worker, balance_score, violations))
        
        # Ordenar por balance (menor carga primero)
        eligible_workers.sort(key=lambda x: x[1])
        
        results = []
        for worker, score, violations in eligible_workers[:num_needed]:
            results.append(AssignmentResult.success_result(worker, score))
        
        return results
    
    def _select_priority_based(self, workers: List[Worker], num_needed: int, date: datetime,
                              shift_type: ShiftType, schedule: Schedule, context: GenerationContext) -> List[AssignmentResult]:
        """Selección basada en prioridades de turno y trabajador."""
        from ..models.shift import ShiftCharacteristics
        
        is_premium = ShiftCharacteristics.is_premium_shift(date, shift_type)
        shift_priority = ShiftCharacteristics.get_shift_priority(shift_type)
        
        worker_priorities = []
        
        for worker in workers:
            can_assign, violations = self.constraint_checker.check_all_constraints(
                worker, date, shift_type, schedule
            )
            
            if not can_assign and not context.allow_relaxed_constraints:
                continue
            
            # Calcular prioridad del trabajador
            experience_priority = worker.get_shift_types_count().get(shift_type.value, 0)
            workload_penalty = worker.get_total_shifts() * 0.1
            
            # Para turnos premium, priorizar equidad económica
            if is_premium:
                equity_bonus = max(0, 50 - worker.earnings) * 0.1  # Bonus para menos compensados
            else:
                equity_bonus = 0
            
            total_priority = (experience_priority + equity_bonus - workload_penalty + shift_priority)
            worker_priorities.append((worker, total_priority, violations))
        
        # Ordenar por prioridad (mayor primero)
        worker_priorities.sort(key=lambda x: x[1], reverse=True)
        
        results = []
        for worker, priority, violations in worker_priorities[:num_needed]:
            results.append(AssignmentResult.success_result(worker, -priority))  # Negativo porque menor = mejor
        
        return results
    
    def _select_equity_focused(self, workers: List[Worker], num_needed: int, date: datetime,
                              shift_type: ShiftType, schedule: Schedule, context: GenerationContext) -> List[AssignmentResult]:
        """Selección enfocada en equidad económica."""
        if not workers:
            return []
        
        # Calcular estadísticas de compensación
        compensations = [w.earnings for w in workers]
        avg_compensation = sum(compensations) / len(compensations)
        
        worker_equity_scores = []
        
        for worker in workers:
            can_assign, violations = self.constraint_checker.check_all_constraints(
                worker, date, shift_type, schedule
            )
            
            if not can_assign and not context.allow_relaxed_constraints:
                continue
            
            # Score de equidad: menor compensación = mayor prioridad
            compensation_gap = avg_compensation - worker.earnings
            workload_factor = worker.get_total_shifts() * 0.05
            
            equity_score = compensation_gap - workload_factor
            worker_equity_scores.append((worker, equity_score, violations))
        
        # Ordenar por equity score (mayor primero = más necesitado)
        worker_equity_scores.sort(key=lambda x: x[1], reverse=True)
        
        results = []
        for worker, score, violations in worker_equity_scores[:num_needed]:
            results.append(AssignmentResult.success_result(worker, -score))
        
        return results
    
    def _calculate_future_impact(self, worker: Worker, date: datetime, 
                                shift_type: ShiftType, schedule: Schedule) -> float:
        """
        Calcula el impacto futuro de asignar un turno a un trabajador.
        
        Args:
            worker: Trabajador a evaluar
            date: Fecha del turno
            shift_type: Tipo de turno
            schedule: Horario actual
            
        Returns:
            float: Score de impacto (mayor = peor impacto)
        """
        impact_score = 0.0
        
        # Simular la asignación temporalmente
        temp_worker = self._create_temp_worker_with_shift(worker, date, shift_type)
        
        # Evaluar impacto en próximos 3 días
        for future_days in range(1, 4):
            future_date = date + timedelta(days=future_days)
            
            if not schedule.is_date_in_range(future_date):
                continue
            
            # Verificar disponibilidad para cada tipo de turno
            for future_shift in [ShiftType.MORNING, ShiftType.AFTERNOON, ShiftType.NIGHT]:
                can_work, _ = self.constraint_checker.check_all_constraints(
                    temp_worker, future_date, future_shift, schedule
                )
                
                if not can_work:
                    # Calcular criticidad del bloqueo
                    shift_criticality = 3 if future_shift == ShiftType.NIGHT else 2
                    day_proximity = 4 - future_days  # 3, 2, 1 para días 1, 2, 3
                    
                    impact_score += shift_criticality * day_proximity
        
        return impact_score
    
    def _create_temp_worker_with_shift(self, worker: Worker, date: datetime, shift_type: ShiftType) -> Worker:
        """Crea una copia temporal del trabajador con una asignación adicional."""
        temp_worker = Worker(worker.id, worker.worker_type)
        temp_worker.shifts = worker.shifts.copy()
        temp_worker.days_off = worker.days_off.copy()
        temp_worker.earnings = worker.earnings
        
        # Añadir la nueva asignación
        temp_worker.add_shift(date, shift_type.value)
        
        return temp_worker


class CriticalDayAnalyzer:
    """
    Analizador de días críticos para priorización.
    
    Identifica días que requieren atención especial durante la generación.
    """
    
    def __init__(self, holiday_provider: Optional[HolidayProvider] = None):
        """
        Inicializa el analizador.
        
        Args:
            holiday_provider: Proveedor de información de festivos (opcional)
        """
        self.holiday_provider = holiday_provider
    
    def identify_critical_days(self, start_date: datetime, end_date: datetime) -> Set[datetime]:
        """
        Identifica días críticos en un período.
        
        Args:
            start_date: Fecha de inicio
            end_date: Fecha de fin
            
        Returns:
            Set[datetime]: Conjunto de fechas críticas
        """
        critical_days = set()
        
        current_date = start_date
        while current_date <= end_date:
            if self._is_critical_day(current_date):
                critical_days.add(current_date)
            current_date += timedelta(days=1)
        
        return critical_days
    
    def _is_critical_day(self, date: datetime) -> bool:
        """Determina si un día es crítico."""
        # Fin de semana
        if date.weekday() >= 5:
            return True
        
        # Festivo (si hay proveedor)
        if self.holiday_provider and self.holiday_provider.is_holiday(date):
            return True
        
        return False
    
    def get_day_priority(self, date: datetime) -> int:
        """
        Obtiene la prioridad de un día para ordenación.
        
        Args:
            date: Fecha a evaluar
            
        Returns:
            int: Prioridad (menor número = mayor prioridad)
        """
        if self._is_critical_day(date):
            return 0  # Alta prioridad
        else:
            return 1  # Prioridad normal


class ScheduleGenerator:
    """
    Generador principal de horarios.
    
    Orquesta todo el proceso de generación utilizando las estrategias
    y componentes especializados.
    """
    
    def __init__(self, 
                 constraint_checker: Optional[ConstraintChecker] = None,
                 holiday_provider: Optional[HolidayProvider] = None):
        """
        Inicializa el generador.
        
        Args:
            constraint_checker: Verificador de restricciones (opcional)
            holiday_provider: Proveedor de festivos (opcional)
        """
        self.constraint_checker = constraint_checker or BasicConstraintChecker()
        self.worker_selector = WorkerSelector(self.constraint_checker)
        self.critical_day_analyzer = CriticalDayAnalyzer(holiday_provider)
    
    def generate_schedule(self, 
                         start_date: datetime,
                         end_date: datetime,
                         technologists: List[Worker],
                         engineers: List[Worker],
                         context: Optional[GenerationContext] = None) -> Schedule:
        """
        Genera un horario completo para el período especificado.
        
        Args:
            start_date: Fecha de inicio
            end_date: Fecha de fin
            technologists: Lista de tecnólogos
            engineers: Lista de ingenieros
            context: Contexto de generación (opcional)
            
        Returns:
            Schedule: Horario generado
            
        Raises:
            ValueError: Si los parámetros son inválidos
        """
        if context is None:
            context = GenerationContext.default()
        
        # Validar parámetros
        self._validate_generation_parameters(start_date, end_date, technologists, engineers)
        
        # Crear horario base
        all_workers = technologists + engineers
        schedule = Schedule(start_date, end_date, all_workers)
        
        # Identificar días críticos
        critical_days = self.critical_day_analyzer.identify_critical_days(start_date, end_date)
        
        # Ordenar fechas por prioridad
        dates = schedule.get_dates_in_range()
        if context.prioritize_critical_shifts:
            dates.sort(key=lambda d: (self.critical_day_analyzer.get_day_priority(d), d))
        
        # Generar turnos por fase
        self._generate_engineers_phase(schedule, dates, engineers, context)
        self._generate_night_technologists_phase(schedule, dates, technologists, context)
        self._generate_remaining_shifts_phase(schedule, dates, technologists, engineers, context)
        
        return schedule
    
    def _validate_generation_parameters(self, start_date: datetime, end_date: datetime,
                                      technologists: List[Worker], engineers: List[Worker]):
        """Valida los parámetros de generación."""
        if start_date > end_date:
            raise ValueError("start_date debe ser anterior o igual a end_date")
        
        if not technologists:
            raise ValueError("Debe haber al menos un tecnólogo")
        
        if not engineers:
            raise ValueError("Debe haber al menos un ingeniero")
        
        # Verificar tipos de trabajador
        if not all(w.is_technologist for w in technologists):
            raise ValueError("Todos los elementos de technologists deben ser tecnólogos")
        
        if not all(w.is_engineer for w in engineers):
            raise ValueError("Todos los elementos de engineers deben ser ingenieros")
    
    def _generate_engineers_phase(self, schedule: Schedule, dates: List[datetime],
                                 engineers: List[Worker], context: GenerationContext):
        """Fase 1: Pre-asignar ingenieros a todos los turnos."""
        shift_types = [ShiftType.MORNING, ShiftType.AFTERNOON, ShiftType.NIGHT]
        
        for date in dates:
            for shift_type in shift_types:
                # Verificar si ya hay ingeniero asignado
                _, current_engineer = schedule.get_workers_in_shift(date, shift_type)
                if current_engineer:
                    continue
                
                # Seleccionar ingeniero
                results = self.worker_selector.select_workers_for_shift(
                    engineers, 1, date, shift_type, schedule, context
                )
                
                if results and results[0].success:
                    engineer = results[0].worker
                    schedule.assign_worker(engineer, date, shift_type)
    
    def _generate_night_technologists_phase(self, schedule: Schedule, dates: List[datetime],
                                          technologists: List[Worker], context: GenerationContext):
        """Fase 2: Pre-asignar tecnólogos para turnos nocturnos."""
        from ...infrastructure.config.settings import TECHS_PER_SHIFT
        
        for date in dates:
            shift_type = ShiftType.NIGHT
            
            # Verificar cobertura actual
            current_techs, _ = schedule.get_workers_in_shift(date, shift_type)
            needed = TECHS_PER_SHIFT.get(shift_type.value, 2) - len(current_techs)
            
            if needed <= 0:
                continue
            
            # Seleccionar tecnólogos
            results = self.worker_selector.select_workers_for_shift(
                technologists, needed, date, shift_type, schedule, context
            )
            
            for result in results:
                if result.success:
                    schedule.assign_worker(result.worker, date, shift_type)
    
    def _generate_remaining_shifts_phase(self, schedule: Schedule, dates: List[datetime],
                                       technologists: List[Worker], engineers: List[Worker],
                                       context: GenerationContext):
        """Fase 3: Completar turnos restantes."""
        from ...infrastructure.config.settings import TECHS_PER_SHIFT
        
        shift_types = [ShiftType.MORNING, ShiftType.AFTERNOON, ShiftType.NIGHT]
        
        for date in dates:
            for shift_type in shift_types:
                # Completar tecnólogos si es necesario
                current_techs, _ = schedule.get_workers_in_shift(date, shift_type)
                required_techs = TECHS_PER_SHIFT.get(shift_type.value, 5)
                needed_techs = required_techs - len(current_techs)
                
                if needed_techs > 0:
                    # Filtrar tecnólogos ya asignados
                    available_techs = [t for t in technologists if t not in current_techs]
                    
                    results = self.worker_selector.select_workers_for_shift(
                        available_techs, needed_techs, date, shift_type, schedule, context
                    )
                    
                    for result in results:
                        if result.success:
                            schedule.assign_worker(result.worker, date, shift_type)