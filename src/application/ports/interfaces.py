"""
Interfaces y contratos para la capa de aplicación.

Este módulo define todas las interfaces que la capa de aplicación
necesita para interactuar con la infraestructura y servicios externos.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass

from ...core.models import Schedule, Worker


# =====================================================================
# Repository Interfaces
# =====================================================================

class ScheduleRepository(ABC):
    """Interfaz para el repositorio de horarios."""
    
    @abstractmethod
    def save_schedule(self, schedule: Schedule, schedule_id: str) -> bool:
        """
        Guarda un horario en el repositorio.
        
        Args:
            schedule: Horario a guardar
            schedule_id: ID único del horario
            
        Returns:
            bool: True si se guardó exitosamente
        """
        pass
    
    @abstractmethod
    def load_schedule(self, schedule_id: str) -> Optional[Schedule]:
        """
        Carga un horario del repositorio.
        
        Args:
            schedule_id: ID del horario a cargar
            
        Returns:
            Schedule o None si no se encuentra
        """
        pass
    
    @abstractmethod
    def exists(self, schedule_id: str) -> bool:
        """
        Verifica si existe un horario con el ID especificado.
        
        Args:
            schedule_id: ID del horario
            
        Returns:
            bool: True si existe
        """
        pass
    
    @abstractmethod
    def delete_schedule(self, schedule_id: str) -> bool:
        """
        Elimina un horario del repositorio.
        
        Args:
            schedule_id: ID del horario a eliminar
            
        Returns:
            bool: True si se eliminó exitosamente
        """
        pass
    
    @abstractmethod
    def list_schedules(self, start_date: Optional[datetime] = None,
                      end_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Lista horarios disponibles, opcionalmente filtrados por fecha.
        
        Args:
            start_date: Fecha de inicio del filtro (opcional)
            end_date: Fecha de fin del filtro (opcional)
            
        Returns:
            List[Dict]: Lista de metadatos de horarios
        """
        pass
    
    @abstractmethod
    def get_schedule_metadata(self, schedule_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene metadatos de un horario sin cargarlo completamente.
        
        Args:
            schedule_id: ID del horario
            
        Returns:
            Dict con metadatos o None si no existe
        """
        pass


class WorkerRepository(ABC):
    """Interfaz para el repositorio de trabajadores."""
    
    @abstractmethod
    def get_all_workers(self) -> List[Worker]:
        """
        Obtiene todos los trabajadores registrados.
        
        Returns:
            List[Worker]: Lista de trabajadores
        """
        pass
    
    @abstractmethod
    def get_available_workers(self, start_date: datetime, 
                            end_date: datetime) -> List[Worker]:
        """
        Obtiene trabajadores disponibles para un período específico.
        
        Args:
            start_date: Fecha de inicio del período
            end_date: Fecha de fin del período
            
        Returns:
            List[Worker]: Lista de trabajadores disponibles
        """
        pass
    
    @abstractmethod
    def get_worker_by_id(self, worker_id: int, is_technologist: bool) -> Optional[Worker]:
        """
        Obtiene un trabajador específico por ID.
        
        Args:
            worker_id: ID del trabajador
            is_technologist: True si es tecnólogo, False si es ingeniero
            
        Returns:
            Worker o None si no se encuentra
        """
        pass
    
    @abstractmethod
    def save_worker(self, worker: Worker) -> bool:
        """
        Guarda o actualiza un trabajador.
        
        Args:
            worker: Trabajador a guardar
            
        Returns:
            bool: True si se guardó exitosamente
        """
        pass
    
    @abstractmethod
    def get_worker_preferences(self, worker_id: int, 
                             is_technologist: bool) -> Dict[str, Any]:
        """
        Obtiene las preferencias de horario de un trabajador.
        
        Args:
            worker_id: ID del trabajador
            is_technologist: Tipo de trabajador
            
        Returns:
            Dict: Preferencias del trabajador
        """
        pass


# =====================================================================
# Service Interfaces
# =====================================================================

class LoggingService(ABC):
    """Interfaz para el servicio de logging."""
    
    @abstractmethod
    def log_generation_started(self, schedule_id: str, start_date: datetime, 
                             end_date: datetime) -> None:
        """Registra el inicio de generación de horario."""
        pass
    
    @abstractmethod
    def log_generation_completed(self, schedule_id: str, quality_score: float,
                                violations_count: int) -> None:
        """Registra la finalización de generación de horario."""
        pass
    
    @abstractmethod
    def log_optimization_performed(self, schedule_id: str, 
                                 improvement_percentage: float) -> None:
        """Registra una optimización realizada."""
        pass
    
    @abstractmethod
    def log_export_performed(self, schedule_id: str, export_format: str,
                           file_path: str) -> None:
        """Registra una exportación realizada."""
        pass
    
    @abstractmethod
    def log_info(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Registra información general."""
        pass
    
    @abstractmethod
    def log_warning(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Registra una advertencia."""
        pass
    
    @abstractmethod
    def log_error(self, operation: str, error: Exception, 
                 context: Optional[Dict[str, Any]] = None) -> None:
        """Registra un error."""
        pass


class NotificationService(ABC):
    """Interfaz para el servicio de notificaciones."""
    
    @abstractmethod
    def send_schedule_generated(self, schedule_info: Dict[str, Any], 
                              recipients: List[str]) -> bool:
        """
        Envía notificación de horario generado.
        
        Args:
            schedule_info: Información del horario generado
            recipients: Lista de destinatarios
            
        Returns:
            bool: True si se envió exitosamente
        """
        pass
    
    @abstractmethod
    def send_validation_report(self, violations: List[str], 
                             recipients: List[str]) -> bool:
        """
        Envía reporte de violaciones encontradas.
        
        Args:
            violations: Lista de violaciones
            recipients: Lista de destinatarios
            
        Returns:
            bool: True si se envió exitosamente
        """
        pass
    
    @abstractmethod
    def send_warning_report(self, warnings: List[str], 
                          recipients: List[str]) -> bool:
        """
        Envía reporte de advertencias.
        
        Args:
            warnings: Lista de advertencias
            recipients: Lista de destinatarios
            
        Returns:
            bool: True si se envió exitosamente
        """
        pass
    
    @abstractmethod
    def send_error_alert(self, error_info: Dict[str, Any], 
                        recipients: List[str]) -> bool:
        """
        Envía alerta de error.
        
        Args:
            error_info: Información del error
            recipients: Lista de destinatarios
            
        Returns:
            bool: True si se envió exitosamente
        """
        pass
    
    @abstractmethod
    def send_export_completion(self, export_info: Dict[str, Any], 
                             recipients: List[str]) -> bool:
        """
        Envía notificación de exportación completada.
        
        Args:
            export_info: Información de la exportación
            recipients: Lista de destinatarios
            
        Returns:
            bool: True si se envió exitosamente
        """
        pass


class CacheService(ABC):
    """Interfaz para el servicio de caché."""
    
    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """
        Obtiene un valor del caché.
        
        Args:
            key: Clave del valor
            
        Returns:
            Valor almacenado o None si no existe
        """
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Almacena un valor en el caché.
        
        Args:
            key: Clave del valor
            value: Valor a almacenar
            ttl: Tiempo de vida en segundos (opcional)
            
        Returns:
            bool: True si se almacenó exitosamente
        """
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """
        Elimina un valor del caché.
        
        Args:
            key: Clave del valor a eliminar
            
        Returns:
            bool: True si se eliminó exitosamente
        """
        pass
    
    @abstractmethod
    def clear(self) -> bool:
        """
        Limpia todo el caché.
        
        Returns:
            bool: True si se limpió exitosamente
        """
        pass
    
    @abstractmethod
    def exists(self, key: str) -> bool:
        """
        Verifica si una clave existe en el caché.
        
        Args:
            key: Clave a verificar
            
        Returns:
            bool: True si existe
        """
        pass


@dataclass
class ShiftRequirements:
    """Configuración de requerimientos de personal por turno."""
    technologists_per_shift: Dict[str, int]  # {"Mañana": 5, "Tarde": 5, "Noche": 2}
    engineers_per_shift: Dict[str, int]      # {"Mañana": 1, "Tarde": 1, "Noche": 1}
    total_workers_required: int
    minimum_rest_hours: int = 12
    maximum_consecutive_days: int = 6


@dataclass
class CompensationRules:
    """Reglas de compensación por tipo de turno."""
    base_rate: float = 1.0
    night_rate: float = 1.5
    weekend_day_rate: float = 2.0
    weekend_night_rate: float = 2.5
    holiday_multiplier: float = 1.25


@dataclass
class GenerationSettings:
    """Configuración para la generación de horarios."""
    max_iterations: int = 100
    convergence_threshold: float = 0.01
    random_seed: Optional[int] = None
    enable_proactive_detection: bool = True
    strict_compliance_mode: bool = False


class ConfigurationService(ABC):
    """Interfaz para el servicio de configuración."""
    
    @abstractmethod
    def get_shift_requirements(self) -> ShiftRequirements:
        """
        Obtiene los requerimientos de personal por turno.
        
        Returns:
            ShiftRequirements: Configuración de requerimientos
        """
        pass
    
    @abstractmethod
    def get_compensation_rules(self) -> CompensationRules:
        """
        Obtiene las reglas de compensación.
        
        Returns:
            CompensationRules: Reglas de compensación
        """
        pass
    
    @abstractmethod
    def get_generation_config(self) -> GenerationSettings:
        """
        Obtiene la configuración para generación de horarios.
        
        Returns:
            GenerationSettings: Configuración de generación
        """
        pass
    
    @abstractmethod
    def get_holiday_dates(self, year: int) -> List[datetime]:
        """
        Obtiene las fechas de festivos para un año.
        
        Args:
            year: Año para obtener festivos
            
        Returns:
            List[datetime]: Lista de fechas de festivos
        """
        pass
    
    @abstractmethod
    def update_shift_requirements(self, requirements: ShiftRequirements) -> bool:
        """
        Actualiza los requerimientos de personal.
        
        Args:
            requirements: Nuevos requerimientos
            
        Returns:
            bool: True si se actualizó exitosamente
        """
        pass
    
    @abstractmethod
    def update_compensation_rules(self, rules: CompensationRules) -> bool:
        """
        Actualiza las reglas de compensación.
        
        Args:
            rules: Nuevas reglas
            
        Returns:
            bool: True si se actualizó exitosamente
        """
        pass


# =====================================================================
# Export Interfaces
# =====================================================================

class ExportAdapter(ABC):
    """Interfaz base para adaptadores de exportación."""
    
    @abstractmethod
    def export_schedule(self, schedule: Schedule, output_path: str, 
                       options: Optional[Dict[str, Any]] = None) -> bool:
        """
        Exporta un horario al formato específico.
        
        Args:
            schedule: Horario a exportar
            output_path: Ruta de salida
            options: Opciones específicas del formato
            
        Returns:
            bool: True si se exportó exitosamente
        """
        pass
    
    @abstractmethod
    def get_supported_options(self) -> Dict[str, Any]:
        """
        Obtiene las opciones soportadas por este adaptador.
        
        Returns:
            Dict: Opciones disponibles y sus valores por defecto
        """
        pass
    
    @abstractmethod
    def validate_options(self, options: Dict[str, Any]) -> List[str]:
        """
        Valida las opciones proporcionadas.
        
        Args:
            options: Opciones a validar
            
        Returns:
            List[str]: Lista de errores de validación
        """
        pass


class ExcelExportAdapter(ExportAdapter):
    """Interfaz específica para exportación a Excel."""
    pass


class PDFExportAdapter(ExportAdapter):
    """Interfaz específica para exportación a PDF."""
    pass


class CSVExportAdapter(ExportAdapter):
    """Interfaz específica para exportación a CSV."""
    pass


# =====================================================================
# Analysis Interfaces
# =====================================================================

@dataclass
class AnalysisResult:
    """Resultado de análisis de horario."""
    schedule_id: str
    analysis_date: datetime
    metrics: Dict[str, float]
    insights: List[str]
    recommendations: List[str]
    quality_score: float
    compliance_score: float


class AnalysisService(ABC):
    """Interfaz para servicios de análisis."""
    
    @abstractmethod
    def analyze_schedule(self, schedule: Schedule) -> AnalysisResult:
        """
        Realiza análisis completo de un horario.
        
        Args:
            schedule: Horario a analizar
            
        Returns:
            AnalysisResult: Resultado del análisis
        """
        pass
    
    @abstractmethod
    def compare_schedules(self, schedule1: Schedule, 
                         schedule2: Schedule) -> Dict[str, Any]:
        """
        Compara dos horarios y retorna diferencias.
        
        Args:
            schedule1: Primer horario
            schedule2: Segundo horario
            
        Returns:
            Dict: Resultado de la comparación
        """
        pass
    
    @abstractmethod
    def generate_insights(self, schedule: Schedule) -> List[str]:
        """
        Genera insights sobre un horario.
        
        Args:
            schedule: Horario a analizar
            
        Returns:
            List[str]: Lista de insights
        """
        pass
    
    @abstractmethod
    def get_recommendations(self, schedule: Schedule) -> List[str]:
        """
        Genera recomendaciones de mejora.
        
        Args:
            schedule: Horario a analizar
            
        Returns:
            List[str]: Lista de recomendaciones
        """
        pass


# =====================================================================
# Event Interfaces
# =====================================================================

@dataclass
class DomainEvent:
    """Evento de dominio base."""
    event_id: str
    timestamp: datetime
    event_type: str
    data: Dict[str, Any]


class EventPublisher(ABC):
    """Interfaz para publicación de eventos."""
    
    @abstractmethod
    def publish(self, event: DomainEvent) -> bool:
        """
        Publica un evento de dominio.
        
        Args:
            event: Evento a publicar
            
        Returns:
            bool: True si se publicó exitosamente
        """
        pass


class EventSubscriber(ABC):
    """Interfaz para suscripción a eventos."""
    
    @abstractmethod
    def handle_event(self, event: DomainEvent) -> None:
        """
        Maneja un evento recibido.
        
        Args:
            event: Evento a manejar
        """
        pass
    
    @abstractmethod
    def get_subscribed_events(self) -> List[str]:
        """
        Obtiene los tipos de eventos a los que está suscrito.
        
        Returns:
            List[str]: Lista de tipos de eventos
        """
        pass