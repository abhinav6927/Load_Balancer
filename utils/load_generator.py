import asyncio
import aiohttp
import time
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class LoadGenerator:
    """Async load generator for testing"""
    
    def __init__(self):
        self.running = False
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'avg_latency': 0.0,
            'start_time': None,
            'end_time': None
        }
        
    async def start_test(self, target_url: str, requests: int, concurrency: int, rps: int):
        """Start load test with proper rate limiting"""
        if self.running:
            logger.warning("Load test already running")
            return
            
        self.running = True
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'avg_latency': 0.0,
            'start_time': time.time(),
            'end_time': None
        }
        
        logger.info(f"Starting load test: {requests} requests, {concurrency} concurrent, {rps} RPS")
        
        try:
            # Create semaphore to limit concurrency
            semaphore = asyncio.Semaphore(concurrency)
            
            # Calculate time between request batches to achieve target RPS
            if rps <= concurrency:
                # If RPS is less than concurrency, launch requests with delays
                request_interval = 1.0 / rps
                tasks = []
                
                for i in range(requests):
                    # Schedule each request with appropriate delay
                    delay = i * request_interval
                    task = asyncio.create_task(
                        self._delayed_request(target_url, semaphore, delay)
                    )
                    tasks.append(task)
                    
                # Wait for all requests to complete
                latencies = await asyncio.gather(*tasks, return_exceptions=True)
                
            else:
                # If RPS is higher than concurrency, launch in batches
                batch_size = min(concurrency, requests)
                batch_interval = batch_size / rps
                
                tasks = []
                for i in range(0, requests, batch_size):
                    batch_requests = min(batch_size, requests - i)
                    
                    # Create batch of concurrent requests
                    batch_tasks = [
                        asyncio.create_task(self._make_request(target_url, semaphore))
                        for _ in range(batch_requests)
                    ]
                    tasks.extend(batch_tasks)
                    
                    # Wait between batches if not the last batch
                    if i + batch_size < requests:
                        await asyncio.sleep(batch_interval)
                
                # Wait for all requests to complete
                latencies = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Calculate statistics
            successful_latencies = [lat for lat in latencies if isinstance(lat, float)]
            self.stats['successful_requests'] = len(successful_latencies)
            self.stats['failed_requests'] = requests - len(successful_latencies)
            self.stats['total_requests'] = requests
            
            if successful_latencies:
                self.stats['avg_latency'] = sum(successful_latencies) / len(successful_latencies)
                
            self.stats['end_time'] = time.time()
            
            duration = self.stats['end_time'] - self.stats['start_time']
            actual_rps = self.stats['successful_requests'] / duration if duration > 0 else 0
            
            logger.info(f"Load test completed: {self.stats['successful_requests']}/{requests} successful, "
                       f"avg latency: {self.stats['avg_latency']:.2f}ms, actual RPS: {actual_rps:.2f}")
                       
        except Exception as e:
            logger.error(f"Load test error: {e}")
        finally:
            self.running = False
    
    async def _delayed_request(self, url: str, semaphore: asyncio.Semaphore, delay: float) -> float:
        """Make a request after a specified delay"""
        await asyncio.sleep(delay)
        return await self._make_request(url, semaphore)
            
    async def _make_request(self, url: str, semaphore: asyncio.Semaphore) -> float:
        """Make a single HTTP request"""
        async with semaphore:
            start_time = time.time()
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                    async with session.get(url) as response:
                        await response.read()  # Consume response body
                        latency = (time.time() - start_time) * 1000  # Convert to ms
                        return latency
            except Exception as e:
                logger.debug(f"Request failed: {e}")
                raise e