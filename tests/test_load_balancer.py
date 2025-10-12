import pytest
import asyncio
from unittest.mock import Mock, patch
from load_balancer.core import LoadBalancer


class TestLoadBalancer:
    """Test LoadBalancer core functionality"""
    
    @pytest.fixture
    def sample_config(self):
        """Sample configuration for testing"""
        return {
            'load_balancer': {
                'port': 8080,
                'default_algorithm': 'round_robin'
            },
            'health_check': {
                'interval': 5,
                'timeout': 2,
                'fail_threshold': 3
            }
        }
        
    @pytest.fixture
    def sample_servers(self):
        """Sample server configuration"""
        return [
            {'id': 1, 'port': 9001},
            {'id': 2, 'port': 9002}
        ]
        
    def test_load_balancer_initialization(self, sample_servers, sample_config):
        """Test LoadBalancer initialization"""
        lb = LoadBalancer(8080, sample_servers, sample_config)
        
        assert lb.port == 8080
        assert lb.backend_servers == sample_servers
        assert not lb.running
        assert len(lb.server_states) == 2
        
        for server in sample_servers:
            server_id = server['id']
            assert server_id in lb.server_states
            state = lb.server_states[server_id]
            assert state['active_connections'] == 0
            assert state['total_handled'] == 0
            assert state['status'] == 'UP'
            
    @pytest.mark.asyncio
    async def test_update_metrics(self, sample_servers, sample_config):
        """Test metrics updating"""
        lb = LoadBalancer(8080, sample_servers, sample_config)
        
        await lb.update_metrics(1, 50.0, True)
        
        state = lb.server_states[1]
        assert state['total_handled'] == 1
        assert state['avg_latency'] == 50.0
        
        await lb.update_metrics(1, 100.0, True)
        
        state = lb.server_states[1]
        assert state['total_handled'] == 2
        assert state['avg_latency'] == 55.0  # EMA: 0.9 * 50.0 + 0.1 * 100.0
        
    def test_set_algorithm(self, sample_servers, sample_config):
        """Test algorithm switching"""
        lb = LoadBalancer(8080, sample_servers, sample_config)
        
        assert lb.algorithm.__class__.__name__ == 'RoundRobinAlgorithm'
        
        lb.set_algorithm('least_connections')
        assert lb.algorithm.__class__.__name__ == 'LeastConnectionsAlgorithm'
        
        lb.set_algorithm('ip_hash')
        assert lb.algorithm.__class__.__name__ == 'IPHashAlgorithm'