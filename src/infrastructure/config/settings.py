"""
Configuración del sistema de horarios.

Este módulo proporciona una interfaz unificada para acceder a toda la configuración
del sistema, incluyendo valores por defecto y validaciones.
"""

import os
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from pathlib import Path

from .constants import *


class Settings:
    """
    Clase principal de configuración del sistema.
    
    Maneja la carga de configuración desde múltiples fuentes:
    - Variables de entorno
    - Archivos de configuración
    - Valores por defecto
    """
    
    def __init__(self, config_file: Optional[str] = None):
        """
        Inicializa la configuración.
        
        Args:
            config_file: Ruta al archivo de configuración personalizado (opcional)
        """
        self._config_data = {}
        self._config_file = config_file
        self._load_configuration()
    
    def _load_configuration(self):
        """Carga la configuración desde todas las fuentes disponibles."""
        # 1. Cargar valores por defecto
        self._load_defaults()
        
        # 2. Cargar desde archivo de configuración si existe
        if self._config_file and Path(self._config_file).exists():
            self._load_from_file(self._config_file)
        
        # 3. Cargar desde variables de entorno
        self._load_from_environment()
        
        # 4. Validar configuración
        self._validate_configuration()
    
    def _load_defaults(self):
        """Carga los valores por defecto desde constants.py."""
        self._config_data = {
            "shifts": {
                "types": SHIFT_TYPES,
                "technologists_per_shift": TECHS_PER_SHIFT,
                "engineers_per_shift": ENG_PER_SHIFT,
                "schedules": SHIFT_SCHEDULES
            },
            "constraints": {
                "min_rest_hours": MIN_REST_HOURS,
                "max_consecutive_days": MAX_CONSECUTIVE_DAYS,
                "max_consecutive_nights": MAX_CONSECUTIVE_NIGHTS,
                "min_days_off_per_week": MIN_DAYS_OFF_PER_WEEK
            },
            "compensation": {
                "rates": COMPENSATION_RATES,
                "bonuses": SPECIAL_BONUSES
            },
            "generation": GENERATION_LIMITS,
            "optimization": OPTIMIZATION_LIMITS,
            "analysis": ANALYSIS_THRESHOLDS,
            "export": {
                "formats": SUPPORTED_EXPORT_FORMATS,
                "extensions": FILE_EXTENSIONS,
                "max_sizes": MAX_FILE_SIZES
            },
            "cache": CACHE_CONFIG,
            "backup": BACKUP_CONFIG,
            "notifications": {
                "types": NOTIFICATION_TYPES,
                "email": EMAIL_CONFIG
            },
            "quality": {
                "scores": QUALITY_SCORES,
                "weights": QUALITY_WEIGHTS
            },
            "logging": LOGGING_CONFIG,
            "holidays": {
                "fixed": FIXED_HOLIDAYS,
                "movable": MOVABLE_HOLIDAYS
            },
            "ui": {
                "colors": UI_COLORS,
                "window": WINDOW_CONFIG
            },
            "messages": {
                "success": SUCCESS_MESSAGES,
                "error": ERROR_MESSAGES,
                "warning": WARNING_MESSAGES
            },
            "debug": DEBUG_CONFIG,
            "test": TEST_CONFIG
        }
    
    def _load_from_file(self, config_file: str):
        """Carga configuración desde archivo JSON."""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                file_config = json.load(f)
            
            # Merge de configuración usando deep update
            self._deep_update(self._config_data, file_config)
            
        except Exception as e:
            print(f"Warning: No se pudo cargar el archivo de configuración {config_file}: {e}")
    
    def _load_from_environment(self):
        """Carga configuración desde variables de entorno."""
        # Mapeo de variables de entorno a configuración
        env_mappings = {
            "SHIFT_SCHEDULER_DEBUG": ("debug", "enable_debug", bool),
            "SHIFT_SCHEDULER_LOG_LEVEL": ("logging", "level", str),
            "SHIFT_SCHEDULER_MAX_WORKERS": ("generation", "max_workers", int),
            "SHIFT_SCHEDULER_CACHE_TTL": ("cache", "default_ttl", int),
            "SHIFT_SCHEDULER_BACKUP_ENABLED": ("backup", "auto_backup", bool),
            "SHIFT_SCHEDULER_TEST_MODE": ("test", "enable_test_mode", bool)
        }
        
        for env_var, (section, key, var_type) in env_mappings.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                try:
                    if var_type == bool:
                        value = env_value.lower() in ('true', '1', 'yes', 'on')
                    elif var_type == int:
                        value = int(env_value)
                    else:
                        value = env_value
                    
                    if section not in self._config_data:
                        self._config_data[section] = {}
                    self._config_data[section][key] = value
                    
                except ValueError as e:
                    print(f"Warning: Valor inválido para {env_var}: {env_value}")
    
    def _validate_configuration(self):
        """Valida que la configuración sea coherente."""
        errors = []
        
        # Validar configuración de turnos
        if self._config_data["shifts"]["engineers_per_shift"] < 1:
            errors.append("Debe haber al menos 1 ingeniero por turno")
        
        # Validar restricciones laborales
        if self._config_data["constraints"]["min_rest_hours"] < 8:
            errors.append("El descanso mínimo no puede ser menor a 8 horas")
        
        if self._config_data["constraints"]["max_consecutive_days"] > 10:
            errors.append("No se pueden tener más de 10 días consecutivos")
        
        # Validar límites de generación
        if self._config_data["generation"]["max_attempts"] < 1:
            errors.append("Debe haber al menos 1 intento de generación")
        
        if errors:
            raise ValueError("Errores en la configuración: " + "; ".join(errors))
    
    def _deep_update(self, base_dict: dict, update_dict: dict):
        """Actualiza recursivamente un diccionario."""
        for key, value in update_dict.items():
            if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                self._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value
    
    # =====================================================================
    # Métodos de acceso a configuración específica
    # =====================================================================
    
    def get_shift_config(self) -> Dict[str, Any]:
        """Obtiene la configuración de turnos."""
        return self._config_data["shifts"]
    
    def get_constraint_config(self) -> Dict[str, Any]:
        """Obtiene la configuración de restricciones."""
        return self._config_data["constraints"]
    
    def get_compensation_config(self) -> Dict[str, Any]:
        """Obtiene la configuración de compensaciones."""
        return self._config_data["compensation"]
    
    def get_generation_config(self) -> Dict[str, Any]:
        """Obtiene la configuración de generación."""
        return self._config_data["generation"]
    
    def get_optimization_config(self) -> Dict[str, Any]:
        """Obtiene la configuración de optimización."""
        return self._config_data["optimization"]
    
    def get_export_config(self) -> Dict[str, Any]:
        """Obtiene la configuración de exportación."""
        return self._config_data["export"]
    
    def get_cache_config(self) -> Dict[str, Any]:
        """Obtiene la configuración de caché."""
        return self._config_data["cache"]
    
    def get_logging_config(self) -> Dict[str, Any]:
        """Obtiene la configuración de logging."""
        return self._config_data["logging"]
    
    def get_holiday_config(self) -> Dict[str, Any]:
        """Obtiene la configuración de festivos."""
        return self._config_data["holidays"]
    
    def get_ui_config(self) -> Dict[str, Any]:
        """Obtiene la configuración de interfaz de usuario."""
        return self._config_data["ui"]
    
    def get_notification_config(self) -> Dict[str, Any]:
        """Obtiene la configuración de notificaciones."""
        return self._config_data["notifications"]
    
    def get_quality_config(self) -> Dict[str, Any]:
        """Obtiene la configuración de calidad."""
        return self._config_data["quality"]
    
    # =====================================================================
    # Métodos de utilidad
    # =====================================================================
    
    def is_debug_enabled(self) -> bool:
        """Verifica si el modo debug está habilitado."""
        return self._config_data["debug"]["enable_debug"]
    
    def is_test_mode(self) -> bool:
        """Verifica si el modo test está habilitado."""
        return self._config_data["test"]["enable_test_mode"]
    
    def get_supported_export_formats(self) -> List[str]:
        """Obtiene los formatos de exportación soportados."""
        return self._config_data["export"]["formats"]
    
    def get_max_file_size(self, format: str) -> int:
        """Obtiene el tamaño máximo de archivo para un formato."""
        return self._config_data["export"]["max_sizes"].get(format, 10)
    
    def get_cache_ttl(self, cache_type: str = "default") -> int:
        """Obtiene el TTL para un tipo específico de caché."""
        key = f"{cache_type}_ttl"
        return self._config_data["cache"].get(key, self._config_data["cache"]["default_ttl"])
    
    def get_compensation_rate(self, rate_type: str) -> float:
        """Obtiene una tasa de compensación específica."""
        return self._config_data["compensation"]["rates"].get(rate_type, 1.0)
    
    def get_quality_threshold(self, level: str) -> float:
        """Obtiene el umbral para un nivel de calidad específico."""
        return self._config_data["quality"]["scores"].get(level, 50.0)
    
    def get_message(self, category: str, key: str) -> str:
        """Obtiene un mensaje del sistema."""
        return self._config_data["messages"].get(category, {}).get(key, f"Mensaje no encontrado: {category}.{key}")
    
    # =====================================================================
    # Métodos de configuración dinámica
    # =====================================================================
    
    def update_setting(self, path: str, value: Any):
        """
        Actualiza un valor de configuración dinámicamente.
        
        Args:
            path: Ruta del setting en formato "section.key" o "section.subsection.key"
            value: Nuevo valor
        """
        keys = path.split('.')
        current = self._config_data
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        current[keys[-1]] = value
    
    def get_setting(self, path: str, default: Any = None) -> Any:
        """
        Obtiene un valor de configuración por ruta.
        
        Args:
            path: Ruta del setting en formato "section.key"
            default: Valor por defecto si no se encuentra
            
        Returns:
            Valor de configuración o default
        """
        keys = path.split('.')
        current = self._config_data
        
        try:
            for key in keys:
                current = current[key]
            return current
        except KeyError:
            return default
    
    def save_to_file(self, filename: str):
        """
        Guarda la configuración actual a un archivo.
        
        Args:
            filename: Nombre del archivo donde guardar
        """
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self._config_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            raise Exception(f"Error al guardar configuración: {e}")
    
    def reset_to_defaults(self):
        """Resetea la configuración a los valores por defecto."""
        self._load_defaults()
    
    def get_all_config(self) -> Dict[str, Any]:
        """Obtiene toda la configuración como diccionario."""
        return self._config_data.copy()


# =====================================================================
# Instancia global de configuración
# =====================================================================

# Instancia global que puede ser importada y usada en toda la aplicación
settings = Settings()

# Funciones de conveniencia para acceso rápido
def get_shift_types() -> List[str]:
    """Obtiene los tipos de turno disponibles."""
    return settings.get_shift_config()["types"]

def get_techs_per_shift() -> Dict[str, int]:
    """Obtiene el número de tecnólogos requeridos por turno."""
    return settings.get_shift_config()["technologists_per_shift"]

def get_engineers_per_shift() -> int:
    """Obtiene el número de ingenieros requeridos por turno."""
    return settings.get_shift_config()["engineers_per_shift"]

def get_compensation_rate(rate_type: str) -> float:
    """Obtiene una tasa de compensación específica."""
    return settings.get_compensation_rate(rate_type)

def is_debug_mode() -> bool:
    """Verifica si está en modo debug."""
    return settings.is_debug_enabled()

def get_cache_ttl(cache_type: str = "default") -> int:
    """Obtiene el TTL de caché."""
    return settings.get_cache_ttl(cache_type)