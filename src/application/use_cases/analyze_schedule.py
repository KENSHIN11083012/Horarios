"""
Caso de uso: Analizar horario existente.

Este módulo implementa el análisis completo de horarios generados,
proporcionando métricas, estadísticas, insights y recomendaciones
de mejora.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

from ...core.models import Schedule
from ...core.services import (
    ScheduleAnalyzer,
    AnalysisType,
    ScheduleAnalysisReport
)
from ...core.rules import default_validator
from ..ports import (
    ScheduleRepository,
    LoggingService,
    NotificationService,
    CacheService
)


class AnalysisScope(Enum):
    """Alcance del análisis disponible."""
    BASIC = "basic"                     # Métricas básicas y coverage
    WORKLOAD = "workload"               # Análisis de carga de trabajo
    COMPLIANCE = "compliance"           # Cumplimiento de restricciones
    EQUITY = "equity"                   # Equidad de compensaciones
    COMPREHENSIVE = "comprehensive"     # Análisis completo


@dataclass
class AnalysisRequest:
    """Solicitud de análisis de horario."""
    schedule_id: str
    scope: AnalysisScope = AnalysisScope.COMPREHENSIVE
    include_recommendations: bool = True
    compare_with_schedule_id: Optional[str] = None
    export_format: Optional[str] = None  # "json", "excel", "pdf"
    notification_recipients: Optional[List[str]] = None
    
    def validate(self) -> List[str]:
        """Valida la solicitud de análisis."""
        errors = []
        
        if not self.schedule_id.strip():
            errors.append("El ID del horario es requerido")
        
        if self.compare_with_schedule_id and not self.compare_with_schedule_id.strip():
            errors.append("El ID del horario de comparación no puede estar vacío")
        
        if self.export_format and self.export_format not in ["json", "excel", "pdf"]:
            errors.append("Formato de exportación debe ser: json, excel o pdf")
        
        return errors


@dataclass
class AnalysisResult:
    """Resultado del análisis de horario."""
    success: bool
    schedule_id: str
    analysis_report: Optional[ScheduleAnalysisReport]
    comparison_data: Optional[Dict[str, Any]]
    analysis_time: float
    cached: bool
    export_path: Optional[str]
    message: str
    warnings: List[str]
    
    @property
    def overall_score(self) -> float:
        """Score general del horario analizado."""
        if not self.analysis_report:
            return 0.0
        return self.analysis_report.overall_quality_score
    
    @property
    def key_insights(self) -> List[str]:
        """Insights principales del análisis."""
        if not self.analysis_report:
            return []
        
        insights = []
        
        # Coverage insight
        coverage = self.analysis_report.coverage_analysis.coverage_percentage
        if coverage < 90:
            insights.append(f"Cobertura de turnos baja: {coverage:.1f}%")
        elif coverage >= 98:
            insights.append(f"Excelente cobertura de turnos: {coverage:.1f}%")
        
        # Violations insight
        violations_count = len(self.analysis_report.constraint_violations)
        if violations_count > 10:
            insights.append(f"Alto número de violaciones: {violations_count}")
        elif violations_count == 0:
            insights.append("Cumplimiento perfecto de restricciones")
        
        # Workload balance insight
        tech_balance = self.analysis_report.technologist_stats.workload_balance_score
        if tech_balance < 0.7:
            insights.append("Desequilibrio significativo en carga de tecnólogos")
        
        # Equity insight  
        tech_equity = self.analysis_report.technologist_stats.compensation_equity_score
        if tech_equity < 0.8:
            insights.append("Inequidad en compensaciones de tecnólogos")
        
        return insights
    
    @classmethod
    def success_result(cls, schedule_id: str, report: ScheduleAnalysisReport, 
                      analysis_time: float, cached: bool = False) -> 'AnalysisResult':
        """Crea un resultado exitoso."""
        return cls(
            success=True,
            schedule_id=schedule_id,
            analysis_report=report,
            comparison_data=None,
            analysis_time=analysis_time,
            cached=cached,
            export_path=None,
            message="Análisis completado exitosamente",
            warnings=[]
        )
    
    @classmethod
    def failure_result(cls, schedule_id: str, message: str, 
                      warnings: List[str] = None) -> 'AnalysisResult':
        """Crea un resultado de fallo."""
        return cls(
            success=False,
            schedule_id=schedule_id,
            analysis_report=None,
            comparison_data=None,
            analysis_time=0.0,
            cached=False,
            export_path=None,
            message=message,
            warnings=warnings or []
        )


class AnalyzeScheduleUseCase:
    """
    Caso de uso para analizar horarios existentes.
    
    Este caso de uso coordina el análisis completo de un horario,
    proporcionando métricas, insights y recomendaciones.
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
        
        # Inicializar analizador
        self.schedule_analyzer = ScheduleAnalyzer()
    
    def execute(self, request: AnalysisRequest) -> AnalysisResult:
        """
        Ejecuta el análisis de horario.
        
        Args:
            request: Solicitud de análisis
            
        Returns:
            AnalysisResult: Resultado del análisis
        """
        start_time = datetime.now()
        
        try:
            # 1. Validar solicitud
            validation_errors = request.validate()
            if validation_errors:
                return AnalysisResult.failure_result(
                    request.schedule_id, 
                    "Solicitud inválida: " + "; ".join(validation_errors)
                )
            
            # 2. Verificar caché
            cached_result = self._check_cache(request) if self.cache_service else None
            if cached_result:
                if self.logging_service:
                    self.logging_service.log_info(f"Análisis obtenido desde caché: {request.schedule_id}")
                return cached_result
            
            # 3. Cargar horario
            schedule = self.schedule_repository.load_schedule(request.schedule_id)
            if not schedule:
                return AnalysisResult.failure_result(
                    request.schedule_id, "Horario no encontrado"
                )
            
            # 4. Log inicio del análisis
            if self.logging_service:
                self.logging_service.log_info(f"Iniciando análisis de horario: {request.schedule_id}")
            
            # 5. Determinar tipos de análisis según el alcance
            analysis_types = self._get_analysis_types_for_scope(request.scope)
            
            # 6. Ejecutar análisis principal
            analysis_report = self.schedule_analyzer.analyze_schedule(schedule, analysis_types)
            
            # 7. Análisis de comparación si se solicita
            comparison_data = None
            if request.compare_with_schedule_id:
                comparison_data = self._perform_comparison_analysis(
                    schedule, request.compare_with_schedule_id
                )
            
            # 8. Crear resultado
            analysis_time = (datetime.now() - start_time).total_seconds()
            result = AnalysisResult.success_result(
                request.schedule_id, analysis_report, analysis_time
            )
            result.comparison_data = comparison_data
            
            # 9. Exportar si se solicita
            if request.export_format:
                export_path = self._export_analysis(result, request.export_format)
                result.export_path = export_path
            
            # 10. Guardar en caché
            if self.cache_service:
                self._save_to_cache(request, result)
            
            # 11. Log finalización
            if self.logging_service:
                self.logging_service.log_info(
                    f"Análisis completado: {request.schedule_id}, "
                    f"Score: {result.overall_score:.2f}, "
                    f"Tiempo: {analysis_time:.2f}s"
                )
            
            # 12. Enviar notificaciones
            if self.notification_service and request.notification_recipients:
                self._send_notifications(result, request.notification_recipients)
            
            return result
            
        except Exception as e:
            # Log error
            if self.logging_service:
                self.logging_service.log_error("schedule_analysis", e, {
                    "schedule_id": request.schedule_id,
                    "scope": request.scope.value
                })
            
            return AnalysisResult.failure_result(
                request.schedule_id,
                f"Error inesperado durante el análisis: {str(e)}"
            )
    
    def get_quick_summary(self, schedule_id: str) -> Dict[str, Any]:
        """
        Obtiene un resumen rápido del horario sin análisis completo.
        
        Args:
            schedule_id: ID del horario
            
        Returns:
            Dict: Resumen rápido
        """
        try:
            schedule = self.schedule_repository.load_schedule(schedule_id)
            if not schedule:
                return {"error": "Horario no encontrado"}
            
            # Obtener estadísticas básicas
            stats = schedule.get_summary_stats()
            
            # Validación rápida
            violations = default_validator.validate(schedule)
            
            # Análisis rápido de cobertura
            understaffed = schedule.get_understaffed_shifts()
            
            return {
                "schedule_id": schedule_id,
                "period": f"{schedule.start_date.strftime('%d/%m/%Y')} - {schedule.end_date.strftime('%d/%m/%Y')}",
                "coverage_percentage": stats["coverage_percentage"],
                "total_workers": stats["total_workers"],
                "violations_count": len(violations),
                "understaffed_shifts": len(understaffed),
                "status": self._determine_status(stats["coverage_percentage"], len(violations))
            }
            
        except Exception as e:
            return {"error": f"Error al generar resumen: {str(e)}"}
    
    def _get_analysis_types_for_scope(self, scope: AnalysisScope) -> List[AnalysisType]:
        """Determina los tipos de análisis según el alcance."""
        if scope == AnalysisScope.BASIC:
            return [AnalysisType.SHIFT_COVERAGE]
        elif scope == AnalysisScope.WORKLOAD:
            return [AnalysisType.WORKLOAD_DISTRIBUTION]
        elif scope == AnalysisScope.COMPLIANCE:
            return [AnalysisType.CONSTRAINT_VIOLATIONS]
        elif scope == AnalysisScope.EQUITY:
            return [AnalysisType.COMPENSATION_EQUITY]
        else:  # COMPREHENSIVE
            return [AnalysisType.COMPREHENSIVE]
    
    def _perform_comparison_analysis(self, schedule1: Schedule, schedule2_id: str) -> Optional[Dict[str, Any]]:
        """Realiza análisis de comparación entre dos horarios."""
        try:
            schedule2 = self.schedule_repository.load_schedule(schedule2_id)
            if not schedule2:
                return {"error": "Horario de comparación no encontrado"}
            
            comparison = self.schedule_analyzer.compare_schedules(schedule1, schedule2)
            return comparison
            
        except Exception as e:
            return {"error": f"Error en comparación: {str(e)}"}
    
    def _export_analysis(self, result: AnalysisResult, format: str) -> Optional[str]:
        """Exporta el análisis al formato especificado."""
        try:
            # Implementación básica - en producción usaría servicios de exportación
            filename = f"analysis_{result.schedule_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format}"
            
            if format == "json":
                # Exportar como JSON
                return f"exports/{filename}"
            elif format == "excel":
                # Exportar como Excel
                return f"exports/{filename}"
            elif format == "pdf":
                # Exportar como PDF
                return f"exports/{filename}"
            
            return None
            
        except Exception as e:
            if self.logging_service:
                self.logging_service.log_error("analysis_export", e, {
                    "schedule_id": result.schedule_id,
                    "format": format
                })
            return None
    
    def _determine_status(self, coverage: float, violations_count: int) -> str:
        """Determina el estado general del horario."""
        if violations_count > 10:
            return "Crítico"
        elif coverage < 80:
            return "Deficiente"
        elif coverage < 95 or violations_count > 5:
            return "Necesita mejoras"
        elif coverage >= 98 and violations_count <= 2:
            return "Excelente"
        else:
            return "Bueno"
    
    def _check_cache(self, request: AnalysisRequest) -> Optional[AnalysisResult]:
        """Verifica si existe un análisis en caché."""
        if not self.cache_service:
            return None
        
        cache_key = f"analysis_{request.schedule_id}_{request.scope.value}"
        cached_data = self.cache_service.get(cache_key)
        
        if cached_data:
            # Verificar que el horario aún existe
            if self.schedule_repository.exists(request.schedule_id):
                # Reconstruir resultado desde caché
                return AnalysisResult(
                    success=cached_data.get("success", False),
                    schedule_id=request.schedule_id,
                    analysis_report=cached_data.get("analysis_report"),
                    comparison_data=cached_data.get("comparison_data"),
                    analysis_time=cached_data.get("analysis_time", 0.0),
                    cached=True,
                    export_path=cached_data.get("export_path"),
                    message=cached_data.get("message", ""),
                    warnings=cached_data.get("warnings", [])
                )
        
        return None
    
    def _save_to_cache(self, request: AnalysisRequest, result: AnalysisResult):
        """Guarda el resultado en caché."""
        if not self.cache_service or not result.success:
            return
        
        cache_key = f"analysis_{request.schedule_id}_{request.scope.value}"
        cache_data = {
            "success": result.success,
            "analysis_report": result.analysis_report,
            "comparison_data": result.comparison_data,
            "analysis_time": result.analysis_time,
            "export_path": result.export_path,
            "message": result.message,
            "warnings": result.warnings,
            "timestamp": datetime.now().isoformat()
        }
        
        # Caché por 1 hora
        self.cache_service.set(cache_key, cache_data, ttl=3600)
    
    def _send_notifications(self, result: AnalysisResult, recipients: List[str]):
        """Envía notificaciones sobre el resultado del análisis."""
        if not self.notification_service:
            return
        
        try:
            if result.success and result.analysis_report:
                analysis_info = {
                    "schedule_id": result.schedule_id,
                    "analysis_date": result.analysis_report.analysis_date.isoformat(),
                    "overall_score": result.overall_score,
                    "coverage_percentage": result.analysis_report.coverage_analysis.coverage_percentage,
                    "violations_count": len(result.analysis_report.constraint_violations),
                    "key_insights": result.key_insights,
                    "export_path": result.export_path
                }
                
                # Enviar notificación de análisis completado
                self.notification_service.send_schedule_generated(analysis_info, recipients)
                
                # Enviar reporte de violaciones si las hay
                if result.analysis_report.constraint_violations:
                    self.notification_service.send_validation_report(
                        result.analysis_report.constraint_violations, recipients
                    )
            else:
                error_info = {
                    "operation": "schedule_analysis",
                    "schedule_id": result.schedule_id,
                    "message": result.message,
                    "warnings": result.warnings
                }
                
                self.notification_service.send_error_alert(error_info, recipients)
                
        except Exception as e:
            if self.logging_service:
                self.logging_service.log_error("send_analysis_notifications", e, {
                    "schedule_id": result.schedule_id,
                    "recipients": recipients
                })