import asyncio
import time
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
import logging

logger = logging.getLogger(__name__)


class BackendServer:
    """FastAPI backend server instance"""
    
    def __init__(self, server_id: int, port: int):
        self.server_id = server_id
        self.port = port
        self.start_time = time.time()
        self.request_count = 0
        self.healthy = True
        self.simulated_latency = 0.0  # seconds
        
        self.app = FastAPI(title=f"Backend Server {server_id}")
        self.setup_routes()
        
    def setup_routes(self):
        """Setup FastAPI routes"""
        
        @self.app.get("/")
        async def root():
            if self.simulated_latency > 0:
                await asyncio.sleep(self.simulated_latency)
                
            self.request_count += 1
            uptime = int(time.time() - self.start_time)
            
            return {
                "message": f"Hello from Server {self.server_id}",
                "server_id": self.server_id,
                "uptime": uptime,
                "total_handled": self.request_count
            }
            
        @self.app.get("/health")
        async def health():
            if not self.healthy:
                raise HTTPException(status_code=503, detail="Server unhealthy")
            return {"status": "ok"}
            
        @self.app.post("/control/fail")
        async def simulate_failure():
            self.healthy = False
            return {"status": "Server marked as unhealthy"}
            
        @self.app.post("/control/recover")
        async def recover():
            self.healthy = True
            return {"status": "Server marked as healthy"}
            
        @self.app.post("/control/latency/{latency}")
        async def set_latency(latency: float):
            self.simulated_latency = max(0, min(latency, 10))  # Cap at 10 seconds
            return {"status": f"Latency set to {self.simulated_latency}s"}
            
        @self.app.get("/stats")
        async def stats():
            return {
                "server_id": self.server_id,
                "port": self.port,
                "uptime": int(time.time() - self.start_time),
                "total_handled": self.request_count,
                "healthy": self.healthy,
                "simulated_latency": self.simulated_latency
            }
            
    def run(self):
        """Run the server"""
        uvicorn.run(
            self.app,
            host="localhost",
            port=self.port,
            log_level="info"
        )


def create_server(server_id: int, port: int) -> BackendServer:
    """Factory function to create a backend server"""
    return BackendServer(server_id, port)


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Usage: python backend_server.py <server_id> <port>")
        sys.exit(1)
        
    server_id = int(sys.argv[1])
    port = int(sys.argv[2])
    
    server = create_server(server_id, port)
    server.run()