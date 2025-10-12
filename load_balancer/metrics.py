import time
from collections import defaultdict, deque
from typing import Dict, List


class MetricsCollector:
    """Collects and stores metrics for the load balancer"""
    
    def __init__(self, max_history: int = 300):  # 5 minutes at 1-second intervals
        self.max_history = max_history
        self.request_history = deque(maxlen=max_history)
        self.server_metrics = defaultdict(lambda: {
            'requests': deque(maxlen=max_history),
            'latencies': deque(maxlen=max_history),
            'errors': deque(maxlen=max_history)
        })
        
    def record_request(self, server_id: int, latency: float, success: bool):
        """Record a request metric"""
        timestamp = time.time()
        
        # Global metrics
        self.request_history.append({
            'timestamp': timestamp,
            'server_id': server_id,
            'latency': latency,
            'success': success
        })
        
        # Per-server metrics
        metrics = self.server_metrics[server_id]
        metrics['requests'].append(timestamp)
        metrics['latencies'].append(latency)
        if not success:
            metrics['errors'].append(timestamp)
            
    def get_request_rate(self, window_seconds: int = 60) -> float:
        """Get requests per second over the specified window"""
        cutoff_time = time.time() - window_seconds
        recent_requests = [
            req for req in self.request_history 
            if req['timestamp'] > cutoff_time
        ]
        return len(recent_requests) / window_seconds
        
    def get_server_request_counts(self, window_seconds: int = 60) -> Dict[int, int]:
        """Get request counts per server over the specified window"""
        cutoff_time = time.time() - window_seconds
        counts = defaultdict(int)
        
        for req in self.request_history:
            if req['timestamp'] > cutoff_time:
                counts[req['server_id']] += 1
                
        return dict(counts)
        
    def get_average_latency(self, server_id: int, window_seconds: int = 60) -> float:
        """Get average latency for a server over the specified window"""
        cutoff_time = time.time() - window_seconds
        metrics = self.server_metrics[server_id]
        
        recent_latencies = [
            latency for latency, timestamp in zip(metrics['latencies'], metrics['requests'])
            if timestamp > cutoff_time
        ]
        
        if not recent_latencies:
            return 0.0
            
        return sum(recent_latencies) / len(recent_latencies)
        
    def get_error_rate(self, server_id: int, window_seconds: int = 60) -> float:
        """Get error rate for a server over the specified window"""
        cutoff_time = time.time() - window_seconds
        metrics = self.server_metrics[server_id]
        
        total_requests = len([t for t in metrics['requests'] if t > cutoff_time])
        error_count = len([t for t in metrics['errors'] if t > cutoff_time])
        
        if total_requests == 0:
            return 0.0
            
        return error_count / total_requests