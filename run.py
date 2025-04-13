import os
import csv
import time
import sys
import multiprocessing

# Import knapsack solver
from knapsack_solver import read_kplib_file, solver_knapsack

RESULT_FILE = 'results.csv'
KPLIB_FOLDER = 'kplib'
NUM_OF_TC = 5
TIME_LIMIT = 180  # Default time limit in seconds

# Set up multiprocessing for Windows
if __name__ == '__main__':
    multiprocessing.freeze_support()
    try:
        multiprocessing.set_start_method('spawn')
    except RuntimeError:
        pass  # Already set


def get_test_cases():
    """Get all test cases from the kplib folder."""
    test_cases = []
    
    try:
        problem_groups = [f for f in os.listdir(KPLIB_FOLDER) 
                         if os.path.isdir(os.path.join(KPLIB_FOLDER, f))]
        
        for group in problem_groups:
            group_test_cases = []
            group_path = os.path.join(KPLIB_FOLDER, group)
            
            # Get problem sizes (n00050, n00100, etc.)
            size_folders = [f for f in os.listdir(group_path)
                           if os.path.isdir(os.path.join(group_path, f)) and f.startswith('n')]
            
            # Sort by size and take up to NUM_OF_TC
            size_folders.sort(key=lambda x: int(x[1:]) if x[1:].isdigit() else 0)
            for size_folder in size_folders[:NUM_OF_TC]:
                size_path = os.path.join(group_path, size_folder)
                
                # Get type folders (R01000, etc.)
                type_folders = [f for f in os.listdir(size_path)
                               if os.path.isdir(os.path.join(size_path, f))]
                
                if not type_folders:
                    continue
                    
                # Take first type folder
                type_path = os.path.join(size_path, type_folders[0])
                
                # Get first .kp file
                kp_files = [f for f in os.listdir(type_path) if f.endswith('.kp')]
                if not kp_files:
                    continue
                    
                kp_file_path = os.path.join(type_path, kp_files[0])
                group_test_cases.append((size_folder, kp_file_path))
            
            if group_test_cases:
                test_cases.append((group, group_test_cases))
                
    except Exception as e:
        print(f"Error gathering test cases: {e}")
    
    return test_cases


def solve_problem_with_timeout(group_name, size_name, file_path, timeout):
    """
    Solve a single knapsack problem with timeout enforcement.
    Instead of creating a separate process, use internal timeout handling.
    """
    # Print problem information
    print(f"\n{'='*60}")
    print(f"SOLVING: Group={group_name}, Size={size_name}")
    print(f"File: {os.path.basename(file_path)}")
    print(f"Time limit: {timeout} seconds")
    print('='*60)
    
    try:
        # Start timer
        start_time = time.time()
        
        # Read problem instance
        values, weights, capacity = read_kplib_file(file_path)
        
        # Create a simple timer to enforce timeout
        max_end_time = start_time + timeout
        
        # Solve with explicit timeout check
        result = solver_knapsack(values, weights, capacity, timeout)
        
        # Check if we exceeded the time limit
        end_time = time.time()
        if end_time > max_end_time + 10:  # Allow a small buffer
            print(f"WARNING: Solver returned after exceeding time limit by {end_time - max_end_time:.2f} seconds")
            # Force optimal flag to False if we exceeded time limit
            result['optimal'] = False
        
        # Calculate solving time
        solve_time = end_time - start_time
        
        # Return results
        return {
            'group': group_name,
            'size': size_name,
            'file': os.path.relpath(file_path, KPLIB_FOLDER),
            'value': result['value'],
            'weight': result['weight'],
            'optimal': result['optimal'],
            'time': solve_time,
            'status': 'solved'
        }
    except Exception as e:
        print(f"Error solving problem: {str(e)}")
        return {
            'group': group_name,
            'size': size_name,
            'file': os.path.relpath(file_path, KPLIB_FOLDER),
            'value': 0,
            'weight': 0,
            'optimal': False,
            'time': 0,
            'status': f'error: {str(e)}'
        }


