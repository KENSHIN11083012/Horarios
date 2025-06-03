"""
Caso de uso: Generar nuevo horario.

Este módulo implementa la generación de horarios desde cero,
considerando restricciones laborales, distribución equitativa
y optimización de recursos humanos.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

from ...core.models import Schedule, Worker, WorkerType, ShiftType
from ...core.services import (
    ScheduleGenerator,
    GenerationConfig,
    GenerationStrategy,
    GenerationResult as CoreGenerationResult
)
from ...core.rules import default_validator
from ..ports import (
    ScheduleRepository,
    WorkerRepository,
    LoggingService,
    NotificationService,
    ConfigurationService
)


class GenerationPriority(Enum):
    """Prioridades para la generación de horarios."""
    COVERAGE_FIRST = "coverage_first"           # Priorizar cobertura completa
    EQUITY_FIRST = "equity_first"               # Priorizar equidad de compensaciones
    BALANCE_FIRST = "balance_first"             # Priorizar balance de carga
    COMPREHENSIVE = "comprehensive"              # Balance entre todos los factores


@dataclass
class ScheduleGenerationRequest:
    """Solicitud de generación de horario."""
    start_date: datetime
    end_date: datetime
    priority: GenerationPriority = GenerationPriority.COMPREHENSIVE
    max_attempts: int = 3
    require_perfect_compliance: bool = False
    preserve_worker_preferences: bool = True
    notification_recipients: Optional[List[str]] = None
    custom_config: Optional[Dict[str, Any]] = None
    
    def validate(self) -> List[str]:
        """Valida la solicitud de generación."""
        errors = []
        
        if self.start_date >= self.end_date:
            errors.append("La fecha de inicio debe ser anterior a la fecha de fin")
        
        period_days = (self.end_date - self.start_date).days + 1
        if period_days < 1:
            errors.append("El período debe ser de al menos 1 día")
        elif period_days > 366:
            errors.append("El período no puede exceder 366 días")
        
        if self.max_attempts < 1:
            errors.append("El número máximo de intentos debe ser al menos 1")
        elif self.max_attempts > 10:
            errors.append("El número máximo de intentos no puede exceder 10")
        
        if self.start_date < datetime.now().replace(hour=0, minute=0, second=0, microsecond=0):
            errors.append("No se pueden generar horarios para fechas pasadas")
        
        return errors
    
    @property
    def period_duration_days(self) -> int:
        """Duración del período en días."""
        return (self.end_date - self.start_date).days + 1
    
    @property
    def schedule_id(self) -> str:
        """Genera ID único para el horario."""
        return f"schedule_{self.start_date.strftime('%Y%m')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


@dataclass
class GenerationResult:
    """Resultado de la generación de horario."""
    success: bool
    schedule_id: Optional[str]
    schedule: Optional[Schedule]
    generation_time: float
    attempts_made: int
    coverage_percentage: float
    violations: List[str]
    warnings: List[str]
    stats: Dict[str, Any]
    message: str
    
    @property
    def is_fully_compliant(self) -> bool:
        """Indica si el horario cumple completamente con las restricciones."""
        return len(self.violations) == 0
    
    @property
    def quality_score(self) -> float:
        """Calcula un puntaje de calidad del horario (0-100)."""
        if not self.success:
            return 0.0
        
        # Factores de calidad
        coverage_factor = self.coverage_percentage / 100.0
        compliance_factor = max(0, 1 - (len(self.violations) / 50.0))  # Penalizar violaciones
        balance_factor = self.stats.get('workload_balance', 0.8)
        equity_factor = self.stats.get('compensation_equity', 0.8)
        
        # Puntaje ponderado
        quality = (coverage_factor * 0.4 + 
                  compliance_factor * 0.3 + 
                  balance_factor * 0.15 + 
                  equity_factor * 0.15)
        
        return min(100.0, quality * 100.0)
    
    @classmethod
    def success_result(cls, schedule_id: str, schedule: Schedule, 
                      core_result: CoreGenerationResult, 
                      generation_time: float, attempts: int) -> 'GenerationResult':
        """Crea un resultado exitoso."""
        return cls(
            success=True,
            schedule_id=schedule_id,
            schedule=schedule,
            generation_time=generation_time,
            attempts_made=attempts,
            coverage_percentage=core_result.coverage_percentage,
            violations=core_result.violations,
            warnings=core_result.warnings,
            stats=core_result.stats,
            message="Horario generado exitosamente"
        )
    
    @classmethod
    def failure_result(cls, message: str, attempts: int = 0, 
                      errors: List[str] = None) -> 'GenerationResult':
        """Crea un resultado de fallo."""
        return cls(
            success=False,
            schedule_id=None,
            schedule=None,
            generation_time=0.0,
            attempts_made=attempts,
            coverage_percentage=0.0,
            violations=errors or [],
            warnings=[],
            stats={},
            message=message
        )


class GenerateScheduleUseCase:
    """
    Caso de uso para generar horarios completos.
    
    Este caso de uso coordina la generación de un horario completo
    desde cero, aplicando todas las reglas de negocio y optimizaciones.
    """
    
    def __init__(self,
                 schedule_repository: ScheduleRepository,
                 worker_repository: WorkerRepository,
                 configuration_service: ConfigurationService,
                 logging_service: Optional[LoggingService] = None,
                 notification_service: Optional[NotificationService] = None):
        """
        Inicializa el caso de uso.
        
        Args:
            schedule_repository: Repositorio de horarios
            worker_repository: Repositorio de trabajadores
            configuration_service: Servicio de configuración
            logging_service: Servicio de logging (opcional)
            notification_service: Servicio de notificaciones (opcional)
        """
        self.schedule_repository = schedule_repository
        self.worker_repository = worker_repository
        self.configuration_service = configuration_service
        self.logging_service = logging_service
        self.notification_service = notification_service
        
        # Inicializar generador
        self.schedule_generator = ScheduleGenerator()
    
    def execute(self, request: ScheduleGenerationRequest) -> GenerationResult:
        """
        Ejecuta la generación de horario.
        
        Args:
            request: Solicitud de generación
            
        Returns:
            GenerationResult: Resultado de la generación
        """
        start_time = datetime.now()
        
        try:
            # 1. Validar solicitud
            validation_errors = request.validate()
            if validation_errors:
                return GenerationResult.failure_result(
                    "Solicitud inválida: " + "; ".join(validation_errors),
                    errors=validation_errors
                )
            
            # 2. Verificar disponibilidad de trabajadores
            available_workers = self.worker_repository.get_available_workers(
                request.start_date, request.end_date
            )
            
            if not self._validate_worker_availability(available_workers, request):
                return GenerationResult.failure_result(
                    "No hay suficientes trabajadores disponibles para el período solicitado"
                )
            
            # 3. Log inicio
            if self.logging_service:
                self.logging_service.log_generation_started(
                    request.schedule_id, request.start_date, request.end_date
                )
            
            # 4. Crear configuración de generación
            generation_config = self._create_generation_config(request, available_workers)
            
            # 5. Intentar generar horario (con reintentos)
            best_result = None
            best_schedule = None
            
            for attempt in range(1, request.max_attempts + 1):
                if self.logging_service:
                    self.logging_service.log_info(f"Intento de generación {attempt}/{request.max_attempts}")
                
                # Generar horario
                schedule = Schedule(request.start_date, request.end_date, available_workers)
                core_result = self.schedule_generator.generate_schedule(schedule, generation_config)
                
                if core_result.success:
                    # Validar resultado
                    violations = default_validator.validate(schedule)
                    
                    # Evaluar calidad
                    if self._is_acceptable_quality(core_result, violations, request):
                        best_result = core_result
                        best_schedule = schedule
                        
                        # Si es perfecta o lo suficientemente buena, parar
                        if not violations or not request.require_perfect_compliance:
                            break
                    elif best_result is None or core_result.coverage_percentage > best_result.coverage_percentage:
                        # Guardar como mejor resultado hasta ahora
                        best_result = core_result
                        best_schedule = schedule
            
            # 6. Verificar si tenemos un resultado aceptable
            if not best_result or not best_schedule:
                return GenerationResult.failure_result(
                    f"No se pudo generar un horario aceptable después de {request.max_attempts} intentos",
                    attempts=request.max_attempts
                )
            
            # 7. Validación final
            final_violations = default_validator.validate(best_schedule)
            
            if request.require_perfect_compliance and final_violations:
                return GenerationResult.failure_result(
                    f"El horario generado no cumple con el requisito de cumplimiento perfecto. "
                    f"Violaciones encontradas: {len(final_violations)}",
                    attempts=request.max_attempts,
                    errors=final_violations
                )
            
            # 8. Guardar horario
            schedule_saved = self.schedule_repository.save_schedule(
                best_schedule, request.schedule_id
            )
            
            if not schedule_saved:
                return GenerationResult.failure_result(
                    "Error al guardar el horario generado"
                )
            
            # 9. Crear resultado final
            generation_time = (datetime.now() - start_time).total_seconds()
            result = GenerationResult.success_result(
                request.schedule_id, best_schedule, best_result, 
                generation_time, request.max_attempts
            )
            
            # 10. Log finalización
            if self.logging_service:
                self.logging_service.log_generation_completed(
                    request.schedule_id, result.quality_score, len(final_violations)
                )
            
            # 11. Enviar notificaciones
            if self.notification_service and request.notification_recipients:
                self._send_notifications(result, request.notification_recipients)
            
            return result
            
        except Exception as e:
            # Log error
            if self.logging_service:
                self.logging_service.log_error("schedule_generation", e, {
                    "schedule_id": request.schedule_id,
                    "start_date": request.start_date.isoformat(),
                    "end_date": request.end_date.isoformat()
                })
            
            return GenerationResult.failure_result(
                f"Error inesperado durante la generación: {str(e)}"
            )
    
    def get_generation_preview(self, request: ScheduleGenerationRequest) -> Dict[str, Any]:
        """
        Obtiene una vista previa de los recursos necesarios para generar el horario.
        
        Args:
            request: Solicitud de generación
            
        Returns:
            Dict: Información de vista previa
        """
        try:
            # Validar básicamente
            validation_errors = request.validate()
            if validation_errors:
                return {"error": "Solicitud inválida", "details": validation_errors}
            
            # Obtener trabajadores disponibles
            available_workers = self.worker_repository.get_available_workers(
                request.start_date, request.end_date
            )
            
            # Calcular estadísticas básicas
            period_days = request.period_duration_days
            total_shifts_needed = period_days * 3  # 3 turnos por día
            
            technologists = [w for w in available_workers if w.worker_type == WorkerType.TECHNOLOGIST]
            engineers = [w for w in available_workers if w.worker_type == WorkerType.ENGINEER]
            
            # Calcular capacidad
            tech_capacity = len(technologists) * period_days
            eng_capacity = len(engineers) * period_days
            
            # Obtener configuración de requerimientos
            config = self.configuration_service.get_shift_requirements()
            tech_needed_per_day = sum(config.technologists_per_shift.values())
            eng_needed_per_day = len(config.technologists_per_shift)  # 1 ingeniero por turno
            
            total_tech_needed = tech_needed_per_day * period_days
            total_eng_needed = eng_needed_per_day * period_days
            
            # Calcular factibilidad
            tech_feasible = tech_capacity >= total_tech_needed
            eng_feasible = eng_capacity >= total_eng_needed
            
            # Identificar posibles problemas
            issues = []
            if not tech_feasible:
                shortage = total_tech_needed - tech_capacity
                issues.append(f"Faltan {shortage} turnos de tecnólogos para cubrir el período")
            
            if not eng_feasible:
                shortage = total_eng_needed - eng_capacity
                issues.append(f"Faltan {shortage} turnos de ingenieros para cubrir el período")
            
            # Calcular complejidad estimada
            complexity_factors = {
                "period_length": min(1.0, period_days / 31),  # Normalizado por mes
                "worker_count": min(1.0, len(available_workers) / 20),  # Normalizado por equipo típico
                "coverage_ratio": min(1.0, (tech_capacity + eng_capacity) / (total_tech_needed + total_eng_needed)),
                "weekend_count": len([d for d in range(period_days) 
                                    if (request.start_date + timedelta(days=d)).weekday() >= 5])
            }
            
            complexity_score = sum(complexity_factors.values()) / len(complexity_factors)
            complexity_level = ("Baja" if complexity_score < 0.4 else 
                              "Media" if complexity_score < 0.7 else "Alta")
            
            return {
                "feasible": tech_feasible and eng_feasible,
                "resource_summary": {
                    "available_technologists": len(technologists),
                    "available_engineers": len(engineers),
                    "total_shifts_needed": total_shifts_needed,
                    "period_days": period_days
                },
                "capacity_analysis": {
                    "technologists": {
                        "capacity": tech_capacity,
                        "needed": total_tech_needed,
                        "utilization": total_tech_needed / tech_capacity if tech_capacity > 0 else float('inf')
                    },
                    "engineers": {
                        "capacity": eng_capacity,
                        "needed": total_eng_needed,
                        "utilization": total_eng_needed / eng_capacity if eng_capacity > 0 else float('inf')
                    }
                },
                "complexity": {
                    "level": complexity_level,
                    "score": complexity_score,
                    "factors": complexity_factors
                },
                "potential_issues": issues,
                "estimated_generation_time": self._estimate_generation_time(request, complexity_score)
            }
            
        except Exception as e:
            return {"error": f"Error al generar vista previa: {str(e)}"}
    
    def _validate_worker_availability(self, workers: List[Worker], request: ScheduleGenerationRequest) -> bool:
        """Valida que hay suficientes trabajadores para el período."""
        technologists = [w for w in workers if w.worker_type == WorkerType.TECHNOLOGIST]
        engineers = [w for w in workers if w.worker_type == WorkerType.ENGINEER]
        
        # Obtener configuración mínima
        config = self.configuration_service.get_shift_requirements()
        
        # Verificar mínimos absolutos
        min_techs = max(config.technologists_per_shift.values())
        min_engs = 1  # Al menos 1 ingeniero debe estar disponible
        
        return len(technologists) >= min_techs and len(engineers) >= min_engs
    
    def _create_generation_config(self, request: ScheduleGenerationRequest, 
                                workers: List[Worker]) -> GenerationConfig:
        """Crea la configuración de generación basada en la solicitud."""
        # Obtener configuración base del sistema
        system_config = self.configuration_service.get_generation_config()
        
        # Personalizar según prioridad solicitada
        if request.priority == GenerationPriority.COVERAGE_FIRST:
            strategy = GenerationStrategy.COVERAGE_FOCUSED
        elif request.priority == GenerationPriority.EQUITY_FIRST:
            strategy = GenerationStrategy.EQUITY_FOCUSED
        elif request.priority == GenerationPriority.BALANCE_FIRST:
            strategy = GenerationStrategy.BALANCE_FOCUSED
        else:
            strategy = GenerationStrategy.COMPREHENSIVE
        
        # Crear configuración
        config = GenerationConfig(
            strategy=strategy,
            workers=workers,
            period_start=request.start_date,
            period_end=request.end_date,
            max_iterations=system_config.max_iterations,
            target_coverage=0.95 if request.require_perfect_compliance else 0.85,
            preserve_preferences=request.preserve_worker_preferences
        )
        
        # Aplicar configuración personalizada si se proporciona
        if request.custom_config:
            config.update_from_dict(request.custom_config)
        
        return config
    
    def _is_acceptable_quality(self, result: CoreGenerationResult, 
                             violations: List[str], 
                             request: ScheduleGenerationRequest) -> bool:
        """Determina si la calidad del resultado es aceptable."""
        # Criterios básicos
        min_coverage = 0.95 if request.require_perfect_compliance else 0.80
        max_violations = 0 if request.require_perfect_compliance else 10
        
        return (result.coverage_percentage >= min_coverage * 100 and 
                len(violations) <= max_violations)
    
    def _estimate_generation_time(self, request: ScheduleGenerationRequest, 
                                complexity_score: float) -> str:
        """Estima el tiempo de generación basado en la complejidad."""
        base_time = 30  # segundos base
        complexity_multiplier = 1 + (complexity_score * 2)  # 1x a 3x
        period_multiplier = 1 + (request.period_duration_days / 365)  # Factor por duración
        
        estimated_seconds = base_time * complexity_multiplier * period_multiplier
        
        if estimated_seconds < 60:
            return f"{int(estimated_seconds)} segundos"
        elif estimated_seconds < 3600:
            return f"{int(estimated_seconds / 60)} minutos"
        else:
            return f"{estimated_seconds / 3600:.1f} horas"
    
    def _send_notifications(self, result: GenerationResult, recipients: List[str]):
        """Envía notificaciones sobre el resultado de la generación."""
        if not self.notification_service:
            return
        
        try:
            if result.success:
                schedule_info = {
                    "schedule_id": result.schedule_id,
                    "period": f"{result.schedule.start_date.strftime('%d/%m/%Y')} - {result.schedule.end_date.strftime('%d/%m/%Y')}",
                    "coverage_percentage": result.coverage_percentage,
                    "quality_score": result.quality_score,
                    "generation_time": result.generation_time,
                    "violations_count": len(result.violations),
                    "workers_count": len(result.schedule.get_all_workers())
                }
                
                self.notification_service.send_schedule_generated(schedule_info, recipients)
                
                if result.violations:
                    self.notification_service.send_validation_report(result.violations, recipients)
                    
                if result.warnings:
                    self.notification_service.send_warning_report(result.warnings, recipients)
            else:
                error_info = {
                    "operation": "schedule_generation",
                    "message": result.message,
                    "attempts_made": result.attempts_made,
                    "errors": result.violations
                }
                
                self.notification_service.send_error_alert(error_info, recipients)
                
        except Exception as e:
            if self.logging_service:
                self.logging_service.log_error("send_generation_notifications", e, {
                    "schedule_id": result.schedule_id,
                    "recipients": recipients
                })