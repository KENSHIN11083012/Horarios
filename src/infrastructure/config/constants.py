"""
Constantes del sistema de horarios.

Este módulo contiene todas las constantes utilizadas a lo largo del sistema,
organizadas por categorías para facilitar el mantenimiento.
"""

from typing import Dict, List

# =====================================================================
# Configuración de Turnos
# =====================================================================

# Tipos de turnos disponibles
SHIFT_TYPES = ["Mañana", "Tarde", "Noche"]

# Personal requerido por turno (tecnólogos)
TECHS_PER_SHIFT = {
    "Mañana": 5,
    "Tarde": 5,
    "Noche": 2
}

# Ingenieros requeridos por turno (siempre 1)
ENG_PER_SHIFT = 1

# Horarios de cada turno
SHIFT_SCHEDULES = {
    "Mañana": {"start": "06:00", "end": "14:00"},
    "Tarde": {"start": "14:00", "end": "22:00"},
    "Noche": {"start": "22:00", "end": "06:00"}
}

# =====================================================================
# Restricciones Laborales
# =====================================================================

# Horas mínimas de descanso entre turnos
MIN_REST_HOURS = 12

# Máximo de días consecutivos de trabajo
MAX_CONSECUTIVE_DAYS = 6

# Máximo de turnos nocturnos consecutivos
MAX_CONSECUTIVE_NIGHTS = 3

# Mínimo de días libres por semana
MIN_DAYS_OFF_PER_WEEK = 1

# =====================================================================
# Compensaciones
# =====================================================================

# Factores de compensación base
COMPENSATION_RATES = {
    "base": 1.0,
    "night": 1.5,
    "weekend_day": 2.0,
    "weekend_night": 2.5,
    "holiday": 1.25  # Multiplicador adicional para festivos
}

# Bonificaciones especiales
SPECIAL_BONUSES = {
    "consecutive_nights": 0.1,  # 10% extra por noche consecutiva
    "overtime": 1.5,            # 150% para tiempo extra
    "emergency": 2.0            # 200% para emergencias
}

# =====================================================================
# Configuración del Sistema
# =====================================================================

# Límites de generación
GENERATION_LIMITS = {
    "max_attempts": 10,
    "max_iterations": 100,
    "timeout_seconds": 300,
    "min_coverage_percentage": 80.0
}

# Configuración de optimización
OPTIMIZATION_LIMITS = {
    "max_iterations": 50,
    "max_swaps_per_iteration": 30,
    "improvement_threshold": 0.01,
    "convergence_patience": 5
}

# Configuración de análisis
ANALYSIS_THRESHOLDS = {
    "excellent_coverage": 98.0,
    "good_coverage": 95.0,
    "acceptable_coverage": 85.0,
    "poor_coverage": 70.0,
    "max_violations_warning": 5,
    "max_violations_critical": 15
}

# =====================================================================
# Configuración de Archivos y Exportación
# =====================================================================

# Formatos de exportación soportados
SUPPORTED_EXPORT_FORMATS = ["excel", "pdf", "csv", "json"]

# Extensiones de archivo
FILE_EXTENSIONS = {
    "excel": ".xlsx",
    "pdf": ".pdf",
    "csv": ".csv",
    "json": ".json"
}

# Tamaños máximos de archivo (en MB)
MAX_FILE_SIZES = {
    "excel": 50,
    "pdf": 20,
    "csv": 10,
    "json": 5
}

# =====================================================================
# Configuración de Base de Datos/Persistencia
# =====================================================================

# Configuración de caché
CACHE_CONFIG = {
    "default_ttl": 3600,  # 1 hora
    "analysis_ttl": 3600,  # 1 hora
    "optimization_ttl": 7200,  # 2 horas
    "schedule_ttl": 86400,  # 24 horas
    "max_entries": 1000
}

# Configuración de backup
BACKUP_CONFIG = {
    "auto_backup": True,
    "backup_interval_hours": 24,
    "max_backups": 30,
    "compress_backups": True
}

# =====================================================================
# Configuración de Notificaciones
# =====================================================================

# Tipos de notificaciones
NOTIFICATION_TYPES = [
    "schedule_generated",
    "schedule_optimized",
    "analysis_completed",
    "export_completed",
    "validation_warning",
    "error_alert"
]

