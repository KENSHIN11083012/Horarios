"""
Configuraciones y constantes para el generador de horarios.
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

# Número de trabajadores por turno
TECHS_PER_SHIFT = {
    "Mañana": 4,
    "Tarde": 4,
    "Noche": 2
}
ENG_PER_SHIFT = 1

# Tasas de compensación en Colombia
NIGHT_SHIFT_RATE = 1.35     # 35% adicional por nocturnidad
HOLIDAY_RATE = 1.75         # 75% adicional por festivos
SUNDAY_RATE = 1.75          # 75% adicional por domingos

# Festivos colombianos 2025 (formato MM-DD)
COLOMBIAN_HOLIDAYS_2025 = [
    "01-01",  # Año Nuevo
    "01-06",  # Reyes Magos
    "03-24",  # San José
    "04-17",  # Jueves Santo
    "04-18",  # Viernes Santo
    "05-01",  # Día del Trabajo
    "05-12",  # Ascensión del Señor
    "06-02",  # Corpus Christi
    "06-23",  # Sagrado Corazón
    "06-30",  # San Pedro y San Pablo
    "07-20",  # Independencia
    "08-07",  # Batalla de Boyacá
    "08-18",  # Asunción
    "10-13",  # Día de la Raza
    "11-03",  # Todos los Santos
    "11-17",  # Independencia de Cartagena
    "12-08",  # Inmaculada Concepción
    "12-25",  # Navidad
]