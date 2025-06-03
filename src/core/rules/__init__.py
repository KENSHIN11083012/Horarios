"""
Core Rules - Reglas de dominio para el sistema de horarios.

Este paquete contiene todas las reglas de negocio, restricciones y validadores
que definen cómo deben comportarse las asignaciones de turnos.
"""

# Interfaces
from .interfaces import (
    ConstraintRule,
    ScheduleValidator,
    OptimizationRule,
    CompensationCalculator,
    HolidayProvider,
    ConstraintChecker,
    WorkloadBalancer,
    EquityAnalyzer
)

# Implementaciones concretas de restricciones
from .constraints import (
    AdequateRestConstraint,
    RelaxedRestConstraint,
    NightToDayTransitionConstraint,
    ConsecutiveShiftsConstraint,
    DayOffRespectConstraint,
    SingleShiftPerDayConstraint,
    MaxConsecutiveDaysConstraint,
    WorkloadBalanceConstraint,
    ShiftTypeBalanceConstraint,
    DEFAULT_CONSTRAINTS,
    RELAXED_CONSTRAINTS
)

# Validadores
from .validators import (
    CoverageValidator,
    ConstraintValidator,
    DataIntegrityValidator,
    WeeklyDayOffValidator,
    BasicConstraintChecker,
    CompositeValidator,
    default_validator
)

__all__ = [
    # Interfaces
    'ConstraintRule',
    'ScheduleValidator',
    'OptimizationRule',
    'CompensationCalculator',
    'HolidayProvider',
    'ConstraintChecker',
    'WorkloadBalancer',
    'EquityAnalyzer',
    
    # Constraint implementations
    'AdequateRestConstraint',
    'RelaxedRestConstraint',
    'NightToDayTransitionConstraint',
    'ConsecutiveShiftsConstraint',
    'DayOffRespectConstraint',
    'SingleShiftPerDayConstraint',
    'MaxConsecutiveDaysConstraint',
    'WorkloadBalanceConstraint',
    'ShiftTypeBalanceConstraint',
    'DEFAULT_CONSTRAINTS',
    'RELAXED_CONSTRAINTS',
    
    # Validators
    'CoverageValidator',
    'ConstraintValidator',
    'DataIntegrityValidator',
    'WeeklyDayOffValidator',
    'BasicConstraintChecker',
    'CompositeValidator',
    'default_validator',
]