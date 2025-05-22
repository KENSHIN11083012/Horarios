"""
Módulo especializado para el balance de turnos y equidad.
"""

from datetime import datetime
from config.settings import SHIFT_TYPES
from utils.compensation import calculate_compensation
from config import is_colombian_holiday
from core.constraints import check_night_to_day_transition, check_consecutive_shifts, check_adequate_rest
from algorithms.common import create_date_index

def balance_workload(schedule, technologists, engineers, date_index=None):
    """
    Equilibra la carga de trabajo entre trabajadores.
    
    Args:
        schedule: Horario a modificar
        technologists: Lista de tecnólogos
        engineers: Lista de ingenieros
        date_index: Índice de fechas para acceso rápido
    """
    print("Balanceando carga de trabajo...")
    
    # Usar índice para acceso O(1)
    if date_index is None:
        date_index = create_date_index(schedule)
    
    # Realizar múltiples pasadas para un mejor equilibrio
    for i in range(2):  # Realizar 2 pasadas
        print(f"  Pasada de balance {i+1}...")
        
        # Balancear tecnólogos
        balance_worker_group(schedule, technologists, date_index)
        
        # Balancear ingenieros
        balance_worker_group(schedule, engineers, date_index)
        
    # Balanceo específico de turnos premium
    balance_premium_shifts(schedule, technologists, date_index)
    balance_premium_shifts(schedule, engineers, date_index)


def balance_worker_group(schedule, workers, date_index=None):
    """
    Equilibra la carga de trabajo dentro de un grupo de trabajadores.
    
    Args:
        schedule: Horario a modificar
        workers: Lista de trabajadores del mismo tipo
        date_index: Índice de fechas para acceso rápido
    """
    # Usar índice para acceso O(1)
    if date_index is None:
        date_index = create_date_index(schedule)
        
    group_type = "Tecnólogos" if workers[0].is_technologist else "Ingenieros"
    print(f"  Balanceando grupo: {group_type}")
    
    # Calcular la duración del período en días
    period_duration = (schedule.end_date - schedule.start_date).days + 1
    
    # Analizar distribución actual de turnos
    shifts_per_worker = {w.id: w.get_shift_count() for w in workers}
    min_shifts = min(shifts_per_worker.values()) if shifts_per_worker else 0
    max_shifts = max(shifts_per_worker.values()) if shifts_per_worker else 0
    
    # Calcular estadísticas del grupo para umbral dinámico
    avg_shifts_per_worker = sum(shifts_per_worker.values()) / len(workers) if workers else 0
    
    # Calcular turnos promedio por tipo y trabajador
    avg_shifts_per_type = avg_shifts_per_worker / len(SHIFT_TYPES)
    
    # Calcular umbral de desequilibrio dinámico basado en la duración y promedio
    # Fórmula: Base + Factor * (Duración / 30)
    base_threshold = 1.5  # Umbral mínimo
    scale_factor = 0.5    # Factor de escala por mes
    
    # Calcular umbral dinámico (aumenta con la duración del período)
    dynamic_threshold = base_threshold + scale_factor * (period_duration / 30)
    
    # Ajustar umbral basado en el promedio de turnos por tipo
    # Para períodos cortos con pocos turnos, el umbral puede ser muy bajo
    min_threshold = max(1, avg_shifts_per_type * 0.25)  # Mínimo 1 o 25% del promedio
    
    # Elegir el umbral final (el mayor entre el dinámico y el mínimo)
    final_threshold = max(dynamic_threshold, min_threshold)
    
    print(f"    Umbral de desequilibrio para período de {period_duration} días: {final_threshold:.1f}")
    
    # Equilibrar turnos totales
    if max_shifts - min_shifts > 1:
        print(f"    Diferencia actual de turnos totales: {min_shifts}-{max_shifts}")
        
        # Identificar trabajadores con más y menos turnos
        workers_with_most = [w for w in workers if w.get_shift_count() == max_shifts]
        workers_with_least = [w for w in workers if w.get_shift_count() == min_shifts]
        
        # Intentar transferencias
        transfers_made = 0
        max_transfers = 8
        
        for from_worker in workers_with_most:
            if transfers_made >= max_transfers:
                break
                
            for to_worker in workers_with_least:
                if transfers_made >= max_transfers:
                    break
                    
                # Intentar transferir un turno
                if transfer_shift_safely(schedule, from_worker, to_worker, date_index):
                    transfers_made += 1
                    print(f"      Turno transferido de {from_worker.get_formatted_id()} a {to_worker.get_formatted_id()}")
    
    # Analizar y corregir desequilibrios de tipos de turno usando el umbral dinámico
    desequilibrios_corregidos = 0
    
    for worker in workers:
        counts = worker.get_shift_types_count()
        if not counts:
            continue
            
        max_type = max(counts, key=counts.get)
        min_type = min(counts, key=counts.get)
        
        # Calcular desequilibrio relativo (%)
        min_count = counts.get(min_type, 0)
        max_count = counts.get(max_type, 0)
        
        # Evitar división por cero
        if min_count > 0:
            imbalance_percent = (max_count - min_count) / min_count * 100
        else:
            # Si un tipo tiene 0 turnos, el desequilibrio es máximo
            imbalance_percent = 100
            
        # Usar tanto el umbral absoluto como un umbral relativo
        absolute_imbalance = max_count - min_count
        should_balance = absolute_imbalance > final_threshold
        
        # Para períodos largos, también considerar el desequilibrio porcentual
        if period_duration > 14:  # Más de dos semanas
            should_balance = should_balance or (imbalance_percent > 40)  # 40% de desequilibrio
            
        if should_balance:
            print(f"    Desequilibrio de tipos en {worker.get_formatted_id()}: " +
                  f"{min_type}={min_count}, {max_type}={max_count} " +
                  f"(Δ={absolute_imbalance:.1f}, {imbalance_percent:.1f}%)")
            
            # Intentar equilibrar con cualquier otro trabajador
            for other_worker in workers:
                if other_worker.id == worker.id:
                    continue
                
                other_counts = other_worker.get_shift_types_count()
                
                # Si el otro tiene más del tipo que este tiene menos y viceversa
                if other_counts.get(min_type, 0) > counts.get(min_type, 0) and counts.get(max_type, 0) > other_counts.get(max_type, 0):
                    # Intentar intercambiar un turno de cada tipo
                    if exchange_shifts_by_type(schedule, worker, other_worker, min_type, max_type, date_index):
                        desequilibrios_corregidos += 1
                        print(f"      Intercambio de tipos entre {worker.get_formatted_id()} y {other_worker.get_formatted_id()}")
                        break
    
    print(f"    Desequilibrios corregidos: {desequilibrios_corregidos}")


