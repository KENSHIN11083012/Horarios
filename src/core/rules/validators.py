"""
Validadores de horario completo.

Este módulo contiene validadores que analizan horarios completos
y reportan violaciones de reglas de negocio.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Set, Tuple
from ..models import Schedule, Worker, ShiftType
from .interfaces import ScheduleValidator, ConstraintChecker
from .constraints import DEFAULT_CONSTRAINTS, ConstraintRule


class CoverageValidator(ScheduleValidator):
    """
    Validador de cobertura de personal.
    
    Verifica que todos los turnos tengan la cantidad correcta
    de tecnólogos e ingenieros asignados.
    """
    
    @property
    def name(self) -> str:
        return "coverage_validator"
    
    def validate(self, schedule: Schedule) -> List[str]:
        """
        Valida la cobertura de personal en todos los turnos.
        
        Args:
            schedule: Horario a validar
            
        Returns:
            List[str]: Lista de violaciones de cobertura encontradas
        """
        violations = []
        
        for day_schedule in schedule.days:
            date_str = day_schedule.date.strftime("%Y-%m-%d")
            
            for shift_type_str, assignment in day_schedule.shifts.items():
                try:
                    shift_type = ShiftType.from_string(shift_type_str)
                except ValueError:
                    violations.append(f"Tipo de turno inválido: {shift_type_str} en {date_str}")
                    continue
                
                # Obtener requisitos de personal
                from ...infrastructure.config.settings import TECHS_PER_SHIFT, ENG_PER_SHIFT
                
                required_techs = TECHS_PER_SHIFT.get(shift_type_str, 0)
                actual_techs = len(assignment.technologist_ids)
                
                required_engs = ENG_PER_SHIFT
                actual_engs = 1 if assignment.engineer_id is not None else 0
                
                # Verificar cobertura de tecnólogos
                if actual_techs != required_techs:
                    violations.append(
                        f"Error en {date_str} {shift_type_str}: {actual_techs} tecnólogos "
                        f"cuando deberían ser {required_techs}"
                    )
                
                # Verificar cobertura de ingenieros
                if actual_engs != required_engs:
                    if actual_engs == 0:
                        violations.append(f"Error en {date_str} {shift_type_str}: Falta ingeniero asignado")
                    else:
                        violations.append(
                            f"Error en {date_str} {shift_type_str}: {actual_engs} ingenieros "
                            f"cuando deberían ser {required_engs}"
                        )
        
        return violations


class ConstraintValidator(ScheduleValidator):
    """
    Validador de restricciones de trabajadores.
    
    Verifica que ningún trabajador viole las restricciones
    de asignación de turnos.
    """
    
    def __init__(self, constraint_checker: ConstraintChecker):
        """
        Inicializa el validador con un verificador de restricciones.
        
        Args:
            constraint_checker: Verificador de restricciones a usar
        """
        self.constraint_checker = constraint_checker
    
    @property
    def name(self) -> str:
        return "constraint_validator"
    
    def validate(self, schedule: Schedule) -> List[str]:
        """
        Valida que todos los trabajadores cumplan las restricciones.
        
        Args:
            schedule: Horario a validar
            
        Returns:
            List[str]: Lista de violaciones de restricciones encontradas
        """
        violations = []
        
        for worker in schedule.get_all_workers():
            # Verificar cada asignación del trabajador
            for shift_date, shift_type_str in worker.shifts:
                try:
                    shift_type = ShiftType.from_string(shift_type_str)
                except ValueError:
                    violations.append(f"Tipo de turno inválido para {worker.get_formatted_id()}: {shift_type_str}")
                    continue
                
                # Crear una versión temporal del trabajador sin esta asignación
                # para simular la verificación de restricciones
                temp_worker = self._create_temp_worker_without_shift(worker, shift_date, shift_type_str)
                
                # Verificar si esta asignación viola restricciones
                can_assign, constraint_violations = self.constraint_checker.check_all_constraints(
                    temp_worker, shift_date, shift_type, schedule
                )
                
                if not can_assign:
                    for violation in constraint_violations:
                        violations.append(f"{worker.get_formatted_id()}: {violation}")
        
        return violations
    
    def _create_temp_worker_without_shift(self, worker: Worker, exclude_date: datetime, 
                                        exclude_shift: str) -> Worker:
        """
        Crea una copia temporal del trabajador sin una asignación específica.
        
        Args:
            worker: Trabajador original
            exclude_date: Fecha a excluir
            exclude_shift: Tipo de turno a excluir
            
        Returns:
            Worker: Copia temporal del trabajador
        """
        from ..models import Worker, WorkerType
        
        # Crear copia del trabajador
        temp_worker = Worker(worker.id, worker.worker_type)
        temp_worker.days_off = worker.days_off.copy()
        temp_worker.earnings = worker.earnings
        
        # Copiar todas las asignaciones excepto la excluida
        temp_worker.shifts = [
            (date, shift) for date, shift in worker.shifts
            if not (date == exclude_date and shift == exclude_shift)
        ]
        
        return temp_worker


class DataIntegrityValidator(ScheduleValidator):
    """
    Validador de integridad de datos.
    
    Verifica la consistencia interna de la estructura de datos
    del horario.
    """
    
    @property
    def name(self) -> str:
        return "data_integrity_validator"
    
    def validate(self, schedule: Schedule) -> List[str]:
        """
        Valida la integridad de los datos del horario.
        
        Args:
            schedule: Horario a validar
            
        Returns:
            List[str]: Lista de violaciones de integridad encontradas
        """
        violations = []
        
        # Usar el método integrado del Schedule
        integrity_errors = schedule.verify_data_integrity()
        violations.extend(integrity_errors)
        
        # Verificaciones adicionales específicas del validador
        violations.extend(self._check_duplicate_assignments(schedule))
        violations.extend(self._check_orphaned_assignments(schedule))
        violations.extend(self._check_date_ranges(schedule))
        
        return violations
    
    def _check_duplicate_assignments(self, schedule: Schedule) -> List[str]:
        """Verifica asignaciones duplicadas en el mismo turno."""
        violations = []
        
        for day_schedule in schedule.days:
            date_str = day_schedule.date.strftime("%Y-%m-%d")
            
            for shift_type, assignment in day_schedule.shifts.items():
                # Verificar tecnólogos duplicados
                tech_ids = assignment.technologist_ids
                if len(tech_ids) != len(set(tech_ids)):
                    duplicates = [tid for tid in tech_ids if tech_ids.count(tid) > 1]
                    violations.append(
                        f"Tecnólogos duplicados en {date_str} {shift_type}: {duplicates}"
                    )
        
        return violations
    
    def _check_orphaned_assignments(self, schedule: Schedule) -> List[str]:
        """Verifica asignaciones que referencian trabajadores inexistentes."""
        violations = []
        
        # Crear sets de IDs válidos
        valid_tech_ids = {w.id for w in schedule.get_technologists()}
        valid_eng_ids = {w.id for w in schedule.get_engineers()}
        
        for day_schedule in schedule.days:
            date_str = day_schedule.date.strftime("%Y-%m-%d")
            
            for shift_type, assignment in day_schedule.shifts.items():
                # Verificar tecnólogos
                for tech_id in assignment.technologist_ids:
                    if tech_id not in valid_tech_ids:
                        violations.append(
                            f"Tecnólogo inexistente {tech_id} en {date_str} {shift_type}"
                        )
                
                # Verificar ingeniero
                if assignment.engineer_id is not None:
                    if assignment.engineer_id not in valid_eng_ids:
                        violations.append(
                            f"Ingeniero inexistente {assignment.engineer_id} en {date_str} {shift_type}"
                        )
        
        return violations
    
    def _check_date_ranges(self, schedule: Schedule) -> List[str]:
        """Verifica que todas las fechas estén dentro del rango del horario."""
        violations = []
        
        for worker in schedule.get_all_workers():
            for shift_date, shift_type in worker.shifts:
                if not schedule.is_date_in_range(shift_date):
                    violations.append(
                        f"{worker.get_formatted_id()} tiene turno fuera del rango: "
                        f"{shift_date.strftime('%Y-%m-%d')} {shift_type}"
                    )
            
            for day_off in worker.days_off:
                if not schedule.is_date_in_range(day_off):
                    violations.append(
                        f"{worker.get_formatted_id()} tiene día libre fuera del rango: "
                        f"{day_off.strftime('%Y-%m-%d')}"
                    )
        
        return violations


class WeeklyDayOffValidator(ScheduleValidator):
    """
    Validador de días libres semanales.
    
    Verifica que cada trabajador tenga al menos un día libre
    por semana durante todo el período.
    """
    
    @property
    def name(self) -> str:
        return "weekly_day_off_validator"
    
    def validate(self, schedule: Schedule) -> List[str]:
        """
        Valida que todos los trabajadores tengan días libres semanales.
        
        Args:
            schedule: Horario a validar
            
        Returns:
            List[str]: Lista de violaciones de días libres encontradas
        """
        violations = []
        
        # Obtener todas las semanas del período
        weeks = self._get_weeks_in_period(schedule)
        
        for worker in schedule.get_all_workers():
            for week_start, week_end, effective_start, effective_end in weeks:
                # Obtener días libres en esta semana
                days_off_in_week = worker.get_days_off_in_date_range(effective_start, effective_end)
                
                # Verificar si hay al menos un día libre
                if not days_off_in_week:
                    # Verificar si la semana tiene al menos 3 días efectivos
                    effective_days = (effective_end - effective_start).days + 1
                    
                    if effective_days >= 3:  # Solo reportar para semanas significativas
                        violations.append(
                            f"{worker.get_formatted_id()} no tiene día libre en semana "
                            f"{effective_start.strftime('%d/%m')} - {effective_end.strftime('%d/%m')}"
                        )
        
        return violations
    
    def _get_weeks_in_period(self, schedule: Schedule) -> List[Tuple[datetime, datetime, datetime, datetime]]:
        """
        Obtiene todas las semanas que intersectan con el período del horario.
        
        Returns:
            List[Tuple]: Lista de tuplas (week_start, week_end, effective_start, effective_end)
        """
        from ...shared.utils import get_week_start, get_week_end
        
        weeks = []
        current_week_start = get_week_start(schedule.start_date)
        end_date_week_start = get_week_start(schedule.end_date)
        
        while current_week_start <= end_date_week_start:
            week_end = get_week_end(current_week_start)
            
            # Solo incluir semanas que se superpongan con el período
            if not (week_end < schedule.start_date or current_week_start > schedule.end_date):
                effective_start = max(current_week_start, schedule.start_date)
                effective_end = min(week_end, schedule.end_date)
                weeks.append((current_week_start, week_end, effective_start, effective_end))
            
            current_week_start += timedelta(days=7)
        
        return weeks


class BasicConstraintChecker(ConstraintChecker):
    """
    Implementación básica de verificador de restricciones.
    
    Combina múltiples reglas de restricción para evaluación integral.
    """
    
    def __init__(self, constraints: List[ConstraintRule] = None):
        """
        Inicializa el verificador con una lista de restricciones.
        
        Args:
            constraints: Lista de restricciones a aplicar. Si es None, usa las por defecto.
        """
        self.constraints: Dict[str, ConstraintRule] = {}
        
        # Usar restricciones por defecto si no se proporcionan
        if constraints is None:
            constraints = DEFAULT_CONSTRAINTS
        
        for constraint in constraints:
            self.add_constraint(constraint)
    
    def check_all_constraints(self, worker: Worker, date: datetime, 
                            shift_type: ShiftType, schedule: Schedule) -> Tuple[bool, List[str]]:
        """
        Verifica todas las restricciones aplicables.
        
        Args:
            worker: Trabajador a evaluar
            date: Fecha del turno
            shift_type: Tipo de turno
            schedule: Horario actual
            
        Returns:
            Tuple[bool, List[str]]: (puede_asignar, lista_violaciones)
        """
        violations = []
        can_assign = True
        
        for constraint in self.constraints.values():
            if not constraint.can_assign(worker, date, shift_type):
                can_assign = False
                violation_msg = constraint.get_violation_message(worker, date, shift_type)
                violations.append(violation_msg)
        
        return can_assign, violations
    
    def add_constraint(self, constraint: ConstraintRule):
        """
        Añade una nueva restricción al verificador.
        
        Args:
            constraint: Regla de restricción a añadir
        """
        self.constraints[constraint.name] = constraint
    
    def remove_constraint(self, constraint_name: str) -> bool:
        """
        Elimina una restricción del verificador.
        
        Args:
            constraint_name: Nombre de la restricción a eliminar
            
        Returns:
            bool: True si se eliminó, False si no existía
        """
        if constraint_name in self.constraints:
            del self.constraints[constraint_name]
            return True
        return False
    
    def get_constraint(self, constraint_name: str) -> ConstraintRule:
        """
        Obtiene una restricción por nombre.
        
        Args:
            constraint_name: Nombre de la restricción
            
        Returns:
            ConstraintRule: Restricción encontrada
            
        Raises:
            KeyError: Si la restricción no existe
        """
        return self.constraints[constraint_name]
    
    def list_constraints(self) -> List[str]:
        """Retorna la lista de nombres de restricciones activas."""
        return list(self.constraints.keys())


class CompositeValidator(ScheduleValidator):
    """
    Validador compuesto que combina múltiples validadores.
    
    Permite ejecutar varios validadores de forma coordinada
    y consolidar todos los resultados.
    """
    
    def __init__(self, validators: List[ScheduleValidator] = None):
        """
        Inicializa el validador compuesto.
        
        Args:
            validators: Lista de validadores a incluir. Si es None, usa los estándar.
        """
        self.validators: Dict[str, ScheduleValidator] = {}
        
        # Usar validadores estándar si no se proporcionan
        if validators is None:
            validators = self._create_default_validators()
        
        for validator in validators:
            self.add_validator(validator)
    
    def _create_default_validators(self) -> List[ScheduleValidator]:
        """Crea la lista de validadores por defecto."""
        constraint_checker = BasicConstraintChecker()
        
        return [
            CoverageValidator(),
            ConstraintValidator(constraint_checker),
            DataIntegrityValidator(),
            WeeklyDayOffValidator(),
        ]
    
    @property
    def name(self) -> str:
        return "composite_validator"
    
    def validate(self, schedule: Schedule) -> List[str]:
        """
        Ejecuta todos los validadores y consolida los resultados.
        
        Args:
            schedule: Horario a validar
            
        Returns:
            List[str]: Lista consolidada de todas las violaciones encontradas
        """
        all_violations = []
        
        for validator_name, validator in self.validators.items():
            violations = validator.validate(schedule)
            
            # Agregar prefijo del validador para identificar la fuente
            prefixed_violations = [
                f"[{validator_name}] {violation}" for violation in violations
            ]
            all_violations.extend(prefixed_violations)
        
        return all_violations
    
    def add_validator(self, validator: ScheduleValidator):
        """
        Añade un validador al compuesto.
        
        Args:
            validator: Validador a añadir
        """
        self.validators[validator.name] = validator
    
    def remove_validator(self, validator_name: str) -> bool:
        """
        Elimina un validador del compuesto.
        
        Args:
            validator_name: Nombre del validador a eliminar
            
        Returns:
            bool: True si se eliminó, False si no existía
        """
        if validator_name in self.validators:
            del self.validators[validator_name]
            return True
        return False
    
    def get_validator(self, validator_name: str) -> ScheduleValidator:
        """
        Obtiene un validador por nombre.
        
        Args:
            validator_name: Nombre del validador
            
        Returns:
            ScheduleValidator: Validador encontrado
            
        Raises:
            KeyError: Si el validador no existe
        """
        return self.validators[validator_name]
    
    def list_validators(self) -> List[str]:
        """Retorna la lista de nombres de validadores activos."""
        return list(self.validators.keys())


# Instancia global del validador compuesto estándar
default_validator = CompositeValidator()