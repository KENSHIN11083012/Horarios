# core/interfaces/constraint_interface.py
"""
Interfaz base para todas las restricciones del sistema.
Define el contrato que deben cumplir todas las restricciones.
"""

from abc import ABC, abstractmethod
from typing import List, Tuple, Optional
from datetime import datetime


class ConstraintInterface(ABC):
    """
    Interfaz base para todas las restricciones del sistema de horarios.
    
    Cada restricción debe poder:
    - Verificar si se cumple para una asignación específica
    - Evaluar el impacto de una posible asignación
    - Proporcionar información sobre la restricción
    - Determinar su nivel de severidad
    """
    
    class Severity:
        """Niveles de severidad para las restricciones"""
        HARD = "HARD"          # No puede violarse bajo ninguna circunstancia
        SOFT = "SOFT"          # Puede violarse pero con penalización
        PREFERENCE = "PREF"    # Preferencia, menor prioridad
    
    def __init__(self, name: str, severity: str = Severity.HARD):
        """
        Inicializa la restricción.
        
        Args:
            name: Nombre descriptivo de la restricción
            severity: Nivel de severidad (HARD, SOFT, PREFERENCE)
        """
        self.name = name
        self.severity = severity
        self.enabled = True
    
    @abstractmethod
    def check(self, worker, date: datetime, shift_type: str, schedule) -> bool:
        """
        Verifica si la restricción se cumple para una asignación específica.
        
        Args:
            worker: Trabajador a evaluar
            date: Fecha del turno
            shift_type: Tipo de turno ('Mañana', 'Tarde', 'Noche')
            schedule: Horario actual
            
        Returns:
            bool: True si la restricción se cumple, False si se viola
        """
        pass
    
    @abstractmethod
    def evaluate_impact(self, worker, date: datetime, shift_type: str, schedule) -> float:
        """
        Evalúa el impacto de asignar este turno al trabajador.
        Útil para decisiones proactivas.
        
        Args:
            worker: Trabajador a evaluar
            date: Fecha del turno
            shift_type: Tipo de turno
            schedule: Horario actual
            
        Returns:
            float: Puntuación de impacto (0 = sin impacto, mayor = peor)
        """
        pass
    
    @abstractmethod
    def get_violations(self, schedule) -> List[str]:
        """
        Obtiene todas las violaciones de esta restricción en el horario.
        
        Args:
            schedule: Horario a validar
            
        Returns:
            List[str]: Lista de mensajes describiendo las violaciones
        """
        pass
    
    def get_description(self) -> str:
        """
        Obtiene una descripción legible de la restricción.
        
        Returns:
            str: Descripción de la restricción
        """
        return f"{self.name} (Severidad: {self.severity})"
    
    def is_hard_constraint(self) -> bool:
        """
        Indica si es una restricción dura (no puede violarse).
        
        Returns:
            bool: True si es restricción dura
        """
        return self.severity == self.Severity.HARD
    
    def is_enabled(self) -> bool:
        """
        Indica si la restricción está activa.
        
        Returns:
            bool: True si está activa
        """
        return self.enabled
    
    def enable(self):
        """Activa la restricción"""
        self.enabled = True
    
    def disable(self):
        """Desactiva la restricción"""
        self.enabled = False
    
    def get_penalty_weight(self) -> float:
        """
        Obtiene el peso de penalización para restricciones blandas.
        
        Returns:
            float: Peso de penalización
        """
        weights = {
            self.Severity.HARD: float('inf'),
            self.Severity.SOFT: 10.0,
            self.Severity.PREFERENCE: 1.0
        }
        return weights.get(self.severity, 1.0)