def run_problem_with_watchdog(problem_args, result_queue):
    """
    Run a knapsack problem with a watchdog timer.
    This function runs in a separate process.
    """
    try:
        group, size, file_path, timeout = problem_args
        result = solve_problem_with_timeout(group, size, file_path, timeout)
        result_queue.put(result)
    except Exception as e:
        result_queue.put({
            'group': problem_args[0],
            'size': problem_args[1],
            'file': os.path.relpath(problem_args[2], KPLIB_FOLDER) if len(problem_args) > 2 else "unknown",
            'value': 0,
            'weight': 0,
            'optimal': False,
            'time': 0,
            'status': f'process error: {str(e)}'
        })


def run_all_tests():
    """Run knapsack solver on all test cases with enforced timeouts."""
    print("Starting knapsack tests...")
    
    # Create CSV file and write header
    with open(RESULT_FILE, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Group', 'Size', 'File', 'Value', 'Weight', 'Optimal', 'Time(s)', 'Status'])
    
    # Process all test cases
    all_test_cases = get_test_cases()
    total_cases = sum(len(cases) for _, cases in all_test_cases)
    completed = 0
    
    for group, test_files in all_test_cases:
        print(f"\nProcessing group: {group}")
        
        for size, file_path in test_files:
            # Update progress counter
            completed += 1
            print(f"\nPROGRESS: [{completed}/{total_cases}]")
            
            # Create a queue for the result
            result_queue = multiprocessing.Queue()
            
            # Create and start the process
            process = multiprocessing.Process(
                target=run_problem_with_watchdog,
                args=((group, size, file_path, TIME_LIMIT), result_queue)
            )
            
            # Set process as daemon
            process.daemon = True
            
            # Start the process
            process.start()
            
            # Wait for process with timeout plus a small buffer
            process.join(TIME_LIMIT + 15)
            
            # Check if process is still running
            if process.is_alive():
                print(f"\nFORCED TERMINATION: Process exceeded time limit for {group}/{size}")
                
                # Terminate the process
                process.terminate()
                try:
                    process.join(5)  # Wait a bit for clean termination
                except:
                    pass
                
                # If still alive, use more force
                if process.is_alive():
                    print("Process still alive, using force kill...")
                    if hasattr(os, 'kill'):
                        try:
                            os.kill(process.pid, 9)  # SIGKILL
                        except:
                            pass
                    else:
                        # On Windows
                        try:
                            import subprocess
                            subprocess.call(['taskkill', '/F', '/T', '/PID', str(process.pid)])
                        except:
                            pass
                
                # Create timeout result
                result = {
                    'group': group,
                    'size': size,
                    'file': os.path.relpath(file_path, KPLIB_FOLDER),
                    'value': 0,
                    'weight': 0,
                    'optimal': False,
                    'time': TIME_LIMIT,
                    'status': 'timeout (forced termination)'
                }
            else:
                # Process completed, get the result from the queue
                try:
                    result = result_queue.get(block=False)
                except:
                    # No result in queue, create an error result
                    result = {
                        'group': group,
                        'size': size,
                        'file': os.path.relpath(file_path, KPLIB_FOLDER),
                        'value': 0,
                        'weight': 0,
                        'optimal': False,
                        'time': 0,
                        'status': 'error: Process completed but no result returned'
                    }
            
            # Print result summary
            print("\n=== RESULT SUMMARY ===")
            print(f"Problem: {group}/{size}")
            print(f"Value: {result['value']}")
            print(f"Weight: {result['weight']}")
            print(f"Optimal: {result['optimal']}")
            print(f"Status: {result['status']}")
            print(f"Time: {result['time']:.2f} seconds")
            print("=====================\n")
            
            # Write result to CSV
            with open(RESULT_FILE, 'a', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([
                    result['group'],
                    result['size'],
                    result['file'],
                    result['value'],
                    result['weight'],
                    result['optimal'],
                    f"{result['time']:.2f}",
                    result['status']
                ])
    
    print(f"\nCompleted {completed}/{total_cases} test cases. Results saved to {RESULT_FILE}")


if __name__ == '__main__':
    try:
        # Record total execution time
        program_start = time.time()
        
        # Run all tests
        run_all_tests()
        
        # Print total time
        program_end = time.time()
        print(f"Total runtime: {program_end - program_start:.2f} seconds")
        
        # Keep console window open
        input("\nPress Enter to exit...")
        
    except KeyboardInterrupt:
        print("\nProgram terminated by user.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")
    finally:
        print("Exiting program.")