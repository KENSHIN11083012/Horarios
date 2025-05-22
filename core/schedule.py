"""
Clase para la gestión del horario completo.

Este módulo contiene la clase Schedule que representa un horario
completo para un período específico, incluyendo la asignación de
trabajadores a turnos y métodos para manipular y consultar estas asignaciones.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Union, Tuple, Set
from config.settings import SHIFT_TYPES, SHIFT_HOURS


class Schedule:
    """
    Representa un horario completo para un período específico.
    
    Esta clase maneja la estructura de datos principal para el horario,
    incluyendo todos los días del período, los turnos disponibles y
    las asignaciones de trabajadores a cada turno.
    
    Attributes:
        start_date (datetime): Fecha de inicio del período del horario
        end_date (datetime): Fecha de fin del período del horario
        workers (list): Lista de todos los trabajadores disponibles
        days (list): Lista de días con sus turnos y asignaciones
    """
    
    def __init__(self, start_date: datetime, end_date: datetime, workers: List):
        """
        Inicializa un nuevo horario para el período especificado.
        
        Args:
            start_date: Fecha de inicio del período
            end_date: Fecha de fin del período
            workers: Lista de objetos Worker (tecnólogos e ingenieros)
        
        Raises:
            ValueError: Si las fechas son inválidas o si workers está vacío
        """
        # Validación de fechas
        if start_date > end_date:
            raise ValueError("La fecha de inicio debe ser anterior o igual a la fecha de fin")
        
        # Validación de trabajadores
        if not workers:
            raise ValueError("Debe proporcionar al menos un trabajador")
        
        self.start_date = start_date
        self.end_date = end_date
        self.workers = workers
        self.days = []
        
        # Creación de caché de días para acceso rápido
        self._day_cache = {}
        
        # Inicializar estructura de datos para todos los días
        from utils.date_utils import date_range
        for current_date in date_range(start_date, end_date):
            day_data = {
                "date": current_date,
                "shifts": {
                    shift_type: {
                        "hours": SHIFT_HOURS[shift_type],
                        "technologists": [],
                        "engineer": None
                    } for shift_type in SHIFT_TYPES
                }
            }
            self.days.append(day_data)
            # Guardar referencia en caché
            self._day_cache[current_date] = day_data
    
    def assign_worker(self, worker, date: datetime, shift_type: str) -> bool:
        """
        Asigna un trabajador a un turno específico con validación de duplicados.
        
        Args:
            worker: Objeto Worker a asignar
            date: Fecha del turno
            shift_type: Tipo de turno ('Mañana', 'Tarde', 'Noche')
            
        Returns:
            bool: True si la asignación fue exitosa, False en caso contrario
            
        Raises:
            ValueError: Si el tipo de turno no es válido
        """
        # Validar tipo de turno
        if shift_type not in SHIFT_TYPES:
            raise ValueError(f"Tipo de turno inválido: {shift_type}. Debe ser uno de {SHIFT_TYPES}")
        
        # Usar caché para acceso rápido
        day_data = self._day_cache.get(date)
        
        if not day_data:
            return False  # Fecha fuera del rango del horario
        
        # Obtener los datos del turno
        shift_data = day_data["shifts"][shift_type]
        
        if worker.is_technologist:
            # Verificar duplicados
            if worker.id in shift_data["technologists"]:
                print(f"⚠️ Evitando duplicación: {worker.get_formatted_id()} en {date.strftime('%d/%m/%Y')} {shift_type}")
                return False
                
            # Añadir tecnólogo al turno
            shift_data["technologists"].append(worker.id)
        else:
            # Verificar si ya hay ingeniero asignado
            if shift_data["engineer"] is not None and shift_data["engineer"] != worker.id:
                print(f"⚠️ Reemplazando ingeniero en {date.strftime('%d/%m/%Y')} {shift_type}")
                
            # Asignar ingeniero al turno
            shift_data["engineer"] = worker.id
            
        # Registrar turno en el trabajador
        worker.add_shift(date, shift_type)
        return True
    
    def remove_worker_from_shift(self, worker, date: datetime, shift_type: str) -> bool:
        """
        Elimina a un trabajador de un turno específico.
        
        Args:
            worker: Objeto Worker a remover
            date: Fecha del turno
            shift_type: Tipo de turno ('Mañana', 'Tarde', 'Noche')
            
        Returns:
            bool: True si la eliminación fue exitosa, False en caso contrario
        """
        day_data = self._day_cache.get(date)
        
        if not day_data:
            return False
            
        shift_data = day_data["shifts"][shift_type]
        removed = False
        
        if worker.is_technologist:
            if worker.id in shift_data["technologists"]:
                shift_data["technologists"].remove(worker.id)
                removed = True
        else:
            if shift_data["engineer"] == worker.id:
                shift_data["engineer"] = None
                removed = True
                
        # Si se eliminó del horario, actualizar también el registro del trabajador
        if removed:
            worker.shifts = [(d, s) for d, s in worker.shifts if not (d == date and s == shift_type)]
            
        return removed
    
    def get_all_workers(self) -> List:
        """
        Retorna todos los trabajadores disponibles para este horario.
        
        Returns:
            List: Lista de todos los objetos Worker
        """
        return self.workers
    
    def get_technologists(self) -> List:
        """
        Retorna solo los tecnólogos disponibles.
        
        Returns:
            List: Lista de objetos Worker que son tecnólogos
        """
        return [w for w in self.workers if w.is_technologist]
    
    def get_engineers(self) -> List:
        """
        Retorna solo los ingenieros disponibles.
        
        Returns:
            List: Lista de objetos Worker que son ingenieros
        """
        return [w for w in self.workers if not w.is_technologist]
    
    def get_day(self, date: datetime) -> Optional[Dict]:
        """
        Retorna la información de un día específico.
        
        Args:
            date: Fecha a buscar
            
        Returns:
            Dict o None: Datos del día si existe, None en caso contrario
        """
        return self._day_cache.get(date)
    
    def get_shift(self, date: datetime, shift_type: str) -> Optional[Dict]:
        """
        Retorna la información de un turno específico.
        
        Args:
            date: Fecha del turno
            shift_type: Tipo de turno
            
        Returns:
            Dict o None: Datos del turno si existe, None en caso contrario
        """
        day_data = self._day_cache.get(date)
        if day_data and shift_type in day_data["shifts"]:
            return day_data["shifts"][shift_type]
        return None
    
    def get_worker_shifts(self, worker) -> List[Tuple[datetime, str]]:
        """
        Retorna todos los turnos asignados a un trabajador.
        
        Args:
            worker: Objeto Worker
            
        Returns:
            List: Lista de tuplas (fecha, tipo_turno)
        """
        return worker.shifts.copy()  # Retorna una copia para evitar modificaciones externas
    
    def get_workers_in_shift(self, date: datetime, shift_type: str) -> Tuple[List, Optional[int]]:
        """
        Retorna los trabajadores asignados a un turno específico.
        
        Args:
            date: Fecha del turno
            shift_type: Tipo de turno
            
        Returns:
            Tuple: (Lista de tecnólogos, ID del ingeniero o None)
        """
        shift_data = self.get_shift(date, shift_type)
        if not shift_data:
            return [], None
            
        tech_ids = shift_data["technologists"]
        eng_id = shift_data["engineer"]
        
        technologists = [t for t in self.get_technologists() if t.id in tech_ids]
        engineer = next((e for e in self.get_engineers() if e.id == eng_id), None)
        
        return technologists, engineer
    
    def get_shift_coverage(self, date: datetime, shift_type: str) -> Dict:
        """
        Evalúa la cobertura de un turno respecto a los requisitos.
        
        Args:
            date: Fecha del turno
            shift_type: Tipo de turno
            
        Returns:
            Dict: Información de cobertura con claves 'complete', 'technologists', 'engineer'
        """
        from config.settings import TECHS_PER_SHIFT, ENG_PER_SHIFT
        
        shift_data = self.get_shift(date, shift_type)
        if not shift_data:
            return {
                "complete": False,
                "technologists": {"required": 0, "assigned": 0},
                "engineer": {"required": 0, "assigned": 0}
            }
            
        techs_required = TECHS_PER_SHIFT[shift_type]
        techs_assigned = len(shift_data["technologists"])
        eng_required = ENG_PER_SHIFT
        eng_assigned = 1 if shift_data["engineer"] is not None else 0
        
        return {
            "complete": (techs_assigned >= techs_required and eng_assigned >= eng_required),
            "technologists": {"required": techs_required, "assigned": techs_assigned},
            "engineer": {"required": eng_required, "assigned": eng_assigned}
        }
    
    def verify_unique_assignments(self) -> List[str]:
        """
        Verifica que no haya asignaciones duplicadas en el horario.
        
        Returns:
            List: Lista de errores encontrados
        """
        errors = []
        
        for day in self.days:
            date = day["date"]
            date_str = date.strftime("%Y-%m-%d")
            
            for shift_type in SHIFT_TYPES:
                shift = day["shifts"][shift_type]
                
                # Verificar tecnólogos duplicados
                tech_ids = shift["technologists"]
                unique_techs = set(tech_ids)
                
                if len(unique_techs) < len(tech_ids):
                    errors.append(f"Tecnólogos duplicados en {date_str} {shift_type}: {tech_ids}")
                    
                    # Corregir automáticamente
                    shift["technologists"] = list(unique_techs)
                    
        return errors
    
    def print_summary(self):
        """Imprime un resumen del horario actual."""
        total_shifts = len(self.days) * len(SHIFT_TYPES)
        
        # Contar turnos con cobertura completa
        complete_shifts = 0
        total_techs = 0
        total_engs = 0
        
        for day in self.days:
            date = day["date"]
            for shift_type in SHIFT_TYPES:
                coverage = self.get_shift_coverage(date, shift_type)
                if coverage["complete"]:
                    complete_shifts += 1
                total_techs += coverage["technologists"]["assigned"]
                total_engs += coverage["engineer"]["assigned"]
        
        # Mostrar resumen
        print(f"=== Resumen del Horario ===")
        print(f"Período: {self.start_date.strftime('%d/%m/%Y')} - {self.end_date.strftime('%d/%m/%Y')}")
        print(f"Trabajadores: {len(self.get_technologists())} tecnólogos, {len(self.get_engineers())} ingenieros")
        print(f"Turnos: {total_shifts} en total")
        print(f"Cobertura: {complete_shifts}/{total_shifts} turnos completos ({complete_shifts/total_shifts*100:.1f}%)")
        print(f"Asignaciones: {total_techs} tecnólogos y {total_engs} ingenieros asignados")