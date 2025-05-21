"""
Configuraciones para el generador de horarios.
"""

# Tipos de turnos
SHIFT_TYPES = ["Mañana", "Tarde", "Noche"]

# Horarios de los turnos
SHIFT_HOURS = {
    "Mañana": "06:00-14:00",
    "Tarde": "14:00-22:00",
    "Noche": "22:00-06:00"
}

# Configuración de personal
NUM_TECHNOLOGISTS = 13
NUM_ENGINEERS = 4

# Número de trabajadores por turno - CORREGIDO
TECHS_PER_SHIFT = {
    "Mañana": 5,  
    "Tarde": 5,    
    "Noche": 2
}
ENG_PER_SHIFT = 1

# Tasas de compensación (formato antiguo para compatibilidad)
NIGHT_SHIFT_RATE = 1.5
HOLIDAY_RATE = 2.0
SUNDAY_RATE = 2.0

# Tasas de compensación (nuevas reglas)
COMPENSATION_RATES = {
    "DIURNO": 1.0,                # Turno diurno regular (Mañana, Tarde)
    "NOCTURNO": 1.5,              # Turno nocturno regular
    "FIN_DE_SEMANA_DIURNO": 2.0,  # Turno diurno en fin de semana
    "FIN_DE_SEMANA_NOCTURNO": 2.5 # Turno nocturno en fin de semana
}

COLOMBIAN_HOLIDAYS_2025 = [
    "01-01",  # Año Nuevo
    "01-06",  # Día de los Reyes Magos
    "03-24",  # Día de San José (trasladado)
    "04-17",  # Jueves Santo
    "04-18",  # Viernes Santo
    "05-01",  # Día del Trabajo
    "06-02",  # Día de la Ascensión (trasladado)
    "06-23",  # Corpus Christi (trasladado)
    "06-30",  # Sagrado Corazón (trasladado)
    "07-07",  # San Pedro y San Pablo (trasladado)
    "07-20",  # Día de la Independencia
    "08-07",  # Batalla de Boyacá
    "08-18",  # Asunción de la Virgen (trasladado)
    "10-13",  # Día de la Raza (trasladado)
    "11-03",  # Día de Todos los Santos (trasladado)
    "11-17",  # Independencia de Cartagena (trasladado)
    "12-08",  # Día de la Inmaculada Concepción
    "12-25",  # Navidad
]
