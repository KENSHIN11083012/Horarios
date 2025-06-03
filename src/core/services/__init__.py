"""
Core Services - Servicios de dominio para el sistema de horarios.

Este paquete contiene los servicios que orquestan la lógica de dominio,
incluyendo generación, optimización y análisis de horarios.
"""

# Generator service
from .generator import (
    ScheduleGenerator,
    WorkerSelector,
    CriticalDayAnalyzer,
    AssignmentStrategy,
    GenerationContext,
    AssignmentResult
)

# Optimizer service
from .optimizer import (
    ScheduleOptimizer,
    WorkloadAnalyzer as OptimizerWorkloadAnalyzer,
    CompensationAnalyzer as OptimizerCompensationAnalyzer,
    SwapGenerator,
    OptimizationObjective,
    OptimizationConfig,
    OptimizationResult,
    SwapProposal
)

# Analyzer service
from .analyzer import (
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
    # Generator
    'ScheduleGenerator',
    'WorkerSelector',
    'CriticalDayAnalyzer',
    'AssignmentStrategy',
    'GenerationContext',
    'AssignmentResult',
    
    # Optimizer
    'ScheduleOptimizer',
    'OptimizerWorkloadAnalyzer',
    'OptimizerCompensationAnalyzer',
    'SwapGenerator',
    'OptimizationObjective',
    'OptimizationConfig',
    'OptimizationResult',
    'SwapProposal',
    
    # Analyzer
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