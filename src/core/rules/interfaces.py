"""
Interfaces y contratos para las reglas de dominio.

Este módulo define las interfaces abstractas que deben implementar
los diferentes tipos de reglas y validadores del dominio.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from ..models import Worker, Schedule, ShiftType


class ConstraintRule(ABC):
    """
    Interfaz base para reglas de restricción.
    
    Las reglas de restricción evalúan si una asignación específica
    viola alguna regla de negocio.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre identificativo de la regla."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Descripción de lo que evalúa la regla."""
        pass
    
    @abstractmethod
    def can_assign(self, worker: Worker, date: datetime, shift_type: ShiftType) -> bool:
        """
        Evalúa si un trabajador puede ser asignado a un turno específico.
        
        Args:
            worker: Trabajador a evaluar
            date: Fecha del turno
            shift_type: Tipo de turno
            
        Returns:
            bool: True si puede ser asignado, False si viola la restricción
        """
        pass
    
    @abstractmethod
    def get_violation_message(self, worker: Worker, date: datetime, shift_type: ShiftType) -> str:
        """
        Obtiene el mensaje de violación cuando la regla no se cumple.
        
        Args:
            worker: Trabajador que viola la regla
            date: Fecha del turno
            shift_type: Tipo de turno
            
        Returns:
            str: Mensaje descriptivo de la violación
        """
        pass


class ScheduleValidator(ABC):
    """
    Interfaz base para validadores de horario completo.
    
    Los validadores analizan un horario completo y reportan
    todas las violaciones encontradas.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre identificativo del validador."""
        pass
    
    @abstractmethod
    def validate(self, schedule: Schedule) -> List[str]:
        """
        Valida un horario completo y retorna las violaciones encontradas.
        
        Args:
            schedule: Horario a validar
            
        Returns:
            List[str]: Lista de mensajes de violación
        """
        pass


class OptimizationRule(ABC):
    """
    Interfaz base para reglas de optimización.
    
    Las reglas de optimización evalúan la calidad de una asignación
    y proporcionan scores para comparar alternativas.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre identificativo de la regla."""
        pass
    
    @property
    @abstractmethod
    def weight(self) -> float:
        """Peso de la regla en la optimización global (0.0 - 1.0)."""
        pass
    
    @abstractmethod
    def calculate_score(self, worker: Worker, date: datetime, shift_type: ShiftType, 
                       schedule: Schedule) -> float:
        """
        Calcula un score de calidad para una asignación específica.
        
        Args:
            worker: Trabajador a evaluar
            date: Fecha del turno
            shift_type: Tipo de turno
            schedule: Horario actual
            
        Returns:
            float: Score de calidad (mayor = mejor)
        """
        pass


class CompensationCalculator(ABC):
    """
    Interfaz para cálculo de compensaciones.
    
    Define cómo calcular la compensación económica
    de un turno según sus características.
    """
    
    @abstractmethod
    def calculate_shift_compensation(self, date: datetime, shift_type: ShiftType) -> float:
        """
        Calcula la compensación para un turno específico.
        
        Args:
            date: Fecha del turno
            shift_type: Tipo de turno
            
        Returns:
            float: Factor de compensación
        """
        pass
    
    @abstractmethod
    def calculate_worker_total_compensation(self, worker: Worker) -> float:
        """
        Calcula la compensación total de un trabajador.
        
        Args:
            worker: Trabajador a evaluar
            
        Returns:
            float: Compensación total acumulada
        """
        pass


class HolidayProvider(ABC):
    """
    Interfaz para proveedores de información de festivos.
    
    Abstrae la fuente de información sobre días festivos.
    """
    
    @abstractmethod
    def is_holiday(self, date: datetime) -> bool:
        """
        Determina si una fecha es festivo.
        
        Args:
            date: Fecha a verificar
            
        Returns:
            bool: True si es festivo
        """
        pass
    
    @abstractmethod
    def get_holidays_in_range(self, start_date: datetime, end_date: datetime) -> List[datetime]:
        """
        Obtiene todos los festivos en un rango de fechas.
        
        Args:
            start_date: Fecha de inicio
            end_date: Fecha de fin
            
        Returns:
            List[datetime]: Lista de fechas festivas
        """
        pass


class ConstraintChecker(ABC):
    """
    Interfaz para verificadores de restricciones múltiples.
    
    Combina múltiples reglas de restricción para evaluación integral.
    """
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    def add_constraint(self, constraint: ConstraintRule):
        """
        Añade una nueva restricción al verificador.
        
        Args:
            constraint: Regla de restricción a añadir
        """
        pass
    
    @abstractmethod
    def remove_constraint(self, constraint_name: str) -> bool:
        """
        Elimina una restricción del verificador.
        
        Args:
            constraint_name: Nombre de la restricción a eliminar
            
        Returns:
            bool: True si se eliminó, False si no existía
        """
        pass


class WorkloadBalancer(ABC):
    """
    Interfaz para balanceadores de carga de trabajo.
    
    Define cómo equilibrar la distribución de turnos entre trabajadores.
    """
    
    @abstractmethod
    def calculate_workload_score(self, worker: Worker, reference_date: datetime) -> float:
        """
        Calcula un score de carga de trabajo para un trabajador.
        
        Args:
            worker: Trabajador a evaluar
            reference_date: Fecha de referencia
            
        Returns:
            float: Score de carga (menor = menos cargado)
        """
        pass
    
    @abstractmethod
    def suggest_rebalancing(self, schedule: Schedule) -> List[Dict[str, Any]]:
        """
        Sugiere intercambios para mejorar el balance de carga.
        
        Args:
            schedule: Horario a analizar
            
        Returns:
            List[Dict]: Lista de sugerencias de intercambio
        """
        pass


class EquityAnalyzer(ABC):
    """
    Interfaz para analizadores de equidad.
    
    Evalúa la equidad en distribución de turnos y compensaciones.
    """
    
    @abstractmethod
    def analyze_shift_equity(self, schedule: Schedule) -> Dict[str, Any]:
        """
        Analiza la equidad en la distribución de turnos.
        
        Args:
            schedule: Horario a analizar
            
        Returns:
            Dict: Análisis de equidad de turnos
        """
        pass
    
    @abstractmethod
    def analyze_compensation_equity(self, schedule: Schedule) -> Dict[str, Any]:
        """
        Analiza la equidad en las compensaciones.
        
        Args:
            schedule: Horario a analizar
            
        Returns:
            Dict: Análisis de equidad de compensaciones
        """
        pass
    
    @abstractmethod
    def calculate_equity_score(self, schedule: Schedule) -> float:
        """
        Calcula un score general de equidad del horario.
        
        Args:
            schedule: Horario a evaluar
            
        Returns:
            float: Score de equidad (0.0 - 1.0, mayor = más equitativo)
        """
        pass