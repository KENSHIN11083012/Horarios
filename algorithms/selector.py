"""
Algoritmos para selección de trabajadores para turnos.
"""

from algorithms.common import create_date_index, predict_assignment_impact



def select_workers_proactively(workers, num_needed, date, shift_type, schedule, date_index=None):
    """
    Selecciona trabajadores para un turno considerando proactivamente el impacto
    futuro de cada asignación para minimizar las violaciones.
    
    Args:
        workers: Lista de trabajadores elegibles
        num_needed: Número de trabajadores necesarios
        date: Fecha del turno
        shift_type: Tipo de turno
        schedule: Horario actual
        date_index: Índice de fechas para acceso rápido
        
    Returns:
        list: Trabajadores seleccionados optimizados para minimizar violaciones
    """
    if date_index is None:
        date_index = create_date_index(schedule)
    
    # Evaluar el impacto de cada trabajador
    worker_impacts = []
    
    for worker in workers:
        can_assign, violations, impact_score = predict_assignment_impact(
            schedule, worker, date, shift_type, date_index
        )
        
        if can_assign:
            # Calcular un puntaje combinado que considere:
            # 1. Impacto negativo en el futuro (menor es mejor)
            # 2. Carga actual (menor es mejor)
            # 3. Experiencia con este tipo de turno (más es mejor, para especialización)
            workload = worker.get_shift_count()
            shift_experience = worker.get_shift_types_count().get(shift_type, 0)
            
            # Normalizar el impacto a un rango manejable
            normalized_impact = min(impact_score, 20) / 20.0
            
            # Fórmula de scoring: más bajo = mejor candidato
            # La ponderación prioriza minimizar el impacto negativo
            combined_score = normalized_impact * 0.6 + (workload / 30.0) * 0.3 - (shift_experience / 10.0) * 0.1
            
            worker_impacts.append((worker, combined_score, impact_score, violations))
    
    # Ordenar por score combinado (menor primero = mejor candidato)
    worker_impacts.sort(key=lambda x: x[1])
    
    # Seleccionar los mejores candidatos
    selected_workers = [wi[0] for wi in worker_impacts[:num_needed]]
    
    # Para fines de registro, mostrar los trabajadores seleccionados y sus impactos
    if selected_workers and len(selected_workers) > 0:
        print(f"  Selección proactiva para {date.strftime('%d/%m/%Y')} {shift_type}:")
        for worker, score, impact, violations in worker_impacts[:min(num_needed, len(worker_impacts))]:
            violations_str = ", ".join(violations) if violations else "ninguna"
            print(f"    - {worker.get_formatted_id()}: score={score:.2f}, impacto={impact}")
    
    return selected_workers