# Configuración de email
EMAIL_CONFIG = {
    "max_recipients": 50,
    "retry_attempts": 3,
    "timeout_seconds": 30,
    "batch_size": 10
}

# =====================================================================
# Validación y Calidad
# =====================================================================

# Scores de calidad
QUALITY_SCORES = {
    "excellent": 90.0,
    "good": 75.0,
    "acceptable": 60.0,
    "poor": 40.0,
    "critical": 20.0
}

# Pesos para cálculo de calidad general
QUALITY_WEIGHTS = {
    "coverage": 0.4,
    "compliance": 0.3,
    "workload_balance": 0.15,
    "compensation_equity": 0.15
}

# =====================================================================
# Configuración de Logging
# =====================================================================

# Niveles de log
LOG_LEVELS = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50
}

# Configuración de logs
LOGGING_CONFIG = {
    "max_file_size_mb": 100,
    "max_backup_count": 5,
    "log_format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "date_format": "%Y-%m-%d %H:%M:%S"
}

# =====================================================================
# Festivos Colombia (fechas fijas - las móviles se calculan dinámicamente)
# =====================================================================

# Festivos fijos por año
FIXED_HOLIDAYS = {
    "01-01": "Año Nuevo",
    "05-01": "Día del Trabajo", 
    "07-20": "Día de la Independencia",
    "08-07": "Batalla de Boyacá",
    "12-08": "Día de la Inmaculada Concepción",
    "12-25": "Navidad"
}

# Festivos que se mueven al lunes siguiente si caen entre martes y domingo
MOVABLE_HOLIDAYS = {
    "01-06": "Día de los Reyes Magos",
    "03-19": "Día de San José",
    "06-29": "San Pedro y San Pablo",
    "08-15": "Asunción de la Virgen",
    "10-12": "Día de la Raza",
    "11-01": "Día de Todos los Santos",
    "11-11": "Independencia de Cartagena"
}

# =====================================================================
# Configuración de la Interface de Usuario
# =====================================================================

# Colores del tema
UI_COLORS = {
    "primary": "#2E3440",
    "secondary": "#3B4252", 
    "accent": "#5E81AC",
    "success": "#A3BE8C",
    "warning": "#EBCB8B",
    "error": "#BF616A",
    "info": "#88C0D0",
    "background": "#ECEFF4",
    "surface": "#FFFFFF",
    "text": "#2E3440"
}

# Configuración de ventanas
WINDOW_CONFIG = {
    "min_width": 1024,
    "min_height": 768,
    "default_width": 1280,
    "default_height": 900,
    "center_on_screen": True
}

# =====================================================================
# Mensajes del Sistema
# =====================================================================

# Mensajes de éxito
SUCCESS_MESSAGES = {
    "schedule_generated": "Horario generado exitosamente",
    "schedule_optimized": "Horario optimizado correctamente",
    "schedule_exported": "Horario exportado exitosamente",
    "analysis_completed": "Análisis completado correctamente"
}

# Mensajes de error
ERROR_MESSAGES = {
    "invalid_date_range": "El rango de fechas no es válido",
    "insufficient_workers": "No hay suficientes trabajadores disponibles",
    "generation_failed": "No se pudo generar el horario",
    "optimization_failed": "No se pudo optimizar el horario",
    "export_failed": "Error al exportar el horario",
    "file_not_found": "No se encontró el archivo especificado",
    "invalid_format": "Formato de archivo no válido"
}

# Mensajes de advertencia
WARNING_MESSAGES = {
    "low_coverage": "La cobertura del horario está por debajo del mínimo recomendado",
    "many_violations": "Se encontraron múltiples violaciones de restricciones",
    "unbalanced_workload": "La distribución de carga de trabajo no está balanceada",
    "compensation_inequity": "Se detectaron inequidades en las compensaciones"
}

# =====================================================================
# Configuración de Desarrollo y Debug
# =====================================================================

# Configuración de debug
DEBUG_CONFIG = {
    "enable_debug": False,
    "log_sql_queries": False,
    "show_performance_metrics": False,
    "enable_profiling": False,
    "mock_data": False
}

# Configuración de testing
TEST_CONFIG = {
    "use_test_data": False,
    "test_workers_count": 20,
    "test_period_days": 30,
    "enable_test_mode": False
}