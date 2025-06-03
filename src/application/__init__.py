"""
Application Use Cases - Casos de uso de la capa de aplicación.

Este paquete contiene todos los casos de uso que orquestan
la lógica de negocio del sistema de horarios.
"""

from .use_cases.generate_schedule import (
    GenerateScheduleUseCase,
    ScheduleGenerationRequest,
    GenerationResult,
    GenerationPriority
)

from .use_cases.optimize_schedule import (
    OptimizeScheduleUseCase,
    OptimizationRequest,
    OptimizationResult,
    OptimizationGoal
)

from .use_cases.analyze_schedule import (
    AnalyzeScheduleUseCase,
    AnalysisRequest,
    AnalysisResult,
    AnalysisScope
)

from .use_cases.export_schedule import (
    ExportScheduleUseCase,
    ExportRequest,
    ExportResult,
    ExportFormat,
    ExportLayout,
    ExportOptions
)

__all__ = [
    # Generate Schedule
    'GenerateScheduleUseCase',
    'ScheduleGenerationRequest',
    'GenerationResult',
    'GenerationPriority',
    
    # Optimize Schedule
    'OptimizeScheduleUseCase',
    'OptimizationRequest',
    'OptimizationResult',
    'OptimizationGoal',
    
    # Analyze Schedule
    'AnalyzeScheduleUseCase',
    'AnalysisRequest',
    'AnalysisResult',
    'AnalysisScope',
    
    # Export Schedule
    'ExportScheduleUseCase',
    'ExportRequest',
    'ExportResult',
    'ExportFormat',
    'ExportLayout',
    'ExportOptions',
]