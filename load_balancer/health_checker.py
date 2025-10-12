import asyncio
import aiohttp
import logging
from typing import Dict, List, Callable, Optional

logger = logging.getLogger(__name__)


class HealthChecker:
    """Async health checker for backend servers"""
    
    def __init__(self, servers: List[Dict], config: Dict):
        self.servers = servers
        self.interval = config['interval']
        self.timeout = config['timeout']
        self.fail_threshold = config['fail_threshold']
        
        self.running = False
        self.server_failures = {server['id']: 0 for server in servers}
        self.health_callback: Optional[Callable] = None
        
    async def start(self, health_callback: Callable):
        """Start health checking"""
        self.health_callback = health_callback
        self.running = True
        asyncio.create_task(self._health_check_loop())
        
    async def stop(self):
        """Stop health checking"""
        self.running = False
        
    async def _health_check_loop(self):
        """Main health checking loop"""
        while self.running:
            try:
                await self._check_all_servers()
                await asyncio.sleep(self.interval)
            except Exception as e:
                logger.error(f"Health check loop error: {e}")
                await asyncio.sleep(1)  # Brief pause before retry
                
    async def _check_all_servers(self):
        """Check health of all servers"""
        tasks = [self._check_server(server) for server in self.servers]
        await asyncio.gather(*tasks, return_exceptions=True)
        
    async def _check_server(self, server: Dict):
        """Check health of a single server"""
        server_id = server['id']
        port = server['port']
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.get(f"http://localhost:{port}/health") as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('status') == 'ok':
                            # Server is healthy
                            if self.server_failures[server_id] > 0:
                                self.server_failures[server_id] = 0
                                await self.health_callback(server_id, 'UP')
                                logger.info(f"Server {server_id} recovered")
                            return
                            
        except Exception as e:
            logger.debug(f"Health check failed for server {server_id}: {e}")
            
        # Health check failed
        self.server_failures[server_id] += 1
        
        if self.server_failures[server_id] >= self.fail_threshold:
            await self.health_callback(server_id, 'DOWN')
            logger.warning(f"Server {server_id} marked as DOWN after {self.server_failures[server_id]} failures")

