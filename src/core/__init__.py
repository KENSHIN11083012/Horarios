"""
Core Domain - Dominio puro del sistema de horarios.

Este paquete contiene toda la lógica de dominio pura del sistema,
incluyendo modelos, reglas de negocio y servicios de dominio.
"""

# Models - Entidades y objetos de valor
from .models import (
    # Worker models
    Worker,
    WorkerType,
    
    # Schedule models
    Schedule,
    DaySchedule,
    ShiftAssignment,
    
    # Shift models
    ShiftType,
    ShiftTime,
    ShiftCharacteristics,
    ShiftRequirement,
    ShiftDefinition,
    ShiftRegistry,
    shift_registry
)

# Rules - Reglas de negocio y validadores
from .rules import (
    # Interfaces
    ConstraintRule,
    ScheduleValidator,
    OptimizationRule,
    CompensationCalculator,
    HolidayProvider,
    ConstraintChecker,
    WorkloadBalancer,
    EquityAnalyzer,
    
    # Constraint implementations
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
    RELAXED_CONSTRAINTS,
    
    # Validators
    CoverageValidator,
    ConstraintValidator,
    DataIntegrityValidator,
    WeeklyDayOffValidator,
    BasicConstraintChecker,
    CompositeValidator,
    default_validator
)

# Services - Servicios de dominio
from .services import (
    # Generator
    ScheduleGenerator,
    WorkerSelector,
    CriticalDayAnalyzer,
    AssignmentStrategy,
    GenerationContext,
    AssignmentResult,
    
    # Optimizer
    ScheduleOptimizer,
    OptimizerWorkloadAnalyzer,
    OptimizerCompensationAnalyzer,
    SwapGenerator,
    OptimizationObjective,
    OptimizationConfig,
    OptimizationResult,
    SwapProposal,
    
    # Analyzer
    ScheduleAnalyzer,
    WorkloadAnalyzer,
    CompensationAnalyzer,
    DayOffAnalyzer,
    CoverageAnalyzer,
    AnalysisType,
    WorkerStatistics,
    GroupStatistics,
    DayOffAnalysis,
    CoverageAnalysis,
    ScheduleAnalysisReport
)

__all__ = [
    # Models
    'Worker',
    'WorkerType',
    'Schedule',
    'DaySchedule',
    'ShiftAssignment',
    'ShiftType',
    'ShiftTime',
    'ShiftCharacteristics',
    'ShiftRequirement',
    'ShiftDefinition',
    'ShiftRegistry',
    'shift_registry',
    
    # Rules
    'ConstraintRule',
    'ScheduleValidator',
    'OptimizationRule',
    'CompensationCalculator',
    'HolidayProvider',
    'ConstraintChecker',
    'WorkloadBalancer',
    'EquityAnalyzer',
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
    'CoverageValidator',
    'ConstraintValidator',
    'DataIntegrityValidator',
    'WeeklyDayOffValidator',
    'BasicConstraintChecker',
    'CompositeValidator',
    'default_validator',
    
    # Services
    'ScheduleGenerator',
    'WorkerSelector',
    'CriticalDayAnalyzer',
    'AssignmentStrategy',
    'GenerationContext',
    'AssignmentResult',
    'ScheduleOptimizer',
    'OptimizerWorkloadAnalyzer',
    'OptimizerCompensationAnalyzer',
    'SwapGenerator',
    'OptimizationObjective',
    'OptimizationConfig',
    'OptimizationResult',
    'SwapProposal',
    'ScheduleAnalyzer',
    'WorkloadAnalyzer',
    'CompensationAnalyzer',
    'DayOffAnalyzer',
    'CoverageAnalyzer',
    'AnalysisType',
    'WorkerStatistics',
    'GroupStatistics',
    'DayOffAnalysis',
    'CoverageAnalysis',
    'ScheduleAnalysisReport',
]