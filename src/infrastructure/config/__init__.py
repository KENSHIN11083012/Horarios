"""
Infrastructure Config - Configuración del sistema.

Este paquete contiene toda la configuración del sistema,
incluyendo constantes, configuraciones y utilidades.
"""

from .constants import (
    SHIFT_TYPES,
    TECHS_PER_SHIFT,
    ENG_PER_SHIFT,
    SHIFT_SCHEDULES,
    MIN_REST_HOURS,
    MAX_CONSECUTIVE_DAYS,
    COMPENSATION_RATES,
    GENERATION_LIMITS,
    OPTIMIZATION_LIMITS,
    SUPPORTED_EXPORT_FORMATS,
    CACHE_CONFIG,
    QUALITY_SCORES
)

from .settings import (
    Settings,
    settings,
    get_shift_types,
    get_techs_per_shift,
    get_engineers_per_shift,
    get_compensation_rate,
    is_debug_mode,
    get_cache_ttl
)

__all__ = [
    # Constants
    'SHIFT_TYPES',
    'TECHS_PER_SHIFT',
    'ENG_PER_SHIFT',
    'SHIFT_SCHEDULES',
    'MIN_REST_HOURS',
    'MAX_CONSECUTIVE_DAYS',
    'COMPENSATION_RATES',
    'GENERATION_LIMITS',
    'OPTIMIZATION_LIMITS',
    'SUPPORTED_EXPORT_FORMATS',
    'CACHE_CONFIG',
    'QUALITY_SCORES',
    
    # Settings
    'Settings',
    'settings',
    'get_shift_types',
    'get_techs_per_shift',
    'get_engineers_per_shift',
    'get_compensation_rate',
    'is_debug_mode',
    'get_cache_ttl',
]