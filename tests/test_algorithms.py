import pytest
from load_balancer.algorithms import RoundRobinAlgorithm, LeastConnectionsAlgorithm, IPHashAlgorithm


class TestRoundRobinAlgorithm:
    """Test Round Robin algorithm"""
    
    def test_round_robin_order(self):
        """Test that Round Robin returns servers in order"""
        algorithm = RoundRobinAlgorithm()
        
        servers = [
            {'id': 1, 'port': 9001},
            {'id': 2, 'port': 9002},
            {'id': 3, 'port': 9003}
        ]
        
        server_states = {
            1: {'active_connections': 0, 'status': 'UP'},
            2: {'active_connections': 0, 'status': 'UP'},
            3: {'active_connections': 0, 'status': 'UP'}
        }
        
        expected_order = [1, 2, 3, 1, 2, 3, 1]
        results = []
        
        for _ in range(7):
            server = algorithm.select_server(servers, "127.0.0.1", server_states)
            results.append(server['id'])
            
        assert results == expected_order
        
    def test_round_robin_empty_servers(self):
        """Test Round Robin with empty server list"""
        algorithm = RoundRobinAlgorithm()
        result = algorithm.select_server([], "127.0.0.1", {})
        assert result is None


class TestLeastConnectionsAlgorithm:
    """Test Least Connections algorithm"""
    
    def test_least_connections_selection(self):
        """Test that Least Connections selects server with fewest connections"""
        algorithm = LeastConnectionsAlgorithm()
        
        servers = [
            {'id': 1, 'port': 9001},
            {'id': 2, 'port': 9002},
            {'id': 3, 'port': 9003}
        ]
        
        server_states = {
            1: {'active_connections': 5, 'status': 'UP'},
            2: {'active_connections': 2, 'status': 'UP'},
            3: {'active_connections': 8, 'status': 'UP'}
        }
        
        server = algorithm.select_server(servers, "127.0.0.1", server_states)
        assert server['id'] == 2
        
    def test_least_connections_empty_servers(self):
        """Test Least Connections with empty server list"""
        algorithm = LeastConnectionsAlgorithm()
        result = algorithm.select_server([], "127.0.0.1", {})
        assert result is None


class TestIPHashAlgorithm:
    """Test IP Hash algorithm"""
    
    def test_ip_hash_deterministic(self):
        """Test that IP Hash is deterministic for same IP"""
        algorithm = IPHashAlgorithm()
        
        servers = [
            {'id': 1, 'port': 9001},
            {'id': 2, 'port': 9002},
            {'id': 3, 'port': 9003}
        ]
        
        server_states = {
            1: {'active_connections': 0, 'status': 'UP'},
            2: {'active_connections': 0, 'status': 'UP'},
            3: {'active_connections': 0, 'status': 'UP'}
        }
        
        client_ip = "192.168.1.100"
        
        results = []
        for _ in range(5):
            server = algorithm.select_server(servers, client_ip, server_states)
            results.append(server['id'])
            
        assert len(set(results)) == 1, "IP Hash should be deterministic"
        
    def test_ip_hash_fallback_when_selected_down(self):
        """Test IP Hash fallback when selected server is DOWN"""
        algorithm = IPHashAlgorithm()
        
        servers = [
            {'id': 1, 'port': 9001},
            {'id': 2, 'port': 9002},
            {'id': 3, 'port': 9003}
        ]
        
        server_states = {
            1: {'active_connections': 0, 'status': 'UP'},
            2: {'active_connections': 0, 'status': 'DOWN'},
            3: {'active_connections': 0, 'status': 'UP'}
        }

        client_ip = "192.168.1.100"
        server = algorithm.select_server(servers, client_ip, server_states)
        
        assert server is not None
        assert server_states[server['id']]['status'] == 'UP'