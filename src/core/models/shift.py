"""
Shift model - Dominio puro para representar turnos de trabajo.

Este módulo contiene la lógica de dominio pura para turnos,
incluyendo tipos, horarios y características especiales.
"""

from datetime import datetime, time
from typing import Dict, List, Optional
from enum import Enum
from dataclasses import dataclass


class ShiftType(Enum):
    """Tipos de turno disponibles."""
    MORNING = "Mañana"
    AFTERNOON = "Tarde"
    NIGHT = "Noche"
    
    @classmethod
    def from_string(cls, shift_str: str) -> 'ShiftType':
        """Convierte string a ShiftType."""
        for shift_type in cls:
            if shift_type.value == shift_str:
                return shift_type
        raise ValueError(f"Tipo de turno inválido: {shift_str}")
    
    @classmethod
    def get_all_values(cls) -> List[str]:
        """Retorna todos los valores como strings."""
        return [shift_type.value for shift_type in cls]


@dataclass(frozen=True)
class ShiftTime:
    """Representa el horario de un turno (inmutable)."""
    start_time: time
    end_time: time
    
    def __post_init__(self):
        """Validación post-inicialización."""
        if not isinstance(self.start_time, time) or not isinstance(self.end_time, time):
            raise ValueError("start_time y end_time deben ser objetos time")
    
    @property
    def duration_hours(self) -> float:
        """Calcula la duración del turno en horas."""
        start_minutes = self.start_time.hour * 60 + self.start_time.minute
        end_minutes = self.end_time.hour * 60 + self.end_time.minute
        
        # Manejar turnos que cruzan medianoche
        if end_minutes <= start_minutes:
            end_minutes += 24 * 60  # Añadir 24 horas
        
        return (end_minutes - start_minutes) / 60.0
    
    @property
    def crosses_midnight(self) -> bool:
        """Verifica si el turno cruza medianoche."""
        return self.start_time >= self.end_time
    
    def format_range(self) -> str:
        """Formatea el rango horario como string."""
        return f"{self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')}"
    
    def __str__(self) -> str:
        return self.format_range()


class ShiftCharacteristics:
    """
    Analiza y determina las características especiales de un turno.
    
    Esta clase encapsula la lógica para determinar si un turno es premium,
    nocturno, de fin de semana, etc.
    """
    
    @staticmethod
    def is_night_shift(shift_type: ShiftType) -> bool:
        """Determina si es turno nocturno."""
        return shift_type == ShiftType.NIGHT
    
    @staticmethod
    def is_weekend_date(date: datetime) -> bool:
        """Determina si la fecha es fin de semana."""
        return date.weekday() >= 5  # 5=Sábado, 6=Domingo
    
    @staticmethod
    def is_holiday_date(date: datetime) -> bool:
        """
        Determina si la fecha es festivo colombiano.
        
        Note: Esta función necesitará acceso a la configuración de festivos.
        Por ahora es un placeholder que será implementado en la capa de infraestructura.
        """
        # TODO: Implementar verificación de festivos colombianos
        # Esta lógica será movida a un servicio de la infraestructura
        return False
    
    @staticmethod
    def is_premium_shift(date: datetime, shift_type: ShiftType) -> bool:
        """
        Determina si un turno es premium (fin de semana, nocturno o festivo).
        
        Args:
            date: Fecha del turno
            shift_type: Tipo de turno
            
        Returns:
            bool: True si es turno premium
        """
        return (ShiftCharacteristics.is_weekend_date(date) or 
                ShiftCharacteristics.is_night_shift(shift_type) or 
                ShiftCharacteristics.is_holiday_date(date))
    
    @staticmethod
    def get_shift_priority(shift_type: ShiftType) -> int:
        """
        Retorna la prioridad de un tipo de turno (mayor número = mayor prioridad).
        
        Args:
            shift_type: Tipo de turno
            
        Returns:
            int: Prioridad del turno (1-3)
        """
        priority_map = {
            ShiftType.MORNING: 1,
            ShiftType.AFTERNOON: 2,
            ShiftType.NIGHT: 3
        }
        return priority_map.get(shift_type, 0)


@dataclass
class ShiftRequirement:
    """Define los requisitos de personal para un turno."""
    technologists_needed: int
    engineers_needed: int
    
    def __post_init__(self):
        """Validación post-inicialización."""
        if self.technologists_needed < 0 or self.engineers_needed < 0:
            raise ValueError("Los requisitos no pueden ser negativos")
    
    @property
    def total_workers_needed(self) -> int:
        """Retorna el total de trabajadores necesarios."""
        return self.technologists_needed + self.engineers_needed
    
    def is_satisfied_by(self, techs_assigned: int, engs_assigned: int) -> bool:
        """Verifica si los requisitos están satisfechos."""
        return (techs_assigned >= self.technologists_needed and 
                engs_assigned >= self.engineers_needed)


