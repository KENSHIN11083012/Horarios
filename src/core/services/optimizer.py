"""
Servicio de optimización de horarios - Dominio puro.

Este módulo contiene la lógica de dominio para optimizar horarios existentes,
mejorando equidad, balance de carga y cumplimiento de restricciones.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass
from enum import Enum
import math

from ..models import Worker, Schedule, ShiftType, WorkerType
from ..rules.interfaces import ConstraintChecker, CompensationCalculator, WorkloadBalancer, EquityAnalyzer
from ..rules.validators import BasicConstraintChecker


class OptimizationObjective(Enum):
    """Objetivos de optimización disponibles."""
    WORKLOAD_BALANCE = "workload_balance"         # Equilibrar carga de trabajo
    COMPENSATION_EQUITY = "compensation_equity"   # Equidad en compensaciones
    CONSTRAINT_COMPLIANCE = "constraint_compliance"  # Cumplimiento de restricciones
    COMPREHENSIVE = "comprehensive"               # Optimización integral


@dataclass
class OptimizationTarget:
    """Meta específica de optimización."""
    objective: OptimizationObjective
    target_value: float
    weight: float
    tolerance: float = 0.05
    
    def is_achieved(self, current_value: float) -> bool:
        """Verifica si la meta se ha alcanzado."""
        return abs(current_value - self.target_value) <= self.tolerance


@dataclass
class OptimizationConfig:
    """Configuración para el proceso de optimización."""
    targets: List[OptimizationTarget]
    max_iterations: int = 10
    max_swaps_per_iteration: int = 20
    improvement_threshold: float = 0.01
    allow_constraint_relaxation: bool = False
    
    @classmethod
    def balanced_workload(cls) -> 'OptimizationConfig':
        """Configuración para balance de carga de trabajo."""
        return cls(
            targets=[
                OptimizationTarget(
                    objective=OptimizationObjective.WORKLOAD_BALANCE,
                    target_value=0.95,  # 95% de balance
                    weight=1.0
                )
            ],
            max_iterations=5,
            max_swaps_per_iteration=15
        )
    
    @classmethod
    def compensation_equity(cls) -> 'OptimizationConfig':
        """Configuración para equidad de compensaciones."""
        return cls(
            targets=[
                OptimizationTarget(
                    objective=OptimizationObjective.COMPENSATION_EQUITY,
                    target_value=0.05,  # Máximo 5% de diferencia
                    weight=1.0
                )
            ],
            max_iterations=8,
            max_swaps_per_iteration=25
        )
    
    @classmethod
    def comprehensive(cls) -> 'OptimizationConfig':
        """Configuración para optimización integral."""
        return cls(
            targets=[
                OptimizationTarget(
                    objective=OptimizationObjective.WORKLOAD_BALANCE,
                    target_value=0.90,
                    weight=0.4
                ),
                OptimizationTarget(
                    objective=OptimizationObjective.COMPENSATION_EQUITY,
                    target_value=0.10,
                    weight=0.4
                ),
                OptimizationTarget(
                    objective=OptimizationObjective.CONSTRAINT_COMPLIANCE,
                    target_value=1.0,
                    weight=0.2
                )
            ],
            max_iterations=12,
            max_swaps_per_iteration=30
        )


@dataclass
class SwapProposal:
    """Propuesta de intercambio entre trabajadores."""
    worker1: Worker
    worker2: Worker
    date1: datetime
    shift1: ShiftType
    date2: datetime
    shift2: ShiftType
    expected_improvement: float
    violates_constraints: bool
    
    @property
    def is_viable(self) -> bool:
        """Verifica si el intercambio es viable."""
        return not self.violates_constraints and self.expected_improvement > 0


@dataclass
class OptimizationResult:
    """Resultado del proceso de optimización."""
    success: bool
    iterations_performed: int
    swaps_executed: int
    initial_score: float
    final_score: float
    improvement: float
    targets_achieved: List[OptimizationObjective]
    violations_remaining: List[str]
    
    @property
    def improvement_percentage(self) -> float:
        """Porcentaje de mejora obtenido."""
        if self.initial_score == 0:
            return 0.0
        return (self.improvement / self.initial_score) * 100


class WorkloadAnalyzer:
    """
    Analizador de carga de trabajo.
    
    Evalúa y calcula métricas de distribución de carga entre trabajadores.
    """
    
    def calculate_workload_balance_score(self, workers: List[Worker]) -> float:
        """
        Calcula un score de balance de carga de trabajo.
        
        Args:
            workers: Lista de trabajadores a evaluar
            
        Returns:
            float: Score de balance (0.0 - 1.0, mayor = mejor balance)
        """
        if not workers:
            return 1.0
        
        # Obtener cargas de trabajo
        workloads = [w.get_total_shifts() for w in workers]
        
        if not workloads or max(workloads) == 0:
            return 1.0
        
        # Calcular coeficiente de variación
        mean_workload = sum(workloads) / len(workloads)
        variance = sum((w - mean_workload) ** 2 for w in workloads) / len(workloads)
        std_dev = math.sqrt(variance)
        
        # Coeficiente de variación (menor = mejor balance)
        cv = std_dev / mean_workload if mean_workload > 0 else 0
        
        # Convertir a score (0-1, mayor = mejor)
        balance_score = max(0, 1 - cv)
        
        return balance_score
    
    def calculate_shift_type_balance_score(self, workers: List[Worker]) -> float:
        """
        Calcula un score de balance de tipos de turno.
        
        Args:
            workers: Lista de trabajadores a evaluar
            
        Returns:
            float: Score de balance de tipos (0.0 - 1.0, mayor = mejor)
        """
        if not workers:
            return 1.0
        
        total_imbalance = 0
        total_workers = 0
        
        for worker in workers:
            shift_counts = worker.get_shift_types_count()
            if shift_counts:
                max_count = max(shift_counts.values())
                min_count = min(shift_counts.values())
                imbalance = max_count - min_count
                total_imbalance += imbalance
                total_workers += 1
        
        if total_workers == 0:
            return 1.0
        
        avg_imbalance = total_imbalance / total_workers
        
        # Normalizar (asumiendo que un desequilibrio de 6+ es muy malo)
        normalized_imbalance = min(avg_imbalance / 6.0, 1.0)
        
        return 1.0 - normalized_imbalance
    
    def identify_workload_imbalances(self, workers: List[Worker]) -> List[Tuple[Worker, Worker, float]]:
        """
        Identifica desequilibrios de carga entre trabajadores.
        
        Args:
            workers: Lista de trabajadores a analizar
            
        Returns:
            List[Tuple[Worker, Worker, float]]: Lista de (sobrecargado, subcargado, diferencia)
        """
        imbalances = []
        
        # Ordenar por carga de trabajo
        sorted_workers = sorted(workers, key=lambda w: w.get_total_shifts())
        
        if len(sorted_workers) < 2:
            return imbalances
        
        # Identificar extremos
        underloaded = sorted_workers[:len(sorted_workers)//3]  # Tercio inferior
        overloaded = sorted_workers[-len(sorted_workers)//3:]  # Tercio superior
        
        # Encontrar pares con mayor diferencia
        for overloaded_worker in overloaded:
            for underloaded_worker in underloaded:
                difference = overloaded_worker.get_total_shifts() - underloaded_worker.get_total_shifts()
                if difference > 2:  # Solo diferencias significativas
                    imbalances.append((overloaded_worker, underloaded_worker, difference))
        
        # Ordenar por diferencia (mayor primero)
        imbalances.sort(key=lambda x: x[2], reverse=True)
        
        return imbalances


class CompensationAnalyzer:
    """
    Analizador de equidad en compensaciones.
    
    Evalúa la distribución de compensaciones entre trabajadores.
    """
    
    def __init__(self, compensation_calculator: Optional[CompensationCalculator] = None):
        """
        Inicializa el analizador.
        
        Args:
            compensation_calculator: Calculador de compensaciones (opcional)
        """
        self.compensation_calculator = compensation_calculator
    
    def calculate_compensation_equity_score(self, workers: List[Worker]) -> float:
        """
        Calcula un score de equidad en compensaciones.
        
        Args:
            workers: Lista de trabajadores a evaluar
            
        Returns:
            float: Score de equidad (0.0 - 1.0, mayor = más equitativo)
        """
        if not workers:
            return 1.0
        
        # Recalcular compensaciones si tenemos calculador
        if self.compensation_calculator:
            for worker in workers:
                total_comp = self.compensation_calculator.calculate_worker_total_compensation(worker)
                worker.earnings = total_comp
        
        # Obtener compensaciones
        compensations = [w.earnings for w in workers]
        
        if not compensations or min(compensations) == 0:
            return 1.0
        
        # Calcular diferencia porcentual
        min_comp = min(compensations)
        max_comp = max(compensations)
        
        diff_percentage = (max_comp - min_comp) / min_comp
        
        # Convertir a score (menor diferencia = mejor equidad)
        # Asumiendo que 25% de diferencia es el límite aceptable
        normalized_diff = min(diff_percentage / 0.25, 1.0)
        equity_score = 1.0 - normalized_diff
        
        return equity_score
    
    def identify_compensation_imbalances(self, workers: List[Worker]) -> List[Tuple[Worker, Worker, float]]:
        """
        Identifica desequilibrios de compensación entre trabajadores.
        
        Args:
            workers: Lista de trabajadores a analizar
            
        Returns:
            List[Tuple[Worker, Worker, float]]: Lista de (mejor_pagado, peor_pagado, diferencia_porcentual)
        """
        imbalances = []
        
        # Ordenar por compensación
        sorted_workers = sorted(workers, key=lambda w: w.earnings)
        
        if len(sorted_workers) < 2:
            return imbalances
        
        # Identificar extremos
        underpaid = sorted_workers[:len(sorted_workers)//3]  # Tercio inferior
        overpaid = sorted_workers[-len(sorted_workers)//3:]  # Tercio superior
        
        # Encontrar pares con mayor diferencia porcentual
        for overpaid_worker in overpaid:
            for underpaid_worker in underpaid:
                if underpaid_worker.earnings > 0:
                    diff_percentage = (overpaid_worker.earnings - underpaid_worker.earnings) / underpaid_worker.earnings
                    if diff_percentage > 0.15:  # Solo diferencias mayores al 15%
                        imbalances.append((overpaid_worker, underpaid_worker, diff_percentage))
        
        # Ordenar por diferencia porcentual (mayor primero)
        imbalances.sort(key=lambda x: x[2], reverse=True)
        
        return imbalances


class SwapGenerator:
    """
    Generador de propuestas de intercambio.
    
    Identifica y propone intercambios que pueden mejorar el horario.
    """
    
    def __init__(self, constraint_checker: ConstraintChecker):
        """
        Inicializa el generador.
        
        Args:
            constraint_checker: Verificador de restricciones
        """
        self.constraint_checker = constraint_checker
    
    def generate_workload_balancing_swaps(self, schedule: Schedule, 
                                        imbalances: List[Tuple[Worker, Worker, float]]) -> List[SwapProposal]:
        """
        Genera propuestas de intercambio para balancear carga de trabajo.
        
        Args:
            schedule: Horario actual
            imbalances: Lista de desequilibrios identificados
            
        Returns:
            List[SwapProposal]: Lista de propuestas de intercambio
        """
        proposals = []
        
        for overloaded, underloaded, difference in imbalances:
            # Buscar turnos que puedan intercambiarse
            for date1, shift1_str in overloaded.shifts:
                shift1 = ShiftType.from_string(shift1_str)
                
                for date2, shift2_str in underloaded.shifts:
                    shift2 = ShiftType.from_string(shift2_str)
                    
                    # Evaluar intercambio
                    proposal = self._evaluate_swap(
                        schedule, overloaded, underloaded,
                        date1, shift1, date2, shift2,
                        OptimizationObjective.WORKLOAD_BALANCE
                    )
                    
                    if proposal and proposal.is_viable:
                        proposals.append(proposal)
        
        # Ordenar por mejora esperada
        proposals.sort(key=lambda p: p.expected_improvement, reverse=True)
        
        return proposals
    
    def generate_compensation_equity_swaps(self, schedule: Schedule,
                                         imbalances: List[Tuple[Worker, Worker, float]]) -> List[SwapProposal]:
        """
        Genera propuestas de intercambio para mejorar equidad de compensaciones.
        
        Args:
            schedule: Horario actual
            imbalances: Lista de desequilibrios de compensación
            
        Returns:
            List[SwapProposal]: Lista de propuestas de intercambio
        """
        proposals = []
        
        for overpaid, underpaid, diff_percentage in imbalances:
            # Buscar turnos premium del trabajador bien pagado
            premium_shifts = self._find_premium_shifts(overpaid, schedule)
            regular_shifts = self._find_regular_shifts(underpaid, schedule)
            
            # Proponer intercambios de turnos premium por regulares
            for date1, shift1 in premium_shifts:
                shift1_type = ShiftType.from_string(shift1)
                
                for date2, shift2 in regular_shifts:
                    shift2_type = ShiftType.from_string(shift2)
                    
                    proposal = self._evaluate_swap(
                        schedule, overpaid, underpaid,
                        date1, shift1_type, date2, shift2_type,
                        OptimizationObjective.COMPENSATION_EQUITY
                    )
                    
                    if proposal and proposal.is_viable:
                        proposals.append(proposal)
        
        # Ordenar por mejora esperada
        proposals.sort(key=lambda p: p.expected_improvement, reverse=True)
        
        return proposals
    
    def _evaluate_swap(self, schedule: Schedule, worker1: Worker, worker2: Worker,
                      date1: datetime, shift1: ShiftType, date2: datetime, shift2: ShiftType,
                      objective: OptimizationObjective) -> Optional[SwapProposal]:
        """
        Evalúa una propuesta de intercambio específica.
        
        Args:
            schedule: Horario actual
            worker1: Primer trabajador
            worker2: Segundo trabajador
            date1: Fecha del primer turno
            shift1: Tipo del primer turno
            date2: Fecha del segundo turno
            shift2: Tipo del segundo turno
            objective: Objetivo de optimización
            
        Returns:
            SwapProposal o None: Propuesta si es viable, None en caso contrario
        """
        # Verificar restricciones para el intercambio
        temp_worker1 = self._create_temp_worker_with_swap(worker1, date1, shift1.value, date2, shift2.value)
        temp_worker2 = self._create_temp_worker_with_swap(worker2, date2, shift2.value, date1, shift1.value)
        
        # Verificar que ambos trabajadores puedan hacer los nuevos turnos
        can_assign1, _ = self.constraint_checker.check_all_constraints(temp_worker2, date1, shift1, schedule)
        can_assign2, _ = self.constraint_checker.check_all_constraints(temp_worker1, date2, shift2, schedule)
        
        violates_constraints = not (can_assign1 and can_assign2)
        
        # Calcular mejora esperada según el objetivo
        if objective == OptimizationObjective.WORKLOAD_BALANCE:
            improvement = self._calculate_workload_improvement(worker1, worker2)
        elif objective == OptimizationObjective.COMPENSATION_EQUITY:
            improvement = self._calculate_compensation_improvement(
                worker1, worker2, date1, shift1, date2, shift2, schedule
            )
        else:
            improvement = 0.0
        
        return SwapProposal(
            worker1=worker1,
            worker2=worker2,
            date1=date1,
            shift1=shift1,
            date2=date2,
            shift2=shift2,
            expected_improvement=improvement,
            violates_constraints=violates_constraints
        )
    
    def _create_temp_worker_with_swap(self, worker: Worker, remove_date: datetime, 
                                    remove_shift: str, add_date: datetime, add_shift: str) -> Worker:
        """Crea una copia temporal del trabajador con un intercambio simulado."""
        temp_worker = Worker(worker.id, worker.worker_type)
        temp_worker.days_off = worker.days_off.copy()
        temp_worker.earnings = worker.earnings
        
        # Copiar turnos excepto el que se va a quitar
        temp_worker.shifts = [
            (date, shift) for date, shift in worker.shifts
            if not (date == remove_date and shift == remove_shift)
        ]
        
        # Añadir el nuevo turno
        temp_worker.shifts.append((add_date, add_shift))
        
        return temp_worker
    
    def _find_premium_shifts(self, worker: Worker, schedule: Schedule) -> List[Tuple[datetime, str]]:
        """Encuentra turnos premium de un trabajador."""
        from ..models.shift import ShiftCharacteristics
        
        premium_shifts = []
        for date, shift_type in worker.shifts:
            shift_enum = ShiftType.from_string(shift_type)
            if ShiftCharacteristics.is_premium_shift(date, shift_enum):
                premium_shifts.append((date, shift_type))
        
        return premium_shifts
    
    def _find_regular_shifts(self, worker: Worker, schedule: Schedule) -> List[Tuple[datetime, str]]:
        """Encuentra turnos regulares de un trabajador."""
        from ..models.shift import ShiftCharacteristics
        
        regular_shifts = []
        for date, shift_type in worker.shifts:
            shift_enum = ShiftType.from_string(shift_type)
            if not ShiftCharacteristics.is_premium_shift(date, shift_enum):
                regular_shifts.append((date, shift_type))
        
        return regular_shifts
    
    def _calculate_workload_improvement(self, worker1: Worker, worker2: Worker) -> float:
        """Calcula la mejora de balance de carga por intercambio."""
        current_diff = abs(worker1.get_total_shifts() - worker2.get_total_shifts())
        
        if current_diff <= 1:
            return 0.0  # Ya están balanceados
        
        # Simular intercambio (ambos cambian 1 turno)
        new_diff = abs((worker1.get_total_shifts() - 1) - (worker2.get_total_shifts() + 1))
        
        improvement = current_diff - new_diff
        return max(0, improvement)
    
    def _calculate_compensation_improvement(self, worker1: Worker, worker2: Worker,
                                         date1: datetime, shift1: ShiftType,
                                         date2: datetime, shift2: ShiftType,
                                         schedule: Schedule) -> float:
        """Calcula la mejora de equidad de compensación por intercambio."""
        if not self.compensation_calculator:
            return 0.0
        
        # Calcular compensaciones de los turnos
        comp1 = self.compensation_calculator.calculate_shift_compensation(date1, shift1)
        comp2 = self.compensation_calculator.calculate_shift_compensation(date2, shift2)
        
        # Diferencia actual de compensaciones
        current_diff = abs(worker1.earnings - worker2.earnings)
        
        # Simular intercambio
        new_earnings1 = worker1.earnings - comp1 + comp2
        new_earnings2 = worker2.earnings - comp2 + comp1
        new_diff = abs(new_earnings1 - new_earnings2)
        
        improvement = current_diff - new_diff
        return max(0, improvement)


class ScheduleOptimizer:
    """
    Optimizador principal de horarios.
    
    Orquesta todo el proceso de optimización utilizando analizadores
    y generadores especializados.
    """
    
    def __init__(self,
                 constraint_checker: Optional[ConstraintChecker] = None,
                 compensation_calculator: Optional[CompensationCalculator] = None):
        """
        Inicializa el optimizador.
        
        Args:
            constraint_checker: Verificador de restricciones (opcional)
            compensation_calculator: Calculador de compensaciones (opcional)
        """
        self.constraint_checker = constraint_checker or BasicConstraintChecker()
        self.workload_analyzer = WorkloadAnalyzer()
        self.compensation_analyzer = CompensationAnalyzer(compensation_calculator)
        self.swap_generator = SwapGenerator(self.constraint_checker)
    
    def optimize_schedule(self, schedule: Schedule, config: OptimizationConfig) -> OptimizationResult:
        """
        Optimiza un horario según la configuración especificada.
        
        Args:
            schedule: Horario a optimizar
            config: Configuración de optimización
            
        Returns:
            OptimizationResult: Resultado del proceso de optimización
        """
        initial_score = self._calculate_overall_score(schedule, config)
        
        swaps_executed = 0
        targets_achieved = []
        
        for iteration in range(config.max_iterations):
            # Generar propuestas de intercambio
            proposals = self._generate_swap_proposals(schedule, config)
            
            if not proposals:
                break  # No hay más intercambios viables
            
            # Ejecutar mejores intercambios
            iteration_swaps = 0
            current_score = self._calculate_overall_score(schedule, config)
            
            for proposal in proposals[:config.max_swaps_per_iteration]:
                if self._execute_swap(schedule, proposal):
                    new_score = self._calculate_overall_score(schedule, config)
                    
                    if new_score > current_score + config.improvement_threshold:
                        # Intercambio exitoso
                        iteration_swaps += 1
                        swaps_executed += 1
                        current_score = new_score
                    else:
                        # Revertir intercambio
                        self._revert_swap(schedule, proposal)
            
            if iteration_swaps == 0:
                break  # No se hicieron mejoras en esta iteración
            
            # Verificar metas alcanzadas
            targets_achieved = self._check_targets_achieved(schedule, config)
            if len(targets_achieved) == len(config.targets):
                break  # Todas las metas alcanzadas
        
        final_score = self._calculate_overall_score(schedule, config)
        improvement = final_score - initial_score
        
        # Verificar violaciones restantes
        from ..rules.validators import default_validator
        violations_remaining = default_validator.validate(schedule)
        
        return OptimizationResult(
            success=improvement > 0,
            iterations_performed=iteration + 1,
            swaps_executed=swaps_executed,
            initial_score=initial_score,
            final_score=final_score,
            improvement=improvement,
            targets_achieved=[target.objective for target in config.targets if target in targets_achieved],
            violations_remaining=violations_remaining
        )
    
    def _generate_swap_proposals(self, schedule: Schedule, config: OptimizationConfig) -> List[SwapProposal]:
        """Genera propuestas de intercambio según los objetivos."""
        all_proposals = []
        
        for target in config.targets:
            if target.objective == OptimizationObjective.WORKLOAD_BALANCE:
                # Generar propuestas para balance de carga
                tech_imbalances = self.workload_analyzer.identify_workload_imbalances(schedule.get_technologists())
                eng_imbalances = self.workload_analyzer.identify_workload_imbalances(schedule.get_engineers())
                
                proposals = self.swap_generator.generate_workload_balancing_swaps(schedule, tech_imbalances + eng_imbalances)
                all_proposals.extend(proposals)
            
            elif target.objective == OptimizationObjective.COMPENSATION_EQUITY:
                # Generar propuestas para equidad de compensación
                tech_comp_imbalances = self.compensation_analyzer.identify_compensation_imbalances(schedule.get_technologists())
                eng_comp_imbalances = self.compensation_analyzer.identify_compensation_imbalances(schedule.get_engineers())
                
                proposals = self.swap_generator.generate_compensation_equity_swaps(schedule, tech_comp_imbalances + eng_comp_imbalances)
                all_proposals.extend(proposals)
        
        # Eliminar duplicados y ordenar por mejora esperada
        unique_proposals = list({(p.worker1.id, p.worker2.id, p.date1, p.date2): p for p in all_proposals}.values())
        unique_proposals.sort(key=lambda p: p.expected_improvement, reverse=True)
        
        return unique_proposals
    
    def _calculate_overall_score(self, schedule: Schedule, config: OptimizationConfig) -> float:
        """Calcula el score general del horario según los objetivos."""
        total_score = 0.0
        total_weight = 0.0
        
        for target in config.targets:
            weight = target.weight
            
            if target.objective == OptimizationObjective.WORKLOAD_BALANCE:
                tech_score = self.workload_analyzer.calculate_workload_balance_score(schedule.get_technologists())
                eng_score = self.workload_analyzer.calculate_workload_balance_score(schedule.get_engineers())
                score = (tech_score + eng_score) / 2
            
            elif target.objective == OptimizationObjective.COMPENSATION_EQUITY:
                tech_score = self.compensation_analyzer.calculate_compensation_equity_score(schedule.get_technologists())
                eng_score = self.compensation_analyzer.calculate_compensation_equity_score(schedule.get_engineers())
                score = (tech_score + eng_score) / 2
            
            elif target.objective == OptimizationObjective.CONSTRAINT_COMPLIANCE:
                from ..rules.validators import default_validator
                violations = default_validator.validate(schedule)
                # Score basado en ausencia de violaciones
                score = max(0, 1.0 - len(violations) / 100.0)  # Normalizar asumiendo max 100 violaciones
            
            else:
                score = 0.5  # Score neutro para objetivos no implementados
            
            total_score += score * weight
            total_weight += weight
        
        return total_score / total_weight if total_weight > 0 else 0.0
    
    def _execute_swap(self, schedule: Schedule, proposal: SwapProposal) -> bool:
        """Ejecuta un intercambio propuesto."""
        try:
            # Remover asignaciones actuales
            schedule.remove_worker_from_shift(proposal.worker1, proposal.date1, proposal.shift1.value)
            schedule.remove_worker_from_shift(proposal.worker2, proposal.date2, proposal.shift2.value)
            
            # Asignar nuevos turnos
            success1 = schedule.assign_worker(proposal.worker1, proposal.date2, proposal.shift2.value)
            success2 = schedule.assign_worker(proposal.worker2, proposal.date1, proposal.shift1.value)
            
            return success1 and success2
        
        except Exception:
            return False
    
    def _revert_swap(self, schedule: Schedule, proposal: SwapProposal):
        """Revierte un intercambio."""
        try:
            # Remover asignaciones del intercambio
            schedule.remove_worker_from_shift(proposal.worker1, proposal.date2, proposal.shift2.value)
            schedule.remove_worker_from_shift(proposal.worker2, proposal.date1, proposal.shift1.value)
            
            # Restaurar asignaciones originales
            schedule.assign_worker(proposal.worker1, proposal.date1, proposal.shift1.value)
            schedule.assign_worker(proposal.worker2, proposal.date2, proposal.shift2.value)
        
        except Exception:
            pass  # Si no se puede revertir, continuar
    
    def _check_targets_achieved(self, schedule: Schedule, config: OptimizationConfig) -> List[OptimizationTarget]:
        """Verifica qué metas se han alcanzado."""
        achieved = []
        
        for target in config.targets:
            current_value = self._get_current_value_for_target(schedule, target)
            if target.is_achieved(current_value):
                achieved.append(target)
        
        return achieved
    
    def _get_current_value_for_target(self, schedule: Schedule, target: OptimizationTarget) -> float:
        """Obtiene el valor actual para una meta específica."""
        if target.objective == OptimizationObjective.WORKLOAD_BALANCE:
            tech_score = self.workload_analyzer.calculate_workload_balance_score(schedule.get_technologists())
            eng_score = self.workload_analyzer.calculate_workload_balance_score(schedule.get_engineers())
            return (tech_score + eng_score) / 2
        
        elif target.objective == OptimizationObjective.COMPENSATION_EQUITY:
            tech_score = self.compensation_analyzer.calculate_compensation_equity_score(schedule.get_technologists())
            eng_score = self.compensation_analyzer.calculate_compensation_equity_score(schedule.get_engineers())
            return (tech_score + eng_score) / 2
        
        elif target.objective == OptimizationObjective.CONSTRAINT_COMPLIANCE:
            from ..rules.validators import default_validator
            violations = default_validator.validate(schedule)
            return max(0, 1.0 - len(violations) / 100.0)
        
        return 0.0