def balance_premium_shifts(schedule, workers, date_index=None):
    """
    Función para balancear específicamente los turnos premium.
    
    Args:
        schedule: Horario a modificar
        workers: Lista de trabajadores del mismo tipo
        date_index: Índice de fechas para acceso rápido
    """
    # Usar índice para acceso O(1)
    if date_index is None:
        date_index = create_date_index(schedule)
        
    print(f"  Balanceando turnos premium para {workers[0].get_formatted_id()[0]}'s...")
    
    # Contar turnos premium por trabajador
    premium_counts = {}
    for worker in workers:
        premium_count = 0
        premium_value = 0.0
        
        for date, shift_type in worker.shifts:
            is_weekend = date.weekday() >= 5
            is_night = shift_type == "Noche"
            is_holiday = is_colombian_holiday(date)
            
            if is_weekend or is_night or is_holiday:
                premium_count += 1
                premium_value += calculate_compensation(date, shift_type)
        
        premium_counts[worker.id] = (premium_count, premium_value)
    
    # Encontrar trabajadores con más y menos turnos premium
    min_premium = min(premium_counts.values(), key=lambda x: x[1]) if premium_counts else (0, 0)
    max_premium = max(premium_counts.values(), key=lambda x: x[1]) if premium_counts else (0, 0)
    
    # Calcular diferencia
    min_value = min_premium[1]
    max_value = max_premium[1]
    diff_percent = (max_value - min_value) / min_value * 100 if min_value > 0 else 0
    
    print(f"    Diferencia en valor premium: {diff_percent:.1f}%")
    
    # Si la diferencia es significativa, intentar equilibrar
    if diff_percent > 15:
        workers_with_most = [w for w in workers if premium_counts[w.id][1] > (min_value * 1.15)]
        workers_with_least = [w for w in workers if premium_counts[w.id][1] < (max_value * 0.85)]
        
        transfers_made = 0
        max_transfers = 5
        
        for from_worker in workers_with_most:
            if transfers_made >= max_transfers:
                break
                
            for to_worker in workers_with_least:
                if transfers_made >= max_transfers:
                    break
                    
                # Intentar transferir un turno premium específicamente
                if transfer_premium_shift(schedule, from_worker, to_worker, date_index):
                    transfers_made += 1
                    print(f"      Turno premium transferido de {from_worker.get_formatted_id()} a {to_worker.get_formatted_id()}")


