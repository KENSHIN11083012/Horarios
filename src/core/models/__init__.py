"""
Core Models - Modelos de dominio puro para el sistema de horarios.

Este paquete contiene todas las entidades y objetos de valor del dominio,
sin dependencias externas ni lógica de infraestructura.
"""

from .worker import Worker, WorkerType
from .schedule import Schedule, DaySchedule, ShiftAssignment
from .shift import (
    ShiftType, 
    ShiftTime, 
    ShiftCharacteristics, 
    ShiftRequirement, 
    ShiftDefinition, 
    ShiftRegistry,
    shift_registry
)

__all__ = [
    # Worker models
    'Worker',
    'WorkerType',
    
    # Schedule models
    'Schedule',
    'DaySchedule', 
    'ShiftAssignment',
    
    # Shift models
    'ShiftType',
    'ShiftTime',
    'ShiftCharacteristics',
    'ShiftRequirement',
    'ShiftDefinition',
    'ShiftRegistry',
    'shift_registry',
]