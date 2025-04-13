import os
import sys
import io
from contextlib import redirect_stdout
import time
import signal

# Suppress library loading messages during import
original_stdout = sys.stdout
sys.stdout = io.StringIO()

from ortools.algorithms.python import knapsack_solver

# Restore stdout after imports
sys.stdout = original_stdout


# Setup global timeout flag
timeout_occurred = False

def timeout_handler(signum, frame):
    """Signal handler for timeouts"""
    global timeout_occurred
    timeout_occurred = True
    print("WARNING: Time limit exceeded during solving!")
    # We don't raise an exception here because we want a graceful return
    # from the solver with partial results


def read_kplib_file(file_path):
    """Read a knapsack problem file in the kplib format."""
    try:
        # Print file reading information
        print(f"    Reading file: {os.path.basename(file_path)}")
        
        with open(file_path, 'r') as file:
            content = file.read().strip()
            
        # Get file stats
        file_size = os.path.getsize(file_path)
        file_lines = content.count('\n') + 1
        
        print(f"    File size: {file_size} bytes")
        print(f"    File lines: {file_lines}")
        
        # Split the content into lines
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        
        # First line should contain the capacity
        if not lines:
            raise ValueError("File is empty")
            
        # Parse the capacity
        capacity = int(lines[0])
        
        # Parse items (value, weight pairs)
        values = []
        weights = []
        
        for i in range(1, len(lines)):
            parts = lines[i].split()
            if len(parts) >= 2:
                values.append(int(parts[0]))
                weights.append(int(parts[1]))
        
        # Calculate statistics about the problem
        num_items = len(values)
        total_value = sum(values)
        total_weight = sum(weights)
        avg_value = total_value / num_items if num_items > 0 else 0
        avg_weight = total_weight / num_items if num_items > 0 else 0
        
        # Print problem information
        print(f"    >>> PROBLEM DETAILS <<<")
        print(f"    Number of items: {num_items}")
        print(f"    Knapsack capacity: {capacity}")
        print(f"    Total value of all items: {total_value}")
        print(f"    Total weight of all items: {total_weight}")
        print(f"    Average item value: {avg_value:.2f}")
        print(f"    Average item weight: {avg_weight:.2f}")
        
        return values, weights, capacity
        
    except Exception as e:
        raise ValueError(f"Error reading file: {str(e)}")


def solver_knapsack(values, weights, capacity, time_limit=180):
    """
    Solve a knapsack problem using OR-Tools with improved timeout handling.
    
    Args:
        values: List of item values
        weights: List of item weights
        capacity: Knapsack capacity
        time_limit: Maximum time in seconds to spend solving
        
    Returns:
        Dictionary with solution details
    """
    global timeout_occurred
    timeout_occurred = False
    
    # Print solving message with time limit
    print(f"\n    >>> SOLVING PROBLEM <<<")
    print(f"    Algorithm: Branch and Bound")
    print(f"    Time limit: {time_limit} seconds")
    print(f"    Items to consider: {len(values)}")
    print(f"    Starting solver...")
    
    # Set up timeout signal if on Unix-like system
    can_use_signals = hasattr(signal, 'SIGALRM')
    if can_use_signals:
        # Set the signal handler
        signal.signal(signal.SIGALRM, timeout_handler)
        # Set the alarm to go off 5 seconds before the time limit
        # This gives the solver a chance to return partial results
        signal.alarm(max(1, time_limit - 5))
    
    # Also set a deadline for manual checking
    deadline = time.time() + time_limit
    
    try:
        # Suppress library loading messages
        with redirect_stdout(io.StringIO()):
            # Create solver
            solver = knapsack_solver.KnapsackSolver(
                knapsack_solver.SolverType.KNAPSACK_MULTIDIMENSION_BRANCH_AND_BOUND_SOLVER,
                'KnapsackExample'
            )
            
            # Set time limit in milliseconds (slightly shorter to ensure our timeout occurs first)
            internal_time_limit = max(1, time_limit - 10)  # 10 seconds shorter
            solver.set_time_limit(internal_time_limit * 1000)
            
            # Convert weights to list of lists as expected by the solver
            weights_as_list_of_lists = [weights]
            
            # Initialize the solver
            solver.init(values, weights_as_list_of_lists, [capacity])
            
            # Start timing
            start_time = time.time()
            
            # Solve the problem
            computed_value = solver.solve()
            is_optimal = solver.is_solution_optimal()
            
            # Periodically check if we've exceeded the deadline
            # This is a redundant check in case the alarm doesn't work
            if time.time() > deadline:
                timeout_occurred = True
                print("WARNING: Manual timeout check detected time limit exceeded!")
                is_optimal = False
            
            # End timing
            end_time = time.time()
            solve_time = end_time - start_time
            
            # Extract solution details
            packed_items = []
            packed_weights = []
            total_weight = 0
            
            for i in range(len(values)):
                if solver.best_solution_contains(i):
                    packed_items.append(i)
                    packed_weights.append(weights[i])
                    total_weight += weights[i]
    
    except Exception as e:
        print(f"ERROR during solving: {str(e)}")
        # Return default empty solution
        return {
            'value': 0,
            'items': [],
            'weight': 0,
            'optimal': False
        }
    finally:
        # Clear alarm if we used signals
        if can_use_signals:
            signal.alarm(0)
    
    # Print solution information
    print(f"\n    >>> SOLUTION DETAILS <<<")
    print(f"    Status: {'OPTIMAL' if is_optimal else 'SUB-OPTIMAL (time limit reached)'}")
    print(f"    Solving time: {solve_time:.2f} seconds")
    print(f"    Solution value: {computed_value}")
    print(f"    Solution weight: {total_weight}/{capacity} ({total_weight/capacity*100:.1f}% of capacity)")
    print(f"    Items selected: {len(packed_items)}/{len(values)} ({len(packed_items)/len(values)*100:.1f}% of items)")
    
    # If a timeout occurred, force is_optimal to False
    if timeout_occurred:
        is_optimal = False
    
    return {
        'value': computed_value,
        'items': packed_items,
        'weight': total_weight,
        'optimal': is_optimal
    }