def transfer_shift_safely(schedule, from_worker, to_worker, date_index=None):
    """
    Transfiere un turno entre trabajadores sin generar violaciones.
    
    Args:
        schedule: Horario a modificar
        from_worker: Trabajador origen
        to_worker: Trabajador destino
        date_index: Índice de fechas para acceso rápido
        
    Returns:
        bool: True si se realizó la transferencia, False en caso contrario
    """
    # Usar índice para acceso O(1)
    if date_index is None:
        date_index = create_date_index(schedule)
        
    # Ordenar turnos del trabajador con más turnos (descendente por fecha)
    shifts = sorted(from_worker.shifts, key=lambda x: x[0], reverse=True)
    
    # Probar cada turno, empezando por los más recientes
    for date, shift_type in shifts:
        # Verificar si el trabajador destino puede tomar este turno
        if date in to_worker.days_off:
            continue
            
        if any(d == date for d, _ in to_worker.shifts):
            continue
        
        # Verificar restricciones críticas
        night_to_day = check_night_to_day_transition(to_worker, date, shift_type)
        consecutive = check_consecutive_shifts(to_worker, date, shift_type)
        adequate_rest = check_adequate_rest(to_worker, date, shift_type)
        
        if night_to_day or consecutive or not adequate_rest:
            continue
        
        # Encontrar el turno en el horario usando el índice
        day_data = date_index.get(date)
        
        if day_data:
            shift_data = day_data["shifts"][shift_type]
            
            # Quitar trabajador origen
            if from_worker.is_technologist:
                if from_worker.id in shift_data["technologists"]:
                    shift_data["technologists"].remove(from_worker.id)
            else:
                if shift_data["engineer"] == from_worker.id:
                    shift_data["engineer"] = None
            
            # Quitar del registro del trabajador
            from_worker.shifts = [(d, s) for d, s in from_worker.shifts 
                                if not (d == date and s == shift_type)]
            
            # Asignar al trabajador destino
            schedule.assign_worker(to_worker, date, shift_type)
            
            return True
    
    return False


