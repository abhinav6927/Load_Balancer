import asyncio
import json
import logging
import socket
import time
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

from .algorithms import AlgorithmFactory
from .health_checker import HealthChecker
from .metrics import MetricsCollector

logger = logging.getLogger(__name__)

class LoadBalancer:
    def __init__(self, port: int, backend_servers: List[Dict], config: Dict):
        self.port = port
        self.backend_servers = backend_servers
        self.config = config
        self.running = False
        self.server_socket = None
        
        self.algorithm = AlgorithmFactory.create(config['load_balancer']['default_algorithm'])
        self.health_checker = HealthChecker(backend_servers, config['health_check'])
        self.metrics = MetricsCollector()
        
        self.server_states = {
            server['id']: {
                'active_connections': 0,
                'total_handled': 0,
                'avg_latency': 0.0,
                'status': 'UP',
                'port': server['port']
            }
            for server in backend_servers
        }
        
        self.request_lock = asyncio.Lock()
        
    async def start(self):
        if self.running:
            return
            
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('localhost', self.port))
        self.server_socket.listen(100)
        self.server_socket.setblocking(False)
        
        self.running = True
        logger.info(f"Load balancer started on port {self.port}")
        
        asyncio.create_task(self.health_checker.start(self._on_health_change))
        
        while self.running:
            try:
                client_socket, addr = await asyncio.get_event_loop().sock_accept(self.server_socket)
                asyncio.create_task(self.handle_client(client_socket, addr))
            except Exception as e:
                if self.running:
                    logger.error(f"Error accepting connection: {e}")
                    
    async def stop(self):
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        await self.health_checker.stop()
        logger.info("Load balancer stopped")
        
    async def handle_client(self, client_socket, client_addr):
        try:
            request_data = await asyncio.get_event_loop().sock_recv(client_socket, 4096)
            if not request_data:
                return
                
            request_str = request_data.decode('utf-8', errors='ignore')
            
            lines = request_str.split('\r\n')
            if not lines:
                return
                
            request_line = lines[0]
            method, path, version = request_line.split(' ', 2) if len(request_line.split(' ')) >= 3 else ('GET', '/', 'HTTP/1.1')
            
            headers = {}
            for line in lines[1:]:
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key.strip().lower()] = value.strip()
                    
            backend_server = await self.select_backend(client_addr[0], method, path)
            if not backend_server:
                await self.send_error_response(client_socket, 503, "Service Unavailable")
                return
                
            start_time = time.time()
            response = await self.forward_request(backend_server, request_data)
            latency = (time.time() - start_time) * 1000
            
            if response:
                await asyncio.get_event_loop().sock_sendall(client_socket, response)
                await self.update_metrics(backend_server['id'], latency, success=True)
            else:
                await self.send_error_response(client_socket, 502, "Bad Gateway")
                await self.update_metrics(backend_server['id'], latency, success=False)
                
        except Exception as e:
            logger.error(f"Error handling client {client_addr}: {e}")
        finally:
            client_socket.close()
            
    async def select_backend(self, client_ip: str, method: str, path: str) -> Optional[Dict]:
        healthy_servers = [
            server for server in self.backend_servers
            if self.server_states[server['id']]['status'] == 'UP'
        ]
        
        if not healthy_servers:
            return None
            
        selected = self.algorithm.select_server(
            healthy_servers, 
            client_ip, 
            self.server_states
        )
        
        if selected:
            async with self.request_lock:
                self.server_states[selected['id']]['active_connections'] += 1
                
        return selected
        
    async def forward_request(self, backend_server: Dict, request_data: bytes) -> Optional[bytes]:
        try:
            backend_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            backend_socket.setblocking(False)
            try:
                await asyncio.wait_for(
                    asyncio.get_event_loop().sock_connect(
                        backend_socket, ('localhost', backend_server['port'])
                    ),
                    timeout=1.0
                )
            except asyncio.TimeoutError:
                logger.error(f"Connection timeout to backend {backend_server['port']}")
                backend_socket.close()
                return None

            try:
                await asyncio.wait_for(
                    asyncio.get_event_loop().sock_sendall(backend_socket, request_data),
                    timeout=1.0
                )
            except asyncio.TimeoutError:
                logger.error(f"Send timeout to backend {backend_server['port']}")
                backend_socket.close()
                return None

            response_data = b""
            try:
                chunk = await asyncio.wait_for(
                    asyncio.get_event_loop().sock_recv(backend_socket, 4096),
                    timeout=2.0
                )

                if not chunk:
                    backend_socket.close()
                    return None

                response_data += chunk

                if b'\r\n\r\n' in response_data:
                    headers_end = response_data.find(b'\r\n\r\n') + 4
                    headers = response_data[:headers_end].decode('utf-8', errors='ignore').lower()

                    content_length = None
                    for line in headers.split('\r\n'):
                        if line.startswith('content-length:'):
                            try:
                                content_length = int(line.split(':')[1].strip())
                                break
                            except (ValueError, IndexError):
                                pass

                    if content_length is not None:
                        body_received = len(response_data) - headers_end
                        while body_received < content_length:
                            try:
                                chunk = await asyncio.wait_for(
                                    asyncio.get_event_loop().sock_recv(backend_socket, 4096),
                                    timeout=1.0
                                )
                                if not chunk:
                                    break
                                response_data += chunk
                                body_received = len(response_data) - headers_end
                            except asyncio.TimeoutError:
                                logger.warning(f"Body read timeout from backend {backend_server['port']}")
                                break

                backend_socket.close()
                return response_data

            except asyncio.TimeoutError:
                logger.error(f"Response timeout from backend {backend_server['port']}")
                backend_socket.close()
                return None

        except Exception as e:
            logger.error(f"Error forwarding to backend {backend_server['port']}: {e}")
            if 'backend_socket' in locals():
                backend_socket.close()
            return None
        finally:
            async with self.request_lock:
                if backend_server['id'] in self.server_states:
                    self.server_states[backend_server['id']]['active_connections'] = max(
                        0, self.server_states[backend_server['id']]['active_connections'] - 1
                    )
                    
    async def send_error_response(self, client_socket, status_code: int, message: str):
        response = f"HTTP/1.1 {status_code} {message}\r\n"
        response += "Content-Type: application/json\r\n"
        response += f"Content-Length: {len(message) + 20}\r\n\r\n"
        response += f'{{"error": "{message}"}}'
        
        try:
            await asyncio.get_event_loop().sock_sendall(client_socket, response.encode())
        except:
            pass
            
    async def update_metrics(self, server_id: int, latency: float, success: bool):
        async with self.request_lock:
            state = self.server_states[server_id]
            state['total_handled'] += 1
            
            if state['avg_latency'] == 0:
                state['avg_latency'] = latency
            else:
                state['avg_latency'] = 0.9 * state['avg_latency'] + 0.1 * latency
                
        self.metrics.record_request(server_id, latency, success)
        
    async def _on_health_change(self, server_id: int, status: str):
        async with self.request_lock:
            self.server_states[server_id]['status'] = status
        logger.info(f"Server {server_id} status changed to {status}")
        
    def set_algorithm(self, algorithm_name: str):
        self.algorithm = AlgorithmFactory.create(algorithm_name)
        logger.info(f"Algorithm changed to {algorithm_name}")
        
    def get_stats(self) -> Dict:
        total_requests = sum(state['total_handled'] for state in self.server_states.values())
        active_connections = sum(state['active_connections'] for state in self.server_states.values())
        
        return {
            'total_requests': total_requests,
            'active_connections': active_connections,
            'servers': [
                {
                    'id': server_id,
                    'port': state['port'],
                    'status': state['status'],
                    'active_connections': state['active_connections'],
                    'total_handled': state['total_handled'],
                    'avg_latency_ms': round(state['avg_latency'], 2)
                }
                for server_id, state in self.server_states.items()
            ]
        }