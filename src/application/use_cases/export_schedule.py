"""
Caso de uso: Exportar horario a diferentes formatos.

Este módulo implementa la exportación de horarios generados
a múltiples formatos (Excel, PDF, CSV) con opciones de
personalización y configuración.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from ...core.models import Schedule
from ..ports import (
    ScheduleRepository,
    ExcelExportAdapter,
    PDFExportAdapter,
    CSVExportAdapter,
    LoggingService,
    NotificationService
)


class ExportFormat(Enum):
    """Formatos de exportación disponibles."""
    EXCEL = "excel"
    PDF = "pdf"
    CSV = "csv"
    JSON = "json"


class ExportLayout(Enum):
    """Diseños de exportación disponibles."""
    CALENDAR = "calendar"           # Vista de calendario mensual
    TABLE = "table"                 # Vista de tabla por trabajador
    SUMMARY = "summary"             # Resumen ejecutivo
    DETAILED = "detailed"           # Vista detallada completa


@dataclass
class ExportOptions:
    """Opciones de personalización para la exportación."""
    layout: ExportLayout = ExportLayout.CALENDAR
    include_statistics: bool = True
    include_worker_details: bool = True
    include_violations: bool = False
    group_by_worker_type: bool = True
    show_compensation: bool = False
    custom_title: Optional[str] = None
    logo_path: Optional[str] = None
    company_info: Optional[Dict[str, str]] = None
    
    def validate(self) -> List[str]:
        """Valida las opciones de exportación."""
        errors = []
        
        if self.logo_path and not Path(self.logo_path).exists():
            errors.append(f"El archivo de logo no existe: {self.logo_path}")
        
        if self.company_info:
            required_fields = ["name", "address"]
            for field in required_fields:
                if field not in self.company_info:
                    errors.append(f"Información de empresa debe incluir: {field}")
        
        return errors


@dataclass
class ExportRequest:
    """Solicitud de exportación de horario."""
    schedule_id: str
    format: ExportFormat
    output_path: str
    options: ExportOptions = ExportOptions()
    notification_recipients: Optional[List[str]] = None
    
    def validate(self) -> List[str]:
        """Valida la solicitud de exportación."""
        errors = []
        
        if not self.schedule_id.strip():
            errors.append("El ID del horario es requerido")
        
        if not self.output_path.strip():
            errors.append("La ruta de salida es requerida")
        
        # Validar que la ruta de salida tenga la extensión correcta
        expected_extension = {
            ExportFormat.EXCEL: ".xlsx",
            ExportFormat.PDF: ".pdf", 
            ExportFormat.CSV: ".csv",
            ExportFormat.JSON: ".json"
        }
        
        if not self.output_path.endswith(expected_extension[self.format]):
            errors.append(f"La ruta debe terminar en {expected_extension[self.format]} para formato {self.format.value}")
        
        # Validar que el directorio padre existe
        output_dir = Path(self.output_path).parent
        if not output_dir.exists():
            errors.append(f"El directorio de salida no existe: {output_dir}")
        
        # Validar opciones
        errors.extend(self.options.validate())
        
        return errors


@dataclass
class ExportResult:
    """Resultado de la exportación de horario."""
    success: bool
    schedule_id: str
    output_path: Optional[str]
    format: ExportFormat
    file_size_bytes: int
    export_time: float
    message: str
    warnings: List[str]
    
    @property
    def file_size_mb(self) -> float:
        """Tamaño del archivo en MB."""
        return self.file_size_bytes / (1024 * 1024)
    
    @classmethod
    def success_result(cls, schedule_id: str, output_path: str, format: ExportFormat,
                      file_size: int, export_time: float) -> 'ExportResult':
        """Crea un resultado exitoso."""
        return cls(
            success=True,
            schedule_id=schedule_id,
            output_path=output_path,
            format=format,
            file_size_bytes=file_size,
            export_time=export_time,
            message="Exportación completada exitosamente",
            warnings=[]
        )
    
    @classmethod
    def failure_result(cls, schedule_id: str, format: ExportFormat, 
                      message: str, warnings: List[str] = None) -> 'ExportResult':
        """Crea un resultado de fallo."""
        return cls(
            success=False,
            schedule_id=schedule_id,
            output_path=None,
            format=format,
            file_size_bytes=0,
            export_time=0.0,
            message=message,
            warnings=warnings or []
        )


class ExportScheduleUseCase:
    """
    Caso de uso para exportar horarios a diferentes formatos.
    
    Este caso de uso coordina la exportación de horarios utilizando
    diferentes adaptadores según el formato solicitado.
    """
    
    def __init__(self,
                 schedule_repository: ScheduleRepository,
                 excel_adapter: Optional[ExcelExportAdapter] = None,
                 pdf_adapter: Optional[PDFExportAdapter] = None,
                 csv_adapter: Optional[CSVExportAdapter] = None,
                 logging_service: Optional[LoggingService] = None,
                 notification_service: Optional[NotificationService] = None):
        """
        Inicializa el caso de uso.
        
        Args:
            schedule_repository: Repositorio de horarios
            excel_adapter: Adaptador para exportación Excel (opcional)
            pdf_adapter: Adaptador para exportación PDF (opcional)
            csv_adapter: Adaptador para exportación CSV (opcional)
            logging_service: Servicio de logging (opcional)
            notification_service: Servicio de notificaciones (opcional)
        """
        self.schedule_repository = schedule_repository
        self.excel_adapter = excel_adapter
        self.pdf_adapter = pdf_adapter
        self.csv_adapter = csv_adapter
        self.logging_service = logging_service
        self.notification_service = notification_service
    
    def execute(self, request: ExportRequest) -> ExportResult:
        """
        Ejecuta la exportación de horario.
        
        Args:
            request: Solicitud de exportación
            
        Returns:
            ExportResult: Resultado de la exportación
        """
        start_time = datetime.now()
        
        try:
            # 1. Validar solicitud
            validation_errors = request.validate()
            if validation_errors:
                return ExportResult.failure_result(
                    request.schedule_id, request.format,
                    "Solicitud inválida: " + "; ".join(validation_errors)
                )
            
            # 2. Cargar horario
            schedule = self.schedule_repository.load_schedule(request.schedule_id)
            if not schedule:
                return ExportResult.failure_result(
                    request.schedule_id, request.format, "Horario no encontrado"
                )
            
            # 3. Verificar adaptador disponible
            adapter = self._get_adapter_for_format(request.format)
            if not adapter:
                return ExportResult.failure_result(
                    request.schedule_id, request.format,
                    f"Adaptador no disponible para formato {request.format.value}"
                )
            
            # 4. Log inicio de exportación
            if self.logging_service:
                self.logging_service.log_info(
                    f"Iniciando exportación: {request.schedule_id} -> {request.format.value}"
                )
            
            # 5. Preparar opciones para el adaptador
            adapter_options = self._prepare_adapter_options(request.options)
            
            # 6. Validar opciones del adaptador
            option_errors = adapter.validate_options(adapter_options)
            if option_errors:
                return ExportResult.failure_result(
                    request.schedule_id, request.format,
                    "Opciones inválidas: " + "; ".join(option_errors)
                )
            
            # 7. Ejecutar exportación
            export_success = adapter.export_schedule(
                schedule, request.output_path, adapter_options
            )
            
            if not export_success:
                return ExportResult.failure_result(
                    request.schedule_id, request.format,
                    "Error durante la exportación"
                )
            
            # 8. Verificar archivo generado
            output_file = Path(request.output_path)
            if not output_file.exists():
                return ExportResult.failure_result(
                    request.schedule_id, request.format,
                    "El archivo de salida no fue creado"
                )
            
            # 9. Calcular estadísticas
            file_size = output_file.stat().st_size
            export_time = (datetime.now() - start_time).total_seconds()
            
            # 10. Crear resultado exitoso
            result = ExportResult.success_result(
                request.schedule_id, request.output_path, request.format,
                file_size, export_time
            )
            
            # 11. Log finalización
            if self.logging_service:
                self.logging_service.log_export_performed(
                    request.schedule_id, request.format.value, request.output_path
                )
            
            # 12. Enviar notificaciones
            if self.notification_service and request.notification_recipients:
                self._send_notifications(result, request.notification_recipients)
            
            return result
            
        except Exception as e:
            # Log error
            if self.logging_service:
                self.logging_service.log_error("schedule_export", e, {
                    "schedule_id": request.schedule_id,
                    "format": request.format.value,
                    "output_path": request.output_path
                })
            
            return ExportResult.failure_result(
                request.schedule_id, request.format,
                f"Error inesperado durante la exportación: {str(e)}"
            )
    
    def get_supported_formats(self) -> List[Dict[str, Any]]:
        """
        Obtiene los formatos de exportación soportados.
        
        Returns:
            List[Dict]: Lista de formatos con sus capacidades
        """
        formats = []
        
        if self.excel_adapter:
            formats.append({
                "format": ExportFormat.EXCEL.value,
                "description": "Microsoft Excel (.xlsx)",
                "features": ["gráficos", "múltiples hojas", "formato avanzado"],
                "options": self.excel_adapter.get_supported_options()
            })
        
        if self.pdf_adapter:
            formats.append({
                "format": ExportFormat.PDF.value,
                "description": "Documento PDF (.pdf)",
                "features": ["imprimible", "portable", "diseño profesional"],
                "options": self.pdf_adapter.get_supported_options()
            })
        
        if self.csv_adapter:
            formats.append({
                "format": ExportFormat.CSV.value,
                "description": "Valores separados por comas (.csv)",
                "features": ["compatible con cualquier software", "ligero"],
                "options": self.csv_adapter.get_supported_options()
            })
        
        # JSON siempre está disponible (implementación interna)
        formats.append({
            "format": ExportFormat.JSON.value,
            "description": "JavaScript Object Notation (.json)",
            "features": ["estructurado", "legible por máquinas", "intercambio de datos"],
            "options": {"include_metadata": True, "pretty_format": True}
        })
        
        return formats
    
    def export_multiple_formats(self, schedule_id: str, base_path: str, 
                               formats: List[ExportFormat], 
                               options: ExportOptions = ExportOptions()) -> List[ExportResult]:
        """
        Exporta un horario a múltiples formatos.
        
        Args:
            schedule_id: ID del horario
            base_path: Ruta base para los archivos (sin extensión)
            formats: Lista de formatos a exportar
            options: Opciones de exportación
            
        Returns:
            List[ExportResult]: Resultados de cada exportación
        """
        results = []
        
        for format in formats:
            # Generar ruta específica para cada formato
            extension_map = {
                ExportFormat.EXCEL: ".xlsx",
                ExportFormat.PDF: ".pdf",
                ExportFormat.CSV: ".csv",
                ExportFormat.JSON: ".json"
            }
            
            output_path = f"{base_path}{extension_map[format]}"
            
            # Crear solicitud
            request = ExportRequest(
                schedule_id=schedule_id,
                format=format,
                output_path=output_path,
                options=options
            )
            
            # Ejecutar exportación
            result = self.execute(request)
            results.append(result)
        
        return results
    
    def _get_adapter_for_format(self, format: ExportFormat):
        """Obtiene el adaptador apropiado para el formato."""
        if format == ExportFormat.EXCEL:
            return self.excel_adapter
        elif format == ExportFormat.PDF:
            return self.pdf_adapter
        elif format == ExportFormat.CSV:
            return self.csv_adapter
        elif format == ExportFormat.JSON:
            return self  # Implementación interna para JSON
        return None
    
    def _prepare_adapter_options(self, options: ExportOptions) -> Dict[str, Any]:
        """Prepara las opciones para el adaptador específico."""
        return {
            "layout": options.layout.value,
            "include_statistics": options.include_statistics,
            "include_worker_details": options.include_worker_details,
            "include_violations": options.include_violations,
            "group_by_worker_type": options.group_by_worker_type,
            "show_compensation": options.show_compensation,
            "custom_title": options.custom_title,
            "logo_path": options.logo_path,
            "company_info": options.company_info or {}
        }
    
    def export_schedule(self, schedule: Schedule, output_path: str, 
                       options: Optional[Dict[str, Any]] = None) -> bool:
        """Implementación interna para exportación JSON."""
        try:
            import json
            
            # Preparar datos para JSON
            schedule_data = {
                "metadata": {
                    "export_date": datetime.now().isoformat(),
                    "schedule_id": f"schedule_{schedule.start_date.strftime('%Y%m')}",
                    "period": {
                        "start_date": schedule.start_date.isoformat(),
                        "end_date": schedule.end_date.isoformat()
                    }
                },
                "statistics": schedule.get_summary_stats(),
                "workers": [
                    {
                        "id": worker.formatted_id,
                        "type": worker.worker_type.value,
                        "shifts": [
                            {
                                "date": shift.date.isoformat(),
                                "shift_type": shift.shift_type.value,
                                "compensation": shift.compensation
                            }
                            for shift in worker.shifts
                        ],
                        "days_off": [d.isoformat() for d in worker.days_off],
                        "total_compensation": worker.total_earnings
                    }
                    for worker in schedule.get_all_workers()
                ],
                "daily_schedule": [
                    {
                        "date": day.date.isoformat(),
                        "shifts": {
                            shift_type.value: {
                                "assigned_workers": slot.assigned_workers,
                                "required_workers": slot.required_workers,
                                "coverage_percentage": slot.coverage_percentage
                            }
                            for shift_type, slot in day.shifts.items()
                        },
                        "coverage_percentage": day.coverage_percentage
                    }
                    for day in schedule.days.values()
                ]
            }
            
            # Escribir archivo JSON
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(schedule_data, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            if self.logging_service:
                self.logging_service.log_error("json_export", e, {"output_path": output_path})
            return False
    
    def get_supported_options(self) -> Dict[str, Any]:
        """Opciones soportadas para exportación JSON."""
        return {
            "include_metadata": True,
            "pretty_format": True,
            "include_statistics": True
        }
    
    def validate_options(self, options: Dict[str, Any]) -> List[str]:
        """Valida opciones para exportación JSON."""
        # JSON es flexible, pocas validaciones necesarias
        return []
    
    def _send_notifications(self, result: ExportResult, recipients: List[str]):
        """Envía notificaciones sobre el resultado de la exportación."""
        if not self.notification_service:
            return
        
        try:
            if result.success:
                export_info = {
                    "schedule_id": result.schedule_id,
                    "format": result.format.value,
                    "output_path": result.output_path,
                    "file_size_mb": result.file_size_mb,
                    "export_time": result.export_time
                }
                
                self.notification_service.send_export_completion(export_info, recipients)
            else:
                error_info = {
                    "operation": "schedule_export",
                    "schedule_id": result.schedule_id,
                    "format": result.format.value,
                    "message": result.message,
                    "warnings": result.warnings
                }
                
                self.notification_service.send_error_alert(error_info, recipients)
                
        except Exception as e:
            if self.logging_service:
                self.logging_service.log_error("send_export_notifications", e, {
                    "schedule_id": result.schedule_id,
                    "recipients": recipients
                })