"""
Servicio de análisis de horarios - Dominio puro.

Este módulo contiene la lógica de dominio para analizar horarios,
generando métricas, estadísticas y reportes detallados.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import math

from ..models import Worker, Schedule, ShiftType, WorkerType
from ..rules.interfaces import CompensationCalculator, HolidayProvider


class AnalysisType(Enum):
    """Tipos de análisis disponibles."""
    WORKLOAD_DISTRIBUTION = "workload_distribution"
    COMPENSATION_EQUITY = "compensation_equity"
    DAYS_OFF_COMPLIANCE = "days_off_compliance"
    SHIFT_COVERAGE = "shift_coverage"
    CONSTRAINT_VIOLATIONS = "constraint_violations"
    COMPREHENSIVE = "comprehensive"


@dataclass
class WorkerStatistics:
    """Estadísticas detalladas de un trabajador."""
    worker_id: str
    worker_type: str
    total_shifts: int
    shift_distribution: Dict[str, int]
    days_off_count: int
    compensation_total: float
    compensation_breakdown: Dict[str, Dict[str, Any]]
    workload_score: float
    equity_score: float
    violations: List[str] = field(default_factory=list)
    
    @property
    def average_shifts_per_week(self) -> float:
        """Promedio de turnos por semana (asumiendo 4 semanas)."""
        return self.total_shifts / 4.0 if self.total_shifts > 0 else 0.0
    
    @property
    def compensation_per_shift(self) -> float:
        """Compensación promedio por turno."""
        return self.compensation_total / self.total_shifts if self.total_shifts > 0 else 0.0


@dataclass
class GroupStatistics:
    """Estadísticas de un grupo de trabajadores (tecnólogos o ingenieros)."""
    group_type: str
    worker_count: int
    total_shifts: int
    average_shifts_per_worker: float
    shift_distribution: Dict[str, int]
    compensation_stats: Dict[str, float]
    workload_balance_score: float
    compensation_equity_score: float
    
    @property
    def shifts_per_worker_per_week(self) -> float:
        """Promedio de turnos por trabajador por semana."""
        return (self.total_shifts / self.worker_count / 4.0) if self.worker_count > 0 else 0.0


@dataclass
class DayOffAnalysis:
    """Análisis de días libres."""
    total_workers: int
    workers_with_weekly_day_off: int
    workers_without_weekly_day_off: List[Dict[str, Any]]
    day_off_distribution: Dict[str, int]
    workers_with_post_night_day_off: List[Dict[str, Any]]
    compliance_percentage: float
    
    @property
    def weekly_compliance_rate(self) -> float:
        """Tasa de cumplimiento de día libre semanal."""
        return (self.workers_with_weekly_day_off / self.total_workers * 100) if self.total_workers > 0 else 0.0


@dataclass
class CoverageAnalysis:
    """Análisis de cobertura de turnos."""
    total_shifts: int
    properly_covered_shifts: int
    under_covered_shifts: List[Dict[str, Any]]
    over_covered_shifts: List[Dict[str, Any]]
    coverage_by_shift_type: Dict[str, Dict[str, int]]
    coverage_percentage: float
    
    @property
    def coverage_rate(self) -> float:
        """Tasa de cobertura adecuada."""
        return (self.properly_covered_shifts / self.total_shifts * 100) if self.total_shifts > 0 else 0.0


@dataclass
class ScheduleAnalysisReport:
    """Reporte completo de análisis de horario."""
    schedule_period: str
    analysis_date: datetime
    summary_stats: Dict[str, Any]
    technologist_stats: GroupStatistics
    engineer_stats: GroupStatistics
    individual_worker_stats: List[WorkerStatistics]
    days_off_analysis: DayOffAnalysis
    coverage_analysis: CoverageAnalysis
    constraint_violations: List[str]
    recommendations: List[str]
    overall_quality_score: float


class WorkloadAnalyzer:
    """
    Analizador especializado en distribución de carga de trabajo.
    """
    
    def analyze_workload_distribution(self, schedule: Schedule) -> Dict[str, Any]:
        """
        Analiza la distribución de carga de trabajo.
        
        Args:
            schedule: Horario a analizar
            
        Returns:
            Dict: Análisis de distribución de carga
        """
        technologists = schedule.get_technologists()
        engineers = schedule.get_engineers()
        
        tech_analysis = self._analyze_group_workload(technologists, "Tecnólogos")
        eng_analysis = self._analyze_group_workload(engineers, "Ingenieros")
        
        return {
            "technologists": tech_analysis,
            "engineers": eng_analysis,
            "overall_balance_score": (tech_analysis["balance_score"] + eng_analysis["balance_score"]) / 2
        }
    
    def _analyze_group_workload(self, workers: List[Worker], group_name: str) -> Dict[str, Any]:
        """Analiza la carga de trabajo de un grupo específico."""
        if not workers:
            return {
                "group_name": group_name,
                "worker_count": 0,
                "balance_score": 1.0,
                "statistics": {},
                "distribution": []
            }
        
        # Obtener distribución de turnos
        shift_counts = [w.get_total_shifts() for w in workers]
        shift_type_counts = {}
        
        # Inicializar contadores por tipo
        for shift_type in ["Mañana", "Tarde", "Noche"]:
            shift_type_counts[shift_type] = [w.get_shift_types_count().get(shift_type, 0) for w in workers]
        
        # Calcular estadísticas
        stats = {
            "mean": sum(shift_counts) / len(shift_counts),
            "min": min(shift_counts),
            "max": max(shift_counts),
            "std_dev": self._calculate_std_dev(shift_counts),
            "range": max(shift_counts) - min(shift_counts),
            "coefficient_of_variation": 0.0
        }
        
        if stats["mean"] > 0:
            stats["coefficient_of_variation"] = stats["std_dev"] / stats["mean"]
        
        # Calcular score de balance (menor CV = mejor balance)
        balance_score = max(0.0, 1.0 - stats["coefficient_of_variation"])
        
        # Distribución detallada por trabajador
        distribution = []
        for worker in workers:
            shift_distribution = worker.get_shift_types_count()
            distribution.append({
                "worker_id": worker.get_formatted_id(),
                "total_shifts": worker.get_total_shifts(),
                "morning_shifts": shift_distribution.get("Mañana", 0),
                "afternoon_shifts": shift_distribution.get("Tarde", 0),
                "night_shifts": shift_distribution.get("Noche", 0),
                "compensation": worker.earnings
            })
        
        return {
            "group_name": group_name,
            "worker_count": len(workers),
            "balance_score": balance_score,
            "statistics": stats,
            "shift_type_balance": {
                shift_type: {
                    "mean": sum(counts) / len(counts),
                    "std_dev": self._calculate_std_dev(counts)
                }
                for shift_type, counts in shift_type_counts.items()
            },
            "distribution": distribution
        }
    
    def _calculate_std_dev(self, values: List[float]) -> float:
        """Calcula la desviación estándar."""
        if not values:
            return 0.0
        
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return math.sqrt(variance)


class CompensationAnalyzer:
    """
    Analizador especializado en equidad de compensaciones.
    """
    
    def __init__(self, compensation_calculator: Optional[CompensationCalculator] = None,
                 holiday_provider: Optional[HolidayProvider] = None):
        """
        Inicializa el analizador.
        
        Args:
            compensation_calculator: Calculador de compensaciones (opcional)
            holiday_provider: Proveedor de festivos (opcional)
        """
        self.compensation_calculator = compensation_calculator
        self.holiday_provider = holiday_provider
    
    def analyze_compensation_equity(self, schedule: Schedule) -> Dict[str, Any]:
        """
        Analiza la equidad en compensaciones.
        
        Args:
            schedule: Horario a analizar
            
        Returns:
            Dict: Análisis de equidad de compensaciones
        """
        # Recalcular compensaciones si tenemos calculador
        if self.compensation_calculator:
            self._recalculate_compensations(schedule)
        
        technologists = schedule.get_technologists()
        engineers = schedule.get_engineers()
        
        tech_analysis = self._analyze_group_compensation(technologists, "Tecnólogos", schedule)
        eng_analysis = self._analyze_group_compensation(engineers, "Ingenieros", schedule)
        
        return {
            "technologists": tech_analysis,
            "engineers": eng_analysis,
            "overall_equity_score": (tech_analysis["equity_score"] + eng_analysis["equity_score"]) / 2
        }
    
    def _recalculate_compensations(self, schedule: Schedule):
        """Recalcula las compensaciones de todos los trabajadores."""
        for worker in schedule.get_all_workers():
            total_compensation = self.compensation_calculator.calculate_worker_total_compensation(worker)
            worker.earnings = total_compensation
    
    def _analyze_group_compensation(self, workers: List[Worker], group_name: str, schedule: Schedule) -> Dict[str, Any]:
        """Analiza la compensación de un grupo específico."""
        if not workers:
            return {
                "group_name": group_name,
                "worker_count": 0,
                "equity_score": 1.0,
                "statistics": {},
                "breakdown": []
            }
        
        # Obtener compensaciones
        compensations = [w.earnings for w in workers]
        
        # Calcular estadísticas
        stats = {
            "mean": sum(compensations) / len(compensations),
            "min": min(compensations),
            "max": max(compensations),
            "std_dev": self._calculate_std_dev(compensations),
            "range": max(compensations) - min(compensations),
            "range_percentage": 0.0
        }
        
        if stats["min"] > 0:
            stats["range_percentage"] = (stats["range"] / stats["min"]) * 100
        
        # Calcular score de equidad (menor diferencia porcentual = mejor equidad)
        equity_score = max(0.0, 1.0 - min(stats["range_percentage"] / 25.0, 1.0))  # 25% como máximo aceptable
        
        # Desglose detallado por trabajador
        breakdown = []
        for worker in workers:
            comp_breakdown = self._calculate_worker_compensation_breakdown(worker, schedule)
            breakdown.append({
                "worker_id": worker.get_formatted_id(),
                "total_compensation": worker.earnings,
                "total_shifts": worker.get_total_shifts(),
                "compensation_per_shift": worker.earnings / worker.get_total_shifts() if worker.get_total_shifts() > 0 else 0,
                "breakdown": comp_breakdown
            })
        
        return {
            "group_name": group_name,
            "worker_count": len(workers),
            "equity_score": equity_score,
            "statistics": stats,
            "breakdown": breakdown
        }
    
    def _calculate_worker_compensation_breakdown(self, worker: Worker, schedule: Schedule) -> Dict[str, Dict[str, Any]]:
        """Calcula el desglose detallado de compensación de un trabajador."""
        breakdown = {
            "regular": {"count": 0, "compensation": 0.0},
            "night": {"count": 0, "compensation": 0.0},
            "weekend_day": {"count": 0, "compensation": 0.0},
            "weekend_night": {"count": 0, "compensation": 0.0},
            "holiday_day": {"count": 0, "compensation": 0.0},
            "holiday_night": {"count": 0, "compensation": 0.0}
        }
        
        for date, shift_type in worker.shifts:
            is_night = shift_type == "Noche"
            is_weekend = date.weekday() >= 5
            is_holiday = self.holiday_provider.is_holiday(date) if self.holiday_provider else False
            
            # Calcular compensación del turno
            if self.compensation_calculator:
                shift_comp = self.compensation_calculator.calculate_shift_compensation(date, ShiftType.from_string(shift_type))
            else:
                shift_comp = 1.0  # Valor por defecto
            
            # Clasificar el turno
            if is_holiday:
                category = "holiday_night" if is_night else "holiday_day"
            elif is_weekend:
                category = "weekend_night" if is_night else "weekend_day"
            elif is_night:
                category = "night"
            else:
                category = "regular"
            
            breakdown[category]["count"] += 1
            breakdown[category]["compensation"] += shift_comp
        
        return breakdown
    
    def _calculate_std_dev(self, values: List[float]) -> float:
        """Calcula la desviación estándar."""
        if not values:
            return 0.0
        
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return math.sqrt(variance)


class DayOffAnalyzer:
    """
    Analizador especializado en días libres.
    """
    
    def analyze_days_off_compliance(self, schedule: Schedule) -> DayOffAnalysis:
        """
        Analiza el cumplimiento de días libres semanales.
        
        Args:
            schedule: Horario a analizar
            
        Returns:
            DayOffAnalysis: Análisis de días libres
        """
        all_workers = schedule.get_all_workers()
        weeks = self._get_weeks_in_period(schedule)
        
        # Analizar cada trabajador
        workers_without_weekly_day_off = []
        workers_with_post_night_day_off = []
        day_off_distribution = {"Monday": 0, "Tuesday": 0, "Wednesday": 0, "Thursday": 0, 
                               "Friday": 0, "Saturday": 0, "Sunday": 0}
        
        workers_with_compliance = 0
        
        for worker in all_workers:
            has_weekly_compliance = True
            post_night_days_off = 0
            
            # Analizar cada semana
            for week_start, week_end, effective_start, effective_end in weeks:
                # Días libres en esta semana
                days_off_in_week = worker.get_days_off_in_date_range(effective_start, effective_end)
                
                # Verificar cumplimiento semanal
                effective_days = (effective_end - effective_start).days + 1
                if effective_days >= 3 and not days_off_in_week:
                    has_weekly_compliance = False
                    workers_without_weekly_day_off.append({
                        "worker_id": worker.get_formatted_id(),
                        "week": f"{effective_start.strftime('%d/%m')} - {effective_end.strftime('%d/%m')}",
                        "effective_days": effective_days
                    })
                
                # Analizar días libres después de turnos nocturnos
                for day_off in days_off_in_week:
                    # Distribución por día de la semana
                    day_name = day_off.strftime("%A")
                    if day_name in day_off_distribution:
                        day_off_distribution[day_name] += 1
                    
                    # Verificar si es después de turno nocturno
                    prev_day = day_off - timedelta(days=1)
                    if worker.worked_night_shift_on(prev_day):
                        post_night_days_off += 1
            
            if has_weekly_compliance:
                workers_with_compliance += 1
            
            if post_night_days_off > 0:
                workers_with_post_night_day_off.append({
                    "worker_id": worker.get_formatted_id(),
                    "count": post_night_days_off
                })
        
        compliance_percentage = (workers_with_compliance / len(all_workers) * 100) if all_workers else 100.0
        
        return DayOffAnalysis(
            total_workers=len(all_workers),
            workers_with_weekly_day_off=workers_with_compliance,
            workers_without_weekly_day_off=workers_without_weekly_day_off,
            day_off_distribution=day_off_distribution,
            workers_with_post_night_day_off=workers_with_post_night_day_off,
            compliance_percentage=compliance_percentage
        )
    
    def _get_weeks_in_period(self, schedule: Schedule) -> List[Tuple[datetime, datetime, datetime, datetime]]:
        """Obtiene todas las semanas del período."""
        from ...shared.utils import get_week_start, get_week_end
        
        weeks = []
        current_week_start = get_week_start(schedule.start_date)
        end_date_week_start = get_week_start(schedule.end_date)
        
        while current_week_start <= end_date_week_start:
            week_end = get_week_end(current_week_start)
            
            if not (week_end < schedule.start_date or current_week_start > schedule.end_date):
                effective_start = max(current_week_start, schedule.start_date)
                effective_end = min(week_end, schedule.end_date)
                weeks.append((current_week_start, week_end, effective_start, effective_end))
            
            current_week_start += timedelta(days=7)
        
        return weeks


class CoverageAnalyzer:
    """
    Analizador especializado en cobertura de turnos.
    """
    
    def analyze_shift_coverage(self, schedule: Schedule) -> CoverageAnalysis:
        """
        Analiza la cobertura de todos los turnos.
        
        Args:
            schedule: Horario a analizar
            
        Returns:
            CoverageAnalysis: Análisis de cobertura
        """
        from ...infrastructure.config.settings import TECHS_PER_SHIFT, ENG_PER_SHIFT
        
        total_shifts = 0
        properly_covered = 0
        under_covered = []
        over_covered = []
        coverage_by_type = {"Mañana": {"total": 0, "proper": 0}, 
                           "Tarde": {"total": 0, "proper": 0}, 
                           "Noche": {"total": 0, "proper": 0}}
        
        for day_schedule in schedule.days:
            date_str = day_schedule.date.strftime("%Y-%m-%d")
            
            for shift_type, assignment in day_schedule.shifts.items():
                total_shifts += 1
                coverage_info = schedule.get_shift_coverage(day_schedule.date, shift_type)
                
                coverage_by_type[shift_type]["total"] += 1
                
                if coverage_info["complete"]:
                    properly_covered += 1
                    coverage_by_type[shift_type]["proper"] += 1
                else:
                    # Determinar si es sub-cobertura o sobre-cobertura
                    tech_req = coverage_info["technologists"]["required"]
                    tech_assigned = coverage_info["technologists"]["assigned"]
                    eng_req = coverage_info["engineer"]["required"]
                    eng_assigned = coverage_info["engineer"]["assigned"]
                    
                    if tech_assigned < tech_req or eng_assigned < eng_req:
                        under_covered.append({
                            "date": date_str,
                            "shift_type": shift_type,
                            "technologists_needed": tech_req - tech_assigned,
                            "engineers_needed": eng_req - eng_assigned
                        })
                    elif tech_assigned > tech_req or eng_assigned > eng_req:
                        over_covered.append({
                            "date": date_str,
                            "shift_type": shift_type,
                            "excess_technologists": tech_assigned - tech_req,
                            "excess_engineers": eng_assigned - eng_req
                        })
        
        coverage_percentage = (properly_covered / total_shifts * 100) if total_shifts > 0 else 0.0
        
        return CoverageAnalysis(
            total_shifts=total_shifts,
            properly_covered_shifts=properly_covered,
            under_covered_shifts=under_covered,
            over_covered_shifts=over_covered,
            coverage_by_shift_type=coverage_by_type,
            coverage_percentage=coverage_percentage
        )


class ScheduleAnalyzer:
    """
    Analizador principal de horarios.
    
    Orquesta todos los análisis especializados y genera reportes comprehensivos.
    """
    
    def __init__(self, 
                 compensation_calculator: Optional[CompensationCalculator] = None,
                 holiday_provider: Optional[HolidayProvider] = None):
        """
        Inicializa el analizador.
        
        Args:
            compensation_calculator: Calculador de compensaciones (opcional)
            holiday_provider: Proveedor de festivos (opcional)
        """
        self.workload_analyzer = WorkloadAnalyzer()
        self.compensation_analyzer = CompensationAnalyzer(compensation_calculator, holiday_provider)
        self.day_off_analyzer = DayOffAnalyzer()
        self.coverage_analyzer = CoverageAnalyzer()
    
    def analyze_schedule(self, schedule: Schedule, analysis_types: Optional[List[AnalysisType]] = None) -> ScheduleAnalysisReport:
        """
        Realiza un análisis completo del horario.
        
        Args:
            schedule: Horario a analizar
            analysis_types: Tipos de análisis a realizar (opcional, por defecto todos)
            
        Returns:
            ScheduleAnalysisReport: Reporte completo de análisis
        """
        if analysis_types is None:
            analysis_types = [AnalysisType.COMPREHENSIVE]
        
        # Análisis base siempre se ejecuta
        summary_stats = self._generate_summary_statistics(schedule)
        
        # Análisis específicos
        workload_analysis = None
        compensation_analysis = None
        days_off_analysis = None
        coverage_analysis = None
        
        if AnalysisType.COMPREHENSIVE in analysis_types or AnalysisType.WORKLOAD_DISTRIBUTION in analysis_types:
            workload_analysis = self.workload_analyzer.analyze_workload_distribution(schedule)
        
        if AnalysisType.COMPREHENSIVE in analysis_types or AnalysisType.COMPENSATION_EQUITY in analysis_types:
            compensation_analysis = self.compensation_analyzer.analyze_compensation_equity(schedule)
        
        if AnalysisType.COMPREHENSIVE in analysis_types or AnalysisType.DAYS_OFF_COMPLIANCE in analysis_types:
            days_off_analysis = self.day_off_analyzer.analyze_days_off_compliance(schedule)
        
        if AnalysisType.COMPREHENSIVE in analysis_types or AnalysisType.SHIFT_COVERAGE in analysis_types:
            coverage_analysis = self.coverage_analyzer.analyze_shift_coverage(schedule)
        
        # Validación de restricciones
        constraint_violations = []
        if AnalysisType.COMPREHENSIVE in analysis_types or AnalysisType.CONSTRAINT_VIOLATIONS in analysis_types:
            from ..rules.validators import default_validator
            constraint_violations = default_validator.validate(schedule)
        
        # Generar estadísticas de grupos
        tech_stats = self._generate_group_statistics(schedule.get_technologists(), "Tecnólogos")
        eng_stats = self._generate_group_statistics(schedule.get_engineers(), "Ingenieros")
        
        # Generar estadísticas individuales
        individual_stats = self._generate_individual_statistics(schedule.get_all_workers())
        
        # Calcular score de calidad general
        overall_quality_score = self._calculate_overall_quality_score(
            workload_analysis, compensation_analysis, days_off_analysis, 
            coverage_analysis, len(constraint_violations)
        )
        
        # Generar recomendaciones
        recommendations = self._generate_recommendations(
            workload_analysis, compensation_analysis, days_off_analysis, 
            coverage_analysis, constraint_violations
        )
        
        return ScheduleAnalysisReport(
            schedule_period=f"{schedule.start_date.strftime('%Y-%m-%d')} to {schedule.end_date.strftime('%Y-%m-%d')}",
            analysis_date=datetime.now(),
            summary_stats=summary_stats,
            technologist_stats=tech_stats,
            engineer_stats=eng_stats,
            individual_worker_stats=individual_stats,
            days_off_analysis=days_off_analysis or DayOffAnalysis(0, 0, [], {}, [], 0.0),
            coverage_analysis=coverage_analysis or CoverageAnalysis(0, 0, [], [], {}, 0.0),
            constraint_violations=constraint_violations,
            recommendations=recommendations,
            overall_quality_score=overall_quality_score
        )
    
    def _generate_summary_statistics(self, schedule: Schedule) -> Dict[str, Any]:
        """Genera estadísticas resumen del horario."""
        stats = schedule.get_summary_stats()
        
        # Agregar estadísticas adicionales
        all_workers = schedule.get_all_workers()
        total_shifts_assigned = sum(w.get_total_shifts() for w in all_workers)
        total_compensation = sum(w.earnings for w in all_workers)
        
        stats.update({
            "total_shifts_assigned": total_shifts_assigned,
            "total_compensation": total_compensation,
            "average_shifts_per_worker": total_shifts_assigned / len(all_workers) if all_workers else 0,
            "average_compensation_per_worker": total_compensation / len(all_workers) if all_workers else 0
        })
        
        return stats
    
    def _generate_group_statistics(self, workers: List[Worker], group_type: str) -> GroupStatistics:
        """Genera estadísticas para un grupo de trabajadores."""
        if not workers:
            return GroupStatistics(
                group_type=group_type,
                worker_count=0,
                total_shifts=0,
                average_shifts_per_worker=0.0,
                shift_distribution={},
                compensation_stats={},
                workload_balance_score=1.0,
                compensation_equity_score=1.0
            )
        
        # Calcular estadísticas básicas
        total_shifts = sum(w.get_total_shifts() for w in workers)
        avg_shifts = total_shifts / len(workers)
        
        # Distribución por tipo de turno
        shift_distribution = {"Mañana": 0, "Tarde": 0, "Noche": 0}
        for worker in workers:
            worker_dist = worker.get_shift_types_count()
            for shift_type in shift_distribution:
                shift_distribution[shift_type] += worker_dist.get(shift_type, 0)
        
        # Estadísticas de compensación
        compensations = [w.earnings for w in workers]
        compensation_stats = {
            "min": min(compensations) if compensations else 0.0,
            "max": max(compensations) if compensations else 0.0,
            "average": sum(compensations) / len(compensations) if compensations else 0.0,
            "total": sum(compensations)
        }
        
        # Scores de balance y equidad
        workload_balance_score = self.workload_analyzer._analyze_group_workload(workers, group_type)["balance_score"]
        compensation_equity_score = self.compensation_analyzer._analyze_group_compensation(workers, group_type, None)["equity_score"]
        
        return GroupStatistics(
            group_type=group_type,
            worker_count=len(workers),
            total_shifts=total_shifts,
            average_shifts_per_worker=avg_shifts,
            shift_distribution=shift_distribution,
            compensation_stats=compensation_stats,
            workload_balance_score=workload_balance_score,
            compensation_equity_score=compensation_equity_score
        )
    
    def _generate_individual_statistics(self, workers: List[Worker]) -> List[WorkerStatistics]:
        """Genera estadísticas individuales para cada trabajador."""
        individual_stats = []
        
        for worker in workers:
            # Calcular scores individuales
            workload_score = 1.0 - (worker.get_total_shifts() / 35.0)  # Normalizar asumiendo 35 turnos máximo
            workload_score = max(0.0, min(1.0, workload_score))
            
            equity_score = 0.5  # Placeholder - necesitaría comparación con grupo
            
            worker_stat = WorkerStatistics(
                worker_id=worker.get_formatted_id(),
                worker_type="Tecnólogo" if worker.is_technologist else "Ingeniero",
                total_shifts=worker.get_total_shifts(),
                shift_distribution=worker.get_shift_types_count(),
                days_off_count=len(worker.days_off),
                compensation_total=worker.earnings,
                compensation_breakdown={},  # Se llenaría con análisis detallado
                workload_score=workload_score,
                equity_score=equity_score
            )
            
            individual_stats.append(worker_stat)
        
        return individual_stats
    
    def _calculate_overall_quality_score(self, workload_analysis: Optional[Dict], 
                                       compensation_analysis: Optional[Dict],
                                       days_off_analysis: Optional[DayOffAnalysis],
                                       coverage_analysis: Optional[CoverageAnalysis],
                                       violation_count: int) -> float:
        """Calcula un score general de calidad del horario."""
        scores = []
        
        # Score de balance de carga
        if workload_analysis:
            scores.append(workload_analysis["overall_balance_score"])
        
        # Score de equidad de compensación
        if compensation_analysis:
            scores.append(compensation_analysis["overall_equity_score"])
        
        # Score de cumplimiento de días libres
        if days_off_analysis:
            scores.append(days_off_analysis.compliance_percentage / 100.0)
        
        # Score de cobertura
        if coverage_analysis:
            scores.append(coverage_analysis.coverage_percentage / 100.0)
        
        # Penalización por violaciones
        violation_penalty = min(violation_count * 0.05, 0.5)  # Máximo 50% de penalización
        base_score = sum(scores) / len(scores) if scores else 0.5
        
        final_score = max(0.0, base_score - violation_penalty)
        return final_score
    
    def _generate_recommendations(self, workload_analysis: Optional[Dict],
                                compensation_analysis: Optional[Dict],
                                days_off_analysis: Optional[DayOffAnalysis],
                                coverage_analysis: Optional[CoverageAnalysis],
                                constraint_violations: List[str]) -> List[str]:
        """Genera recomendaciones basadas en el análisis."""
        recommendations = []
        
        # Recomendaciones de balance de carga
        if workload_analysis and workload_analysis["overall_balance_score"] < 0.8:
            recommendations.append("Considerar redistribuir turnos para mejorar el balance de carga de trabajo")
        
        # Recomendaciones de equidad
        if compensation_analysis and compensation_analysis["overall_equity_score"] < 0.8:
            recommendations.append("Revisar la distribución de turnos premium para mejorar la equidad económica")
        
        # Recomendaciones de días libres
        if days_off_analysis and days_off_analysis.compliance_percentage < 90:
            recommendations.append("Revisar la asignación de días libres semanales para mejorar el cumplimiento")
        
        # Recomendaciones de cobertura
        if coverage_analysis and coverage_analysis.coverage_percentage < 95:
            recommendations.append("Verificar y corregir problemas de cobertura de personal en turnos")
        
        # Recomendaciones por violaciones
        if constraint_violations:
            if len(constraint_violations) > 10:
                recommendations.append("Se detectaron múltiples violaciones de restricciones - considerar regenerar el horario")
            else:
                recommendations.append("Corregir manualmente las violaciones de restricciones identificadas")
        
        # Recomendación general si todo está bien
        if not recommendations:
            recommendations.append("El horario cumple con todos los criterios de calidad establecidos")
        
        return recommendations