def exchange_shifts_by_type(schedule, worker1, worker2, type1, type2, date_index=None):
    """
    Intercambia turnos de diferentes tipos entre dos trabajadores.
    
    Args:
        schedule: Horario a modificar
        worker1: Primer trabajador
        worker2: Segundo trabajador
        type1: Tipo de turno a intercambiar para worker1
        type2: Tipo de turno a intercambiar para worker2
        date_index: Índice de fechas para acceso rápido
        
    Returns:
        bool: True si se realizó el intercambio, False en caso contrario
    """
    # Usar índice para acceso O(1)
    if date_index is None:
        date_index = create_date_index(schedule)
        
    # Buscar un turno de type1 que worker2 pueda realizar
    type1_shifts = [(d, s) for d, s in worker2.shifts if s == type1]
    
    for date1, _ in type1_shifts:
        # Verificar si worker1 puede realizar este turno
        if date1 in worker1.days_off:
            continue
            
        if any(d == date1 and s != type1 for d, s in worker1.shifts):
            continue
        
        # Verificar restricciones para worker1
        night_to_day1 = check_night_to_day_transition(worker1, date1, type1)
        consecutive1 = check_consecutive_shifts(worker1, date1, type1)
        adequate_rest1 = check_adequate_rest(worker1, date1, type1)
        
        if night_to_day1 or consecutive1 or not adequate_rest1:
            continue
        
        # Buscar un turno de type2 que worker1 pueda ceder a worker2
        type2_shifts = [(d, s) for d, s in worker1.shifts if s == type2]
        
        for date2, _ in type2_shifts:
            # Verificar si worker2 puede realizar este turno
            if date2 in worker2.days_off:
                continue
                
            if any(d == date2 and s != type2 for d, s in worker2.shifts):
                continue
            
            # Verificar restricciones para worker2
            night_to_day2 = check_night_to_day_transition(worker2, date2, type2)
            consecutive2 = check_consecutive_shifts(worker2, date2, type2)
            adequate_rest2 = check_adequate_rest(worker2, date2, type2)
            
            if night_to_day2 or consecutive2 or not adequate_rest2:
                continue
            
            # Realizar el intercambio usando el índice
            
            # 1. Quitar worker2 de su turno type1
            day_data1 = date_index.get(date1)
            if day_data1:
                shift_data1 = day_data1["shifts"][type1]
                if worker2.is_technologist:
                    if worker2.id in shift_data1["technologists"]:
                        shift_data1["technologists"].remove(worker2.id)
                else:
                    if shift_data1["engineer"] == worker2.id:
                        shift_data1["engineer"] = None
            
            # 2. Quitar worker1 de su turno type2
            day_data2 = date_index.get(date2)
            if day_data2:
                shift_data2 = day_data2["shifts"][type2]
                if worker1.is_technologist:
                    if worker1.id in shift_data2["technologists"]:
                        shift_data2["technologists"].remove(worker1.id)
                else:
                    if shift_data2["engineer"] == worker1.id:
                        shift_data2["engineer"] = None
            
            # 3. Actualizar registros de trabajadores
            worker1.shifts = [(d, s) for d, s in worker1.shifts if not (d == date2 and s == type2)]
            worker2.shifts = [(d, s) for d, s in worker2.shifts if not (d == date1 and s == type1)]
            
            # 4. Asignar nuevos turnos
            schedule.assign_worker(worker1, date1, type1)
            schedule.assign_worker(worker2, date2, type2)
            
            return True
    
    return False


def transfer_premium_shift(schedule, from_worker, to_worker, date_index=None):
    """
    Transfiere un turno premium (fin de semana o noche) entre trabajadores.
    Versión mejorada que prioriza mejor los turnos más valiosos y usa el índice.
    
    Args:
        schedule: Horario a modificar
        from_worker: Trabajador origen
        to_worker: Trabajador destino
        date_index: Índice de fechas para acceso rápido
        
    Returns:
        bool: True si se realizó la transferencia, False en caso contrario
    """
    # Usar índice para acceso O(1)
    if date_index is None:
        date_index = create_date_index(schedule)
    
    # Identificar turnos premium del trabajador origen
    premium_shifts = []
    for date, shift_type in from_worker.shifts:
        is_weekend = date.weekday() >= 5  # 5=Sábado, 6=Domingo
        is_night = shift_type == "Noche"
        is_holiday = is_colombian_holiday(date)  # Añadir verificación de festivos
        
        if is_weekend or is_night or is_holiday:
            premium_shifts.append((date, shift_type))
    
    # Calcular valor exacto de compensación para ordenar mejor
    def premium_value(shift):
        date, shift_type = shift
        return calculate_compensation(date, shift_type)
    
    # Ordenar por valor real de compensación (descendente)
    premium_shifts.sort(key=premium_value, reverse=True)
    
    # Probar cada turno premium
    for date, shift_type in premium_shifts:
        # Verificar si el trabajador destino puede tomar este turno
        if date in to_worker.days_off:
            continue
            
        if any(d == date for d, _ in to_worker.shifts):
            continue
        
        # Relajar algunas restricciones para aumentar probabilidad de transferencia exitosa
        night_to_day = check_night_to_day_transition(to_worker, date, shift_type)
        consecutive = check_consecutive_shifts(to_worker, date, shift_type)
        
        # Restricciones críticas que nunca deben relajarse
        if night_to_day or consecutive:
            continue
        
        # Verificar si esta transferencia realmente mejorará la equidad
        # Proyectar las nuevas ganancias después de la transferencia
        compensation_value = calculate_compensation(date, shift_type)
        from_worker_new_earnings = from_worker.earnings - compensation_value
        to_worker_new_earnings = to_worker.earnings + compensation_value
        
        # Verificar que la transferencia mejore la equidad y no invierta la situación
        if from_worker_new_earnings < to_worker_new_earnings:
            continue
        
        # Encontrar el turno en el horario usando el índice
        day_data = date_index.get(date)
        
        if day_data:
            shift_data = day_data["shifts"][shift_type]
            
            # Quitar trabajador origen
            if from_worker.is_technologist:
                if from_worker.id in shift_data["technologists"]:
                    shift_data["technologists"].remove(from_worker.id)
            else:
                if shift_data["engineer"] == from_worker.id:
                    shift_data["engineer"] = None
            
            # Quitar del registro del trabajador
            from_worker.shifts = [(d, s) for d, s in from_worker.shifts 
                                if not (d == date and s == shift_type)]
            
            # Asignar al trabajador destino
            schedule.assign_worker(to_worker, date, shift_type)
            
            # Actualizar las ganancias
            from_worker.earnings = from_worker_new_earnings
            to_worker.earnings = to_worker_new_earnings
            
            return True
    
    return False


