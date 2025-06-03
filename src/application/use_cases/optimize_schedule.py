"""
Caso de uso: Optimizar horario existente.

Este módulo implementa la optimización de horarios ya generados,
mejorando aspectos como balance de carga, equidad de compensaciones
y cumplimiento de restricciones.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


from ...core.models import Schedule, Worker
from ...core.services import (
    ScheduleOptimizer,
    OptimizationConfig,
    OptimizationObjective,
    OptimizationResult as CoreOptimizationResult
)
from ...core.rules import default_validator
from ..ports import (
    ScheduleRepository,
    LoggingService,
    NotificationService,
    CacheService
)


class OptimizationGoal(Enum):
    """Objetivos de optimización disponibles."""
    BALANCE_WORKLOAD = "balance_workload"
    IMPROVE_EQUITY = "improve_equity"
    REDUCE_VIOLATIONS = "reduce_violations"
    COMPREHENSIVE = "comprehensive"


@dataclass
class OptimizationRequest:
    """Solicitud de optimización de horario."""
    schedule_id: str
    goals: List[OptimizationGoal]
    max_iterations: int = 10
    improvement_threshold: float = 0.01
    preserve_critical_assignments: bool = True
    notification_recipients: Optional[List[str]] = None
    
    def validate(self) -> List[str]:
        """Valida la solicitud de optimización."""
        errors = []
        
        if not self.schedule_id.strip():
            errors.append("El ID del horario es requerido")
        
        if not self.goals:
            errors.append("Debe especificar al menos un objetivo de optimización")
        
        if self.max_iterations < 1:
            errors.append("El número máximo de iteraciones debe ser al menos 1")
        elif self.max_iterations > 50:
            errors.append("El número máximo de iteraciones no puede exceder 50")
        
        if self.improvement_threshold < 0:
            errors.append("El umbral de mejora no puede ser negativo")
        elif self.improvement_threshold > 1:
            errors.append("El umbral de mejora no puede ser mayor a 1")
        
        return errors


@dataclass
class OptimizationResult:
    """Resultado de la optimización de horario."""
    success: bool
    schedule_id: str
    original_schedule: Optional[Schedule]
    optimized_schedule: Optional[Schedule]
    improvements: Dict[str, float]
    iterations_performed: int
    swaps_executed: int
    initial_violations: List[str]
    final_violations: List[str]
    optimization_time: float
    message: str
    
    @property
    def violations_reduced(self) -> int:
        """Número de violaciones reducidas."""
        return len(self.initial_violations) - len(self.final_violations)
    
    @property
    def overall_improvement(self) -> float:
        """Mejora general obtenida."""
        if not self.improvements:
            return 0.0
        return sum(self.improvements.values()) / len(self.improvements)
    
    @classmethod
    def success_result(cls, schedule_id: str, original: Schedule, optimized: Schedule,
                      core_result: CoreOptimizationResult, initial_violations: List[str]) -> 'OptimizationResult':
        """Crea un resultado exitoso."""
        return cls(
            success=True,
            schedule_id=schedule_id,
            original_schedule=original,
            optimized_schedule=optimized,
            improvements={"overall": core_result.improvement_percentage},
            iterations_performed=core_result.iterations_performed,
            swaps_executed=core_result.swaps_executed,
            initial_violations=initial_violations,
            final_violations=core_result.violations_remaining,
            optimization_time=0.0,  # Se calculará externamente
            message="Optimización completada exitosamente"
        )
    
    @classmethod
    def failure_result(cls, schedule_id: str, message: str, errors: List[str] = None) -> 'OptimizationResult':
        """Crea un resultado de fallo."""
        return cls(
            success=False,
            schedule_id=schedule_id,
            original_schedule=None,
            optimized_schedule=None,
            improvements={},
            iterations_performed=0,
            swaps_executed=0,
            initial_violations=errors or [],
            final_violations=[],
            optimization_time=0.0,
            message=message
        )


class OptimizeScheduleUseCase:
    """
    Caso de uso para optimizar horarios existentes.
    
    Este caso de uso toma un horario existente y lo mejora
    según los objetivos especificados.
    """
    
    def __init__(self,
                 schedule_repository: ScheduleRepository,
                 logging_service: Optional[LoggingService] = None,
                 notification_service: Optional[NotificationService] = None,
                 cache_service: Optional[CacheService] = None):
        """
        Inicializa el caso de uso.
        
        Args:
            schedule_repository: Repositorio de horarios
            logging_service: Servicio de logging (opcional)
            notification_service: Servicio de notificaciones (opcional)
            cache_service: Servicio de caché (opcional)
        """
        self.schedule_repository = schedule_repository
        self.logging_service = logging_service
        self.notification_service = notification_service
        self.cache_service = cache_service
        
        # Inicializar optimizador
        self.schedule_optimizer = ScheduleOptimizer()
    
    def execute(self, request: OptimizationRequest) -> OptimizationResult:
        """
        Ejecuta la optimización de horario.
        
        Args:
            request: Solicitud de optimización
            
        Returns:
            OptimizationResult: Resultado de la optimización
        """
        start_time = datetime.now()
        
        try:
            # 1. Validar solicitud
            validation_errors = request.validate()
            if validation_errors:
                return OptimizationResult.failure_result(
                    request.schedule_id, "Solicitud inválida", validation_errors
                )
            
            # 2. Cargar horario original
            original_schedule = self.schedule_repository.load_schedule(request.schedule_id)
            if not original_schedule:
                return OptimizationResult.failure_result(
                    request.schedule_id, "Horario no encontrado"
                )
            
            # 3. Log inicio
            if self.logging_service:
                self.logging_service.log_optimization_performed(
                    request.schedule_id, 0.0  # Inicio
                )
            
            # 4. Validar horario original
            initial_violations = default_validator.validate(original_schedule)
            
            # 5. Verificar caché si está disponible
            cached_result = self._check_cache(request) if self.cache_service else None
            if cached_result:
                return cached_result
            
            # 6. Crear configuración de optimización
            optimization_config = self._create_optimization_config(request)
            
            # 7. Hacer copia del horario para optimizar
            schedule_to_optimize = self._create_schedule_copy(original_schedule)
            
            # 8. Ejecutar optimización
            core_result = self.schedule_optimizer.optimize_schedule(
                schedule_to_optimize, optimization_config
            )
            
            # 9. Verificar si hubo mejora
            if not core_result.success or core_result.improvement <= 0:
                return OptimizationResult.failure_result(
                    request.schedule_id,
                    "No se lograron mejoras significativas en la optimización"
                )
            
            # 10. Generar nuevo ID y guardar horario optimizado
            optimized_schedule_id = self._generate_optimized_schedule_id(request.schedule_id)
            saved = self.schedule_repository.save_schedule(schedule_to_optimize, optimized_schedule_id)
            
            if not saved:
                return OptimizationResult.failure_result(
                    request.schedule_id, "Error al guardar el horario optimizado"
                )
            
            # 11. Crear resultado
            optimization_time = (datetime.now() - start_time).total_seconds()
            result = OptimizationResult.success_result(
                optimized_schedule_id, original_schedule, schedule_to_optimize,
                core_result, initial_violations
            )
            result.optimization_time = optimization_time
            
            # 12. Actualizar horario original con referencia al optimizado
            # (Opcional: mantener histórico de optimizaciones)
            
            # 13. Guardar en caché si está disponible
            if self.cache_service:
                self._save_to_cache(request, result)
            
            # 14. Log finalización
            if self.logging_service:
                self.logging_service.log_optimization_performed(
                    optimized_schedule_id, core_result.improvement_percentage
                )
            
            # 15. Enviar notificaciones
            if self.notification_service and request.notification_recipients:
                self._send_notifications(result, request.notification_recipients)
            
            return result
            
        except Exception as e:
            # Log error
            if self.logging_service:
                self.logging_service.log_error("schedule_optimization", e, {
                    "schedule_id": request.schedule_id
                })
            
            return OptimizationResult.failure_result(
                request.schedule_id,
                f"Error inesperado durante la optimización: {str(e)}"
            )
    
    def get_optimization_preview(self, request: OptimizationRequest) -> Dict[str, Any]:
        """
        Obtiene una vista previa de lo que la optimización podría mejorar.
        
        Args:
            request: Solicitud de optimización
            
        Returns:
            Dict: Información de vista previa
        """
        try:
            # Cargar horario
            schedule = self.schedule_repository.load_schedule(request.schedule_id)
            if not schedule:
                return {"error": "Horario no encontrado"}
            
            # Analizar estado actual
            violations = default_validator.validate(schedule)
            
            # Analizar métricas actuales
            from ...core.services import WorkloadAnalyzer, CompensationAnalyzer
            workload_analyzer = WorkloadAnalyzer()
            compensation_analyzer = CompensationAnalyzer()
            
            tech_workload_score = workload_analyzer.calculate_workload_balance_score(schedule.get_technologists())
            eng_workload_score = workload_analyzer.calculate_workload_balance_score(schedule.get_engineers())
            
            tech_equity_score = compensation_analyzer.calculate_compensation_equity_score(schedule.get_technologists())
            eng_equity_score = compensation_analyzer.calculate_compensation_equity_score(schedule.get_engineers())
            
            # Identificar oportunidades de mejora
            opportunities = []
            if tech_workload_score < 0.8 or eng_workload_score < 0.8:
                opportunities.append("Balance de carga de trabajo")
            
            if tech_equity_score < 0.8 or eng_equity_score < 0.8:
                opportunities.append("Equidad de compensaciones")
            
            if violations:
                opportunities.append("Cumplimiento de restricciones")
            
            return {
                "current_state": {
                    "violations_count": len(violations),
                    "workload_balance": {
                        "technologists": tech_workload_score,
                        "engineers": eng_workload_score
                    },
                    "compensation_equity": {
                        "technologists": tech_equity_score,
                        "engineers": eng_equity_score
                    }
                },
                "improvement_opportunities": opportunities,
                "estimated_impact": "Medio" if len(opportunities) <= 2 else "Alto"
            }
            
        except Exception as e:
            return {"error": f"Error al generar vista previa: {str(e)}"}
    
    def _create_optimization_config(self, request: OptimizationRequest) -> OptimizationConfig:
        """Crea la configuración de optimización basada en la solicitud."""
        # Mapear objetivos a configuración
        if OptimizationGoal.COMPREHENSIVE in request.goals:
            config = OptimizationConfig.comprehensive()
        elif OptimizationGoal.BALANCE_WORKLOAD in request.goals:
            config = OptimizationConfig.balanced_workload()
        elif OptimizationGoal.IMPROVE_EQUITY in request.goals:
            config = OptimizationConfig.compensation_equity()
        else:
            # Configuración personalizada basada en objetivos específicos
            targets = []
            
            if OptimizationGoal.BALANCE_WORKLOAD in request.goals:
                from ...core.services import OptimizationTarget
                targets.append(OptimizationTarget(
                    objective=OptimizationObjective.WORKLOAD_BALANCE,
                    target_value=0.90,
                    weight=0.5
                ))
            
            if OptimizationGoal.IMPROVE_EQUITY in request.goals:
                from ...core.services import OptimizationTarget
                targets.append(OptimizationTarget(
                    objective=OptimizationObjective.COMPENSATION_EQUITY,
                    target_value=0.10,
                    weight=0.5
                ))
            
            if OptimizationGoal.REDUCE_VIOLATIONS in request.goals:
                from ...core.services import op
                targets.append(OptimizationTarget(
                    objective=OptimizationObjective.CONSTRAINT_COMPLIANCE,
                    target_value=1.0,
                    weight=0.3
                ))
            
            config = OptimizationConfig(
                targets=targets,
                max_iterations=request.max_iterations,
                improvement_threshold=request.improvement_threshold
            )
        
        # Ajustar parámetros específicos
        config.max_iterations = request.max_iterations
        config.improvement_threshold = request.improvement_threshold
        
        return config
    
    def _create_schedule_copy(self, original: Schedule) -> Schedule:
        """Crea una copia profunda del horario para optimización."""
        # Crear nueva instancia de horario
        workers_copy = []
        
        for worker in original.get_all_workers():
            worker_copy = Worker(worker.id, worker.worker_type)
            worker_copy.shifts = worker.shifts.copy()
            worker_copy.days_off = worker.days_off.copy()
            worker_copy.earnings = worker.earnings
            workers_copy.append(worker_copy)
        
        # Crear nuevo horario
        new_schedule = Schedule(original.start_date, original.end_date, workers_copy)
        
        # Reconstruir asignaciones
        for worker_copy in workers_copy:
            for shift_date, shift_type in worker_copy.shifts:
                new_schedule.assign_worker(worker_copy, shift_date, shift_type)
        
        return new_schedule
    
    def _generate_optimized_schedule_id(self, original_id: str) -> str:
        """Genera ID para el horario optimizado."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{original_id}_optimized_{timestamp}"
    
    def _check_cache(self, request: OptimizationRequest) -> Optional[OptimizationResult]:
        """Verifica si existe un resultado en caché."""
        if not self.cache_service:
            return None
        
        cache_key = self._generate_cache_key(request)
        cached_data = self.cache_service.get(cache_key)
        
        if cached_data:
            # Verificar si los horarios aún existen
            original_id = cached_data.get("original_schedule_id")
            optimized_id = cached_data.get("optimized_schedule_id")
            
            if (original_id and optimized_id and 
                self.schedule_repository.exists(original_id) and 
                self.schedule_repository.exists(optimized_id)):
                
                # Reconstruir resultado desde caché
                original = self.schedule_repository.load_schedule(original_id)
                optimized = self.schedule_repository.load_schedule(optimized_id)
                
                if original and optimized:
                    result = OptimizationResult.success_result(
                        optimized_id, original, optimized, 
                        # Crear core_result básico desde caché
                        CoreOptimizationResult(
                            success=True,
                            iterations_performed=cached_data.get("iterations", 0),
                            swaps_executed=cached_data.get("swaps", 0),
                            initial_score=cached_data.get("initial_score", 0),
                            final_score=cached_data.get("final_score", 0),
                            improvement=cached_data.get("improvement", 0),
                            targets_achieved=[],
                            violations_remaining=cached_data.get("final_violations", [])
                        ),
                        cached_data.get("initial_violations", [])
                    )
                    result.optimization_time = cached_data.get("optimization_time", 0.0)
                    return result
        
        return None
    
    def _save_to_cache(self, request: OptimizationRequest, result: OptimizationResult):
        """Guarda el resultado en caché."""
        if not self.cache_service or not result.success:
            return
        
        cache_key = self._generate_cache_key(request)
        cache_data = {
            "original_schedule_id": request.schedule_id,
            "optimized_schedule_id": result.schedule_id,
            "improvements": result.improvements,
            "iterations": result.iterations_performed,
            "swaps": result.swaps_executed,
            "initial_violations": result.initial_violations,
            "final_violations": result.final_violations,
            "optimization_time": result.optimization_time,
            "timestamp": datetime.now().isoformat()
        }
        
        # Caché por 2 horas
        self.cache_service.set(cache_key, cache_data, ttl=7200)
    
    def _generate_cache_key(self, request: OptimizationRequest) -> str:
        """Genera clave de caché para la solicitud."""
        goals_str = "_".join(goal.value for goal in request.goals)
        return f"schedule_opt_{request.schedule_id}_{goals_str}_{request.max_iterations}"
    
    def _send_notifications(self, result: OptimizationResult, recipients: List[str]):
        """Envía notificaciones sobre el resultado."""
        if not self.notification_service:
            return
        
        try:
            if result.success:
                optimization_info = {
                    "original_schedule_id": result.original_schedule.get_summary_stats() if result.original_schedule else {},
                    "optimized_schedule_id": result.schedule_id,
                    "improvement_percentage": result.overall_improvement,
                    "violations_reduced": result.violations_reduced,
                    "swaps_executed": result.swaps_executed,
                    "optimization_time": result.optimization_time
                }
                
                # Usar el método de horario generado como base
                self.notification_service.send_schedule_generated(optimization_info, recipients)
                
                if result.final_violations:
                    self.notification_service.send_validation_report(result.final_violations, recipients)
            else:
                error_info = {
                    "operation": "schedule_optimization",
                    "schedule_id": result.schedule_id,
                    "message": result.message,
                    "errors": result.initial_violations
                }
                
                self.notification_service.send_error_alert(error_info, recipients)
                
        except Exception as e:
            if self.logging_service:
                self.logging_service.log_error("send_optimization_notifications", e, {
                    "schedule_id": result.schedule_id,
                    "recipients": recipients
                })