class ShiftDefinition:
    """
    Define completamente un tipo de turno con todos sus atributos.
    
    Esta clase combina tipo, horario y requisitos de personal.
    """
    
    def __init__(self, 
                 shift_type: ShiftType, 
                 shift_time: ShiftTime, 
                 requirement: ShiftRequirement):
        """
        Inicializa una definición de turno.
        
        Args:
            shift_type: Tipo de turno
            shift_time: Horario del turno
            requirement: Requisitos de personal
        """
        self.shift_type = shift_type
        self.shift_time = shift_time
        self.requirement = requirement
    
    @property
    def name(self) -> str:
        """Retorna el nombre del turno."""
        return self.shift_type.value
    
    @property
    def is_night_shift(self) -> bool:
        """Verifica si es turno nocturno."""
        return ShiftCharacteristics.is_night_shift(self.shift_type)
    
    def get_priority(self) -> int:
        """Retorna la prioridad del turno."""
        return ShiftCharacteristics.get_shift_priority(self.shift_type)
    
    def is_premium_on_date(self, date: datetime) -> bool:
        """Verifica si es turno premium en una fecha específica."""
        return ShiftCharacteristics.is_premium_shift(date, self.shift_type)
    
    def __str__(self) -> str:
        """Representación string de la definición."""
        return f"{self.name} ({self.shift_time}) - {self.requirement.total_workers_needed} workers"
    
    def __repr__(self) -> str:
        """Representación detallada de la definición."""
        return (f"ShiftDefinition(type={self.shift_type}, time={self.shift_time}, "
               f"req={self.requirement.technologists_needed}T+{self.requirement.engineers_needed}E)")


class ShiftRegistry:
    """
    Registro central de definiciones de turnos.
    
    Esta clase mantiene todas las definiciones de turnos disponibles
    y proporciona métodos para acceder a ellas.
    """
    
    def __init__(self):
        """Inicializa el registro con definiciones por defecto."""
        self._definitions: Dict[ShiftType, ShiftDefinition] = {}
        self._initialize_default_definitions()
    
    def _initialize_default_definitions(self):
        """Inicializa las definiciones por defecto de turnos."""
        # Definiciones estándar (pueden ser sobrescritas por configuración)
        definitions = {
            ShiftType.MORNING: ShiftDefinition(
                shift_type=ShiftType.MORNING,
                shift_time=ShiftTime(time(6, 0), time(14, 0)),
                requirement=ShiftRequirement(technologists_needed=5, engineers_needed=1)
            ),
            ShiftType.AFTERNOON: ShiftDefinition(
                shift_type=ShiftType.AFTERNOON,
                shift_time=ShiftTime(time(14, 0), time(22, 0)),
                requirement=ShiftRequirement(technologists_needed=5, engineers_needed=1)
            ),
            ShiftType.NIGHT: ShiftDefinition(
                shift_type=ShiftType.NIGHT,
                shift_time=ShiftTime(time(22, 0), time(6, 0)),
                requirement=ShiftRequirement(technologists_needed=2, engineers_needed=1)
            )
        }
        
        self._definitions.update(definitions)
    
    def register_shift(self, definition: ShiftDefinition):
        """
        Registra una nueva definición de turno.
        
        Args:
            definition: Definición del turno a registrar
        """
        self._definitions[definition.shift_type] = definition
    
    def get_definition(self, shift_type: ShiftType) -> Optional[ShiftDefinition]:
        """
        Obtiene la definición de un tipo de turno.
        
        Args:
            shift_type: Tipo de turno
            
        Returns:
            ShiftDefinition o None: Definición si existe, None en caso contrario
        """
        return self._definitions.get(shift_type)
    
    def get_definition_by_name(self, shift_name: str) -> Optional[ShiftDefinition]:
        """
        Obtiene la definición de un turno por nombre.
        
        Args:
            shift_name: Nombre del turno
            
        Returns:
            ShiftDefinition o None: Definición si existe, None en caso contrario
        """
        try:
            shift_type = ShiftType.from_string(shift_name)
            return self.get_definition(shift_type)
        except ValueError:
            return None
    
    def get_all_definitions(self) -> List[ShiftDefinition]:
        """Retorna todas las definiciones registradas."""
        return list(self._definitions.values())
    
    def get_all_shift_types(self) -> List[ShiftType]:
        """Retorna todos los tipos de turno registrados."""
        return list(self._definitions.keys())
    
    def get_all_shift_names(self) -> List[str]:
        """Retorna todos los nombres de turno como strings."""
        return [definition.name for definition in self._definitions.values()]
    
    def get_requirement_for_shift(self, shift_type: ShiftType) -> Optional[ShiftRequirement]:
        """
        Obtiene los requisitos de personal para un tipo de turno.
        
        Args:
            shift_type: Tipo de turno
            
        Returns:
            ShiftRequirement o None: Requisitos si existen, None en caso contrario
        """
        definition = self.get_definition(shift_type)
        return definition.requirement if definition else None
    
    def get_time_for_shift(self, shift_type: ShiftType) -> Optional[ShiftTime]:
        """
        Obtiene el horario para un tipo de turno.
        
        Args:
            shift_type: Tipo de turno
            
        Returns:
            ShiftTime o None: Horario si existe, None en caso contrario
        """
        definition = self.get_definition(shift_type)
        return definition.shift_time if definition else None
    
    def __contains__(self, shift_type: ShiftType) -> bool:
        """Verifica si un tipo de turno está registrado."""
        return shift_type in self._definitions
    
    def __len__(self) -> int:
        """Retorna el número de tipos de turno registrados."""
        return len(self._definitions)


# Instancia global del registro de turnos
shift_registry = ShiftRegistry()