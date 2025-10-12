import hashlib
from typing import Dict, List, Optional


class LoadBalancingAlgorithm:
    """Base class for load balancing algorithms"""
    
    def select_server(self, servers: List[Dict], client_ip: str, server_states: Dict) -> Optional[Dict]:
        raise NotImplementedError


class RoundRobinAlgorithm(LoadBalancingAlgorithm):
    """Round Robin load balancing algorithm"""
    
    def __init__(self):
        self.current = 0
        
    def select_server(self, servers: List[Dict], client_ip: str, server_states: Dict) -> Optional[Dict]:
        if not servers:
            return None
            
        server = servers[self.current % len(servers)]
        self.current += 1
        return server


class LeastConnectionsAlgorithm(LoadBalancingAlgorithm):
    """Least Connections load balancing algorithm"""
    
    def select_server(self, servers: List[Dict], client_ip: str, server_states: Dict) -> Optional[Dict]:
        if not servers:
            return None
            
        # Find server with least active connections
        min_connections = float('inf')
        selected_server = None
        
        for server in servers:
            connections = server_states[server['id']]['active_connections']
            if connections < min_connections:
                min_connections = connections
                selected_server = server
                
        return selected_server


class IPHashAlgorithm(LoadBalancingAlgorithm):
    """IP Hash (sticky sessions) load balancing algorithm"""
    
    def select_server(self, servers: List[Dict], client_ip: str, server_states: Dict) -> Optional[Dict]:
        if not servers:
            return None
            
        # Create hash of client IP
        hash_value = hashlib.md5(client_ip.encode()).hexdigest()
        index = int(hash_value, 16) % len(servers)
        
        selected_server = servers[index]
        
        # If selected server is down, fall back to round robin
        if server_states[selected_server['id']]['status'] != 'UP':
            # Find first healthy server
            for server in servers:
                if server_states[server['id']]['status'] == 'UP':
                    return server
                    
        return selected_server


class AlgorithmFactory:
    """Factory for creating load balancing algorithms"""
    
    _algorithms = {
        'round_robin': RoundRobinAlgorithm,
        'least_connections': LeastConnectionsAlgorithm,
        'ip_hash': IPHashAlgorithm
    }
    
    @classmethod
    def create(cls, algorithm_name: str) -> LoadBalancingAlgorithm:
        if algorithm_name not in cls._algorithms:
            raise ValueError(f"Unknown algorithm: {algorithm_name}")
        return cls._algorithms[algorithm_name]()
        
    @classmethod
    def get_available_algorithms(cls) -> List[str]:
        return list(cls._algorithms.keys())