def optimize_fairness(schedule, technologists, engineers, date_index=None):
    """
    Realiza una optimización final para maximizar la equidad.
    Versión mejorada con umbral de diferencia mínimo y más transferencias.
    
    Args:
        schedule: Horario a optimizar
        technologists: Lista de tecnólogos
        engineers: Lista de ingenieros
        date_index: Índice de fechas para acceso rápido
    """
    print("Realizando optimización final para equidad...")
    
    # Usar índice para acceso O(1)
    if date_index is None:
        date_index = create_date_index(schedule)
    
    # Calcular ganancias por trabajador
    for worker in technologists + engineers:
        worker.earnings = sum(calculate_compensation(d, s) for d, s in worker.shifts)
    
    # Analizar distribución de ganancias
    tech_earnings = [t.earnings for t in technologists]
    eng_earnings = [e.earnings for e in engineers]
    
    tech_min = min(tech_earnings) if tech_earnings else 0
    tech_max = max(tech_earnings) if tech_earnings else 0
    tech_diff_percent = (tech_max - tech_min) / tech_min * 100 if tech_min > 0 else 0
    
    eng_min = min(eng_earnings) if eng_earnings else 0
    eng_max = max(eng_earnings) if eng_earnings else 0
    eng_diff_percent = (eng_max - eng_min) / eng_min * 100 if eng_min > 0 else 0
    
    print(f"  Diferencia de ganancias en tecnólogos: {tech_diff_percent:.1f}%")
    print(f"  Diferencia de ganancias en ingenieros: {eng_diff_percent:.1f}%")
    
    # Umbral reducido al 3% para una distribución casi perfecta
    EQUITY_THRESHOLD = 3.0
    
    # Si la diferencia supera el umbral, intentar equilibrar
    if tech_diff_percent > EQUITY_THRESHOLD:
        print(f"  Optimizando equidad de ganancias en tecnólogos (objetivo: <{EQUITY_THRESHOLD}%)...")
        
        # Realizar múltiples pasadas para un balance perfecto
        max_passes = 3  # Máximo 3 pasadas para evitar bucles excesivos
        current_pass = 0
        
        while tech_diff_percent > EQUITY_THRESHOLD and current_pass < max_passes:
            current_pass += 1
            print(f"    Pasada de optimización {current_pass}, diferencia actual: {tech_diff_percent:.1f}%")
            
            # Ordenar tecnólogos por ganancias
            techs_by_earnings = sorted(technologists, key=lambda t: t.earnings)
            
            # Considerar más trabajadores para las transferencias (enfoque %)
            poorest_count = max(4, int(len(techs_by_earnings) * 0.40))  # 40% con menos ganancias
            richest_count = max(4, int(len(techs_by_earnings) * 0.40))  # 40% con más ganancias
            
            poorest = techs_by_earnings[:poorest_count]
            richest = techs_by_earnings[-richest_count:]
            
            # Aumentar el número máximo de transferencias basado en la magnitud del problema
            base_transfers = 15
            diff_factor = min(3.0, tech_diff_percent / EQUITY_THRESHOLD)  # Factor basado en la gravedad
            max_transfers = int(base_transfers * diff_factor)
            
            print(f"      Permitiendo hasta {max_transfers} transferencias para esta pasada")
            transfers = 0
            
            # Estrategia de priorización mejorada
            # Emparejar el más rico con el más pobre primero
            for rich_idx, rich in enumerate(reversed(richest)):
                if transfers >= max_transfers:
                    break
                    
                for poor_idx, poor in enumerate(poorest):
                    if transfers >= max_transfers:
                        break
                    
                    # Calcular ganancia relativa de la transferencia
                    earnings_gap = rich.earnings - poor.earnings
                    relative_gap = earnings_gap / tech_min * 100 if tech_min > 0 else 0
                    
                    # Solo proceder con transferencias significativas
                    min_relative_gap = 1.0  # 1% mínimo
                    
                    if relative_gap < min_relative_gap:
                        continue
                    
                    # Intentar transferir múltiples turnos si la diferencia es muy grande
                    max_transfers_per_pair = 1
                    if relative_gap > 8.0:
                        max_transfers_per_pair = 3
                    elif relative_gap > 5.0:
                        max_transfers_per_pair = 2
                    
                    pair_transfers = 0
                    while pair_transfers < max_transfers_per_pair and transfers < max_transfers:
                        if transfer_premium_shift(schedule, rich, poor, date_index):
                            transfers += 1
                            pair_transfers += 1
                            
                            # Recalcular ganancias
                            rich.earnings = sum(calculate_compensation(d, s) for d, s in rich.shifts)
                            poor.earnings = sum(calculate_compensation(d, s) for d, s in poor.shifts)
                            
                            print(f"      Transferido turno premium de {rich.get_formatted_id()} ({rich.earnings:.2f}) " + 
                                  f"a {poor.get_formatted_id()} ({poor.earnings:.2f})")
                        else:
                            # Si no se pudo transferir, pasar al siguiente par
                            break
            
            # Verificar si hubo mejora
            if transfers == 0:
                print("      No se pudieron realizar más transferencias. Finalizando optimización.")
                break
                
            # Recalcular estadísticas para próxima pasada
            tech_earnings = [t.earnings for t in technologists]
            tech_min = min(tech_earnings) if tech_earnings else 0
            tech_max = max(tech_earnings) if tech_earnings else 0
            old_diff = tech_diff_percent
            tech_diff_percent = (tech_max - tech_min) / tech_min * 100 if tech_min > 0 else 0
            
            improvement = old_diff - tech_diff_percent
            print(f"      Mejora: {improvement:.2f}%, nueva diferencia: {tech_diff_percent:.2f}%")
            
            # Si la mejora es muy pequeña, no continuar
            if improvement < 0.2:  # Menos de 0.2% de mejora
                print("      Mejora insignificante. Finalizando optimización.")
                break
    
    # Similar para ingenieros con umbral reducido
    if eng_diff_percent > EQUITY_THRESHOLD:
        print(f"  Optimizando equidad de ganancias en ingenieros (objetivo: <{EQUITY_THRESHOLD}%)...")
        
        # Similar a tecnólogos, múltiples pasadas
        max_passes = 3
        current_pass = 0
        
        while eng_diff_percent > EQUITY_THRESHOLD and current_pass < max_passes:
            current_pass += 1
            print(f"    Pasada de optimización {current_pass}, diferencia actual: {eng_diff_percent:.1f}%")
            
            # Ordenar ingenieros por ganancias
            engs_by_earnings = sorted(engineers, key=lambda e: e.earnings)
            
            # Para ingenieros, como son pocos, considerar a todos
            poorest = engs_by_earnings[:len(engs_by_earnings)//2]  # Primera mitad
            richest = engs_by_earnings[len(engs_by_earnings)//2:]  # Segunda mitad
            
            # Permitir más transferencias para grupos pequeños
            max_transfers = 8
            transfers = 0
            
            for rich in richest:
                if transfers >= max_transfers:
                    break
                    
                for poor in poorest:
                    if transfers >= max_transfers:
                        break
                    
                    # Calcular si vale la pena la transferencia
                    earnings_gap = rich.earnings - poor.earnings
                    relative_gap = earnings_gap / eng_min * 100 if eng_min > 0 else 0
                    
                    if relative_gap < 1.0:  # Ignorar diferencias mínimas
                        continue
                    
                    # Intentar hasta 2 transferencias por par si la diferencia es grande
                    max_transfers_per_pair = 1
                    if relative_gap > 5.0:
                        max_transfers_per_pair = 2
                    
                    pair_transfers = 0
                    while pair_transfers < max_transfers_per_pair and transfers < max_transfers:
                        if transfer_premium_shift(schedule, rich, poor, date_index):
                            transfers += 1
                            pair_transfers += 1
                            
                            # Recalcular ganancias
                            rich.earnings = sum(calculate_compensation(d, s) for d, s in rich.shifts)
                            poor.earnings = sum(calculate_compensation(d, s) for d, s in poor.shifts)
                            
                            print(f"      Transferido turno premium de {rich.get_formatted_id()} ({rich.earnings:.2f}) " +
                                 f"a {poor.get_formatted_id()} ({poor.earnings:.2f})")
                        else:
                            break
            
            # Verificar si hubo mejora
            if transfers == 0:
                break
                
            # Recalcular estadísticas para próxima pasada
            eng_earnings = [e.earnings for e in engineers]
            eng_min = min(eng_earnings) if eng_earnings else 0
            eng_max = max(eng_earnings) if eng_earnings else 0
            old_diff = eng_diff_percent
            eng_diff_percent = (eng_max - eng_min) / eng_min * 100 if eng_min > 0 else 0
            
            improvement = old_diff - eng_diff_percent
            print(f"      Mejora: {improvement:.2f}%, nueva diferencia: {eng_diff_percent:.2f}%")
            
            if improvement < 0.3:  # Menos de 0.3% de mejora para ingenieros
                break
    
    # Reportar equidad final
    tech_earnings = [t.earnings for t in technologists]
    eng_earnings = [e.earnings for e in engineers]
    
    tech_min = min(tech_earnings) if tech_earnings else 0
    tech_max = max(tech_earnings) if tech_earnings else 0
    tech_diff_percent = (tech_max - tech_min) / tech_min * 100 if tech_min > 0 else 0
    
    eng_min = min(eng_earnings) if eng_earnings else 0
    eng_max = max(eng_earnings) if eng_earnings else 0
    eng_diff_percent = (eng_max - eng_min) / eng_min * 100 if eng_min > 0 else 0
    
    print(f"  Equidad final: Tecnólogos {tech_diff_percent:.2f}%, Ingenieros {eng_diff_percent:.2f}%")
    
    # Calcular estadísticas detalladas
    tech_avg = sum(tech_earnings) / len(tech_earnings) if tech_earnings else 0
    eng_avg = sum(eng_earnings) / len(eng_earnings) if eng_earnings else 0
    
    tech_std_dev = (sum((e - tech_avg) ** 2 for e in tech_earnings) / len(tech_earnings)) ** 0.5 if tech_earnings else 0
    eng_std_dev = (sum((e - eng_avg) ** 2 for e in eng_earnings) / len(eng_earnings)) ** 0.5 if eng_earnings else 0
    
    print(f"  Estadísticas de compensación Tecnólogos: " +
          f"Min={tech_min:.2f}, Max={tech_max:.2f}, Promedio={tech_avg:.2f}, Desv={tech_std_dev:.2f}")
    print(f"  Estadísticas de compensación Ingenieros: " +
          f"Min={eng_min:.2f}, Max={eng_max:.2f}, Promedio={eng_avg:.2f}, Desv={eng_std_dev:.2f}")