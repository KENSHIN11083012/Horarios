import random

def select_workers_for_shift(eligible_workers, num_needed, date, shift_type):

    from config import is_colombian_holiday
    
    # Determinar si el turno es nocturno o en festivo (mayor remuneración)
    is_night = (shift_type == "Noche")
    is_holiday = is_colombian_holiday(date)
    is_sunday = (date.weekday() == 6)
    is_premium_shift = is_night or is_holiday or is_sunday
    
    # Si es un turno con prima, priorizar trabajadores con menos ganancias
    if is_premium_shift:
        # Ordenar por ganancias acumuladas (ascendente)
        eligible_workers.sort(key=lambda w: w.earnings)
    else:
        # Para otros turnos, ordenar por total de turnos trabajados
        eligible_workers.sort(key=lambda w: w.get_shift_count())
    
    # Aplicar una segunda capa de ordenamiento basado en el tipo específico de turno
    # Agrupar trabajadores por número de turnos trabajados o ganancias similares
    grouped_workers = []
    if is_premium_shift:
        # Usar rangos de ganancias para agrupar
        min_earnings = min(w.earnings for w in eligible_workers) if eligible_workers else 0
        max_earnings = max(w.earnings for w in eligible_workers) if eligible_workers else 0
        earnings_range = max_earnings - min_earnings
        
        # Crear 3 grupos de ganancias (bajo, medio, alto) si hay suficiente variación
        if earnings_range > 0.5:  # Umbral arbitrario para determinar si hay variación significativa
            num_groups = 3
            group_size = earnings_range / num_groups
            
            for i in range(num_groups):
                lower_bound = min_earnings + i * group_size
                upper_bound = min_earnings + (i + 1) * group_size
                
                group = [w for w in eligible_workers 
                         if lower_bound <= w.earnings < upper_bound]
                
                if group:
                    # Dentro de cada grupo, ordenar por número de este tipo de turno
                    group.sort(key=lambda w: w.get_shift_types_count()[shift_type])
                    grouped_workers.append(group)
        else:
            # Si no hay mucha variación, usar un solo grupo
            eligible_workers.sort(key=lambda w: w.get_shift_types_count()[shift_type])
            grouped_workers = [eligible_workers]
    else:
        # Para turnos normales, agrupar por número de turnos totales
        shift_counts = {}
        for worker in eligible_workers:
            count = worker.get_shift_count()
            if count not in shift_counts:
                shift_counts[count] = []
            shift_counts[count].append(worker)
        
        # Ordenar grupos por número de turnos
        for count in sorted(shift_counts.keys()):
            group = shift_counts[count]
            # Ordenar por número de este tipo específico de turno
            group.sort(key=lambda w: w.get_shift_types_count()[shift_type])
            grouped_workers.append(group)
    
    # Seleccionar trabajadores de cada grupo
    selected_workers = []
    remaining_needed = num_needed
    
    for group in grouped_workers:
        # Determinar cuántos seleccionar de este grupo
        to_select = min(remaining_needed, len(group))
        
        if to_select > 0:
            # Tomar los primeros trabajadores del grupo (ya ordenados)
            selected = group[:to_select]
            
            # Aplicar algo de aleatoriedad para mejorar rotación
            if len(selected) > 1:
                # 20% de probabilidad de reordenar aleatoriamente
                if random.random() < 0.2:
                    random.shuffle(selected)
            
            selected_workers.extend(selected)
            remaining_needed -= to_select
        
        if remaining_needed == 0:
            break
    
    return selected_workers