"""
Performance monitoring utilities for YouTube automation.
Tracks execution times, resource usage, and system performance.
"""

import time
import psutil
import os
from typing import Dict, List, Optional
from datetime import datetime
import json

class PerformanceMonitor:
    """Monitor system performance and execution times."""
    
    def __init__(self):
        self.start_time = time.time()
        self.metrics = {
            'execution_times': {},
            'resource_usage': {},
            'system_info': self._get_system_info()
        }
    
    def _get_system_info(self) -> Dict:
        """Get system information."""
        try:
            return {
                'cpu_count': psutil.cpu_count(),
                'memory_total': psutil.virtual_memory().total,
                'disk_total': psutil.disk_usage('/').total if os.name != 'nt' else psutil.disk_usage('C:').total,
                'python_version': os.sys.version,
                'platform': os.name
            }
        except Exception:
            return {}
    
    def start_timer(self, operation: str) -> str:
        """Start timing an operation."""
        timer_id = f"{operation}_{int(time.time() * 1000)}"
        self.metrics['execution_times'][timer_id] = {
            'operation': operation,
            'start_time': time.time(),
            'end_time': None,
            'duration': None
        }
        return timer_id
    
    def end_timer(self, timer_id: str) -> float:
        """End timing an operation and return duration."""
        if timer_id in self.metrics['execution_times']:
            end_time = time.time()
            self.metrics['execution_times'][timer_id]['end_time'] = end_time
            duration = end_time - self.metrics['execution_times'][timer_id]['start_time']
            self.metrics['execution_times'][timer_id]['duration'] = duration
            return duration
        return 0.0
    
    def get_resource_usage(self) -> Dict:
        """Get current resource usage."""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/') if os.name != 'nt' else psutil.disk_usage('C:')
            
            return {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_used': memory.used,
                'memory_available': memory.available,
                'disk_percent': disk.percent,
                'disk_used': disk.used,
                'disk_free': disk.free,
                'timestamp': datetime.now().isoformat()
            }
        except Exception:
            return {}
    
    def log_performance(self, operation: str, duration: float, success: bool = True):
        """Log performance metrics."""
        self.metrics['resource_usage'][f"{operation}_{int(time.time())}"] = {
            'operation': operation,
            'duration': duration,
            'success': success,
            'resource_usage': self.get_resource_usage(),
            'timestamp': datetime.now().isoformat()
        }
    
    def get_summary(self) -> Dict:
        """Get performance summary."""
        total_time = time.time() - self.start_time
        
        # Calculate average execution times
        avg_times = {}
        for timer_id, data in self.metrics['execution_times'].items():
            if data['duration'] is not None:
                operation = data['operation']
                if operation not in avg_times:
                    avg_times[operation] = []
                avg_times[operation].append(data['duration'])
        
        # Calculate averages
        for operation in avg_times:
            avg_times[operation] = sum(avg_times[operation]) / len(avg_times[operation])
        
        return {
            'total_execution_time': total_time,
            'average_execution_times': avg_times,
            'total_operations': len(self.metrics['execution_times']),
            'system_info': self.metrics['system_info'],
            'current_resource_usage': self.get_resource_usage()
        }
    
    def save_metrics(self, filepath: str):
        """Save metrics to file."""
        try:
            with open(filepath, 'w') as f:
                json.dump(self.metrics, f, indent=2, default=str)
        except Exception as e:
            print(f"Failed to save metrics: {e}")

# Global performance monitor instance
performance_monitor = PerformanceMonitor()

def track_performance(operation: str):
    """Decorator to track function performance."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            timer_id = performance_monitor.start_timer(operation)
            try:
                result = func(*args, **kwargs)
                duration = performance_monitor.end_timer(timer_id)
                performance_monitor.log_performance(operation, duration, success=True)
                return result
            except Exception as e:
                duration = performance_monitor.end_timer(timer_id)
                performance_monitor.log_performance(operation, duration, success=False)
                raise e
        return wrapper
    return decorator
