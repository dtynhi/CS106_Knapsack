import os
import sys
import io
from contextlib import redirect_stdout
import time
import signal

# Suppress library loading messages
original_stdout = sys.stdout
sys.stdout = io.StringIO()
from ortools.algorithms.python import knapsack_solver
sys.stdout = original_stdout

# Global timeout flag
timeout_occurred = False

def timeout_handler(signum, frame):
    global timeout_occurred
    timeout_occurred = True

def read_kplib_file(file_path):
    """Read a knapsack problem file in kplib format."""
    try:
        with open(file_path, 'r') as file:
            lines = [line.strip() for line in file.read().strip().split('\n') if line.strip()]
        
        if not lines:
            raise ValueError("File is empty")
            
        capacity = int(lines[0])
        values = []
        weights = []
        
        for i in range(1, len(lines)):
            parts = lines[i].split()
            if len(parts) >= 2:
                values.append(int(parts[0]))
                weights.append(int(parts[1]))
        
        return values, weights, capacity
        
    except Exception as e:
        raise ValueError(f"Error reading file: {str(e)}")

def solver_knapsack(values, weights, capacity, time_limit=180):
    """
    Solve knapsack problem using OR-Tools with timeout handling.
    
    Args:
        values: List of item values
        weights: List of item weights
        capacity: Knapsack capacity
        time_limit: Maximum time in seconds
        
    Returns:
        Dictionary with solution details
    """
    global timeout_occurred
    timeout_occurred = False
    
    # Set up timeout signal if available
    can_use_signals = hasattr(signal, 'SIGALRM')
    if can_use_signals:
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(max(1, time_limit - 5))
    
    deadline = time.time() + time_limit
    
    try:
        with redirect_stdout(io.StringIO()):
            solver = knapsack_solver.KnapsackSolver(
                knapsack_solver.SolverType.KNAPSACK_MULTIDIMENSION_BRANCH_AND_BOUND_SOLVER,
                'KnapsackExample'
            )
            
            solver.set_time_limit(max(1, time_limit - 10) * 1000)
            solver.init(values, [weights], [capacity])
            
            start_time = time.time()
            computed_value = solver.solve()
            is_optimal = solver.is_solution_optimal()
            
            if time.time() > deadline:
                timeout_occurred = True
                is_optimal = False
            
            end_time = time.time()
            solve_time = end_time - start_time
            
            packed_items = []
            packed_weights = []
            total_weight = 0
            
            for i in range(len(values)):
                if solver.best_solution_contains(i):
                    packed_items.append(i)
                    packed_weights.append(weights[i])
                    total_weight += weights[i]
    
    except Exception as e:
        return {
            'value': 0,
            'items': [],
            'weight': 0,
            'optimal': False,
            'time': 0
        }
    finally:
        if can_use_signals:
            signal.alarm(0)
    
    if timeout_occurred:
        is_optimal = False
    
    return {
        'value': computed_value,
        'items': packed_items,
        'weight': total_weight,
        'optimal': is_optimal,
        'time': solve_time
    }