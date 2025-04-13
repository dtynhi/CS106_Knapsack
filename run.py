import os
import csv
import time
import multiprocessing
from knapsack_solver import read_kplib_file, solver_knapsack

RESULT_FILE = 'results.csv'
KPLIB_FOLDER = 'kplib'
NUM_OF_TC = 5
TIME_LIMIT = 180

if __name__ == '__main__':
    multiprocessing.freeze_support()
    try:
        multiprocessing.set_start_method('spawn')
    except RuntimeError:
        pass

def get_test_cases():
    """Get test cases from kplib folder."""
    test_cases = []
    
    try:
        problem_groups = [f for f in os.listdir(KPLIB_FOLDER) 
                         if os.path.isdir(os.path.join(KPLIB_FOLDER, f))]
        
        for group in problem_groups:
            group_test_cases = []
            group_path = os.path.join(KPLIB_FOLDER, group)
            
            size_folders = [f for f in os.listdir(group_path)
                           if os.path.isdir(os.path.join(group_path, f)) and f.startswith('n')]
            
            size_folders.sort(key=lambda x: int(x[1:]) if x[1:].isdigit() else 0)
            for size_folder in size_folders[:NUM_OF_TC]:
                size_path = os.path.join(group_path, size_folder)
                
                type_folders = [f for f in os.listdir(size_path)
                               if os.path.isdir(os.path.join(size_path, f))]
                
                if not type_folders:
                    continue
                    
                type_path = os.path.join(size_path, type_folders[0])
                kp_files = [f for f in os.listdir(type_path) if f.endswith('.kp')]
                if not kp_files:
                    continue
                    
                kp_file_path = os.path.join(type_path, kp_files[0])
                group_test_cases.append((size_folder, kp_file_path))
            
            if group_test_cases:
                test_cases.append((group, group_test_cases))
                
    except Exception:
        pass
    
    return test_cases

def solve_problem_with_timeout(group_name, size_name, file_path, timeout):
    """Solve a single knapsack problem with timeout."""
    try:
        start_time = time.time()
        values, weights, capacity = read_kplib_file(file_path)
        result = solver_knapsack(values, weights, capacity, timeout)
        
        end_time = time.time()
        solve_time = end_time - start_time
        
        if end_time > start_time + timeout + 10:
            result['optimal'] = False
        
        print(f"Group: {group_name}, Size: {size_name}, "
              f"Value: {result['value']}, Weight: {result['weight']}, "
              f"Optimal: {result['optimal']}, Time: {solve_time:.2f}s")
        
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
        print(f"Group: {group_name}, Size: {size_name}, "
              f"Value: 0, Weight: 0, Optimal: False, Time: 0.00s")
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
    """Run knapsack problem in a separate process."""
    try:
        group, size, file_path, timeout = problem_args
        result = solve_problem_with_timeout(group, size, file_path, timeout)
        result_queue.put(result)
    except Exception as e:
        result_queue.put({
            'group': problem_args[0],
            'size': problem_args[1],
            'file': os.path.relpath(problem_args[2], KPLIB_FOLDER),
            'value': 0,
            'weight': 0,
            'optimal': False,
            'time': 0,
            'status': f'process error: {str(e)}'
        })

def run_all_tests():
    """Run knapsack solver on all test cases."""
    with open(RESULT_FILE, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Group', 'Size', 'File', 'Value', 'Weight', 'Optimal', 'Time(s)', 'Status'])
    
    all_test_cases = get_test_cases()
    
    for group, test_files in all_test_cases:
        for size, file_path in test_files:
            result_queue = multiprocessing.Queue()
            process = multiprocessing.Process(
                target=run_problem_with_watchdog,
                args=((group, size, file_path, TIME_LIMIT), result_queue)
            )
            
            process.daemon = True
            process.start()
            process.join(TIME_LIMIT + 15)
            
            if process.is_alive():
                process.terminate()
                process.join(5)
                
                if process.is_alive() and hasattr(os, 'kill'):
                    try:
                        os.kill(process.pid, 9)
                    except:
                        pass
                
                result = {
                    'group': group,
                    'size': size,
                    'file': os.path.relpath(file_path, KPLIB_FOLDER),
                    'value': 0,
                    'weight': 0,
                    'optimal': False,
                    'time': TIME_LIMIT,
                    'status': 'timeout'
                }
                print(f"Group: {group}, Size: {size}, "
                      f"Value: 0, Weight: 0, Optimal: False, Time: {TIME_LIMIT:.2f}s")
            else:
                try:
                    result = result_queue.get(block=False)
                except:
                    result = {
                        'group': group,
                        'size': size,
                        'file': os.path.relpath(file_path, KPLIB_FOLDER),
                        'value': 0,
                        'weight': 0,
                        'optimal': False,
                        'time': 0,
                        'status': 'error: no result'
                    }
                    print(f"Group: {group}, Size: {size}, "
                          f"Value: 0, Weight: 0, Optimal: False, Time: 0.00s")
            
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

if __name__ == '__main__':
    try:
        run_all_tests()
    except KeyboardInterrupt:
        pass
    except Exception:
        pass