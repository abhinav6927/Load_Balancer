import asyncio
import json
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from utils.process_manager import ProcessManager
from utils.load_generator import LoadGenerator
from load_balancer.core import LoadBalancer
from .websocket_handler import WebSocketHandler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load configuration
config_path = Path(__file__).parent.parent / "config.json"
with open(config_path, 'r') as f:
    CONFIG = json.load(f)

app = FastAPI(title="Load Balancer GUI Backend")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
process_manager = ProcessManager()
load_generator = LoadGenerator()
load_balancer: Optional[LoadBalancer] = None
websocket_handler = WebSocketHandler()
backend_processes: Dict[int, subprocess.Popen] = {}

@app.on_event("startup")
async def startup_event():
    """Initialize the application"""
    logger.info("Starting GUI backend...")
    asyncio.create_task(broadcast_metrics())

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown"""
    logger.info("Shutting down GUI backend...")
    if load_balancer:
        await load_balancer.stop()
    for process in backend_processes.values():
        if process.poll() is None:
            process.terminate()
    await websocket_handler.close_all()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await websocket_handler.connect(websocket)

@app.post("/api/servers/start")
async def start_servers():
    """Start all backend servers"""
    global backend_processes
    try:
        await stop_servers()
        for server_config in CONFIG['backend_servers']:
            server_id = server_config['id']
            port = server_config['port']
            
            if process_manager.is_port_in_use(port):
                conflict_info = process_manager.get_port_info(port)
                return {
                    "success": False,
                    "error": f"Port {port} is in use",
                    "conflict": conflict_info
                }
            
            cmd = [
                sys.executable, "-m", "servers.backend_server",
                str(server_id), str(port)
            ]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=Path(__file__).parent.parent
            )
            
            backend_processes[server_id] = process
            logger.info(f"Started backend server {server_id} on port {port}")
            
        await asyncio.sleep(2)
        return {"success": True, "message": "All servers started"}
        
    except Exception as e:
        logger.error(f"Error starting servers: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/servers/stop")
async def stop_servers():
    """Stop all backend servers"""
    global backend_processes
    try:
        for server_id, process in backend_processes.items():
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                logger.info(f"Stopped backend server {server_id}")
        backend_processes.clear()
        return {"success": True, "message": "All servers stopped"}
    except Exception as e:
        logger.error(f"Error stopping servers: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/load-balancer/start")
async def start_load_balancer():
    """Start the load balancer"""
    global load_balancer
    try:
        if load_balancer and load_balancer.running:
            return {"success": False, "error": "Load balancer is already running"}
            
        port = CONFIG['load_balancer']['port']
        if process_manager.is_port_in_use(port):
            conflict_info = process_manager.get_port_info(port)
            return {
                "success": False,
                "error": f"Port {port} is in use",
                "conflict": conflict_info
            }
            
        load_balancer = LoadBalancer(
            port=port,
            backend_servers=CONFIG['backend_servers'],
            config=CONFIG
        )
        
        asyncio.create_task(load_balancer.start())
        await asyncio.sleep(1)
        return {"success": True, "message": f"Load balancer started on port {port}"}
    except Exception as e:
        logger.error(f"Error starting load balancer: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/load-balancer/stop")
async def stop_load_balancer():
    """Stop the load balancer"""
    global load_balancer
    try:
        if load_balancer:
            await load_balancer.stop()
            load_balancer = None
        return {"success": True, "message": "Load balancer stopped"}
    except Exception as e:
        logger.error(f"Error stopping load balancer: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/load-balancer/algorithm/{algorithm}")
async def set_algorithm(algorithm: str):
    """Change load balancing algorithm"""
    try:
        if not load_balancer:
            return {"success": False, "error": "Load balancer not running"}
        available_algorithms = CONFIG['load_balancer']['algorithms']
        if algorithm not in available_algorithms:
            return {"success": False, "error": f"Invalid algorithm. Available: {available_algorithms}"}
        load_balancer.set_algorithm(algorithm)
        return {"success": True, "message": f"Algorithm changed to {algorithm}"}
    except Exception as e:
        logger.error(f"Error setting algorithm: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/load-test/start")
async def start_load_test(test_config: dict):
    """Start internal load test"""
    try:
        requests = test_config.get('requests', CONFIG['load_test']['default_requests'])
        concurrency = test_config.get('concurrency', CONFIG['load_test']['default_concurrency'])
        rps = test_config.get('rps', CONFIG['load_test']['default_rps'])
        
        if not load_balancer or not load_balancer.running:
            return {"success": False, "error": "Load balancer not running"}
            
        asyncio.create_task(load_generator.start_test(
            target_url=f"http://localhost:{CONFIG['load_balancer']['port']}/",
            requests=requests,
            concurrency=concurrency,
            rps=rps
        ))
        
        return {
            "success": True, 
            "message": f"Load test started: {requests} requests, {concurrency} concurrent, {rps} RPS"
        }
    except Exception as e:
        logger.error(f"Error starting load test: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/server/{server_id}/fail")
async def simulate_server_failure(server_id: int):
    """Simulate server failure"""
    try:
        server_config = next(
            (s for s in CONFIG['backend_servers'] if s['id'] == server_id), 
            None
        )
        if not server_config:
            return {"success": False, "error": f"Server {server_id} not found"}
            
        port = server_config['port']
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(f"http://localhost:{port}/control/fail") as response:
                if response.status == 200:
                    return {"success": True, "message": f"Server {server_id} marked as failed"}
        return {"success": False, "error": "Failed to communicate with server"}
    except Exception as e:
        logger.error(f"Error simulating failure for server {server_id}: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/server/{server_id}/recover")
async def recover_server(server_id: int):
    """Recover server from failure"""
    try:
        server_config = next(
            (s for s in CONFIG['backend_servers'] if s['id'] == server_id), 
            None
        )
        if not server_config:
            return {"success": False, "error": f"Server {server_id} not found"}
            
        port = server_config['port']
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(f"http://localhost:{port}/control/recover") as response:
                if response.status == 200:
                    return {"success": True, "message": f"Server {server_id} recovered"}
        return {"success": False, "error": "Failed to communicate with server"}
    except Exception as e:
        logger.error(f"Error recovering server {server_id}: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/server/{server_id}/latency/{latency}")
async def set_server_latency(server_id: int, latency: float):
    """Add simulated latency to server"""
    try:
        server_config = next(
            (s for s in CONFIG['backend_servers'] if s['id'] == server_id), 
            None
        )
        if not server_config:
            return {"success": False, "error": f"Server {server_id} not found"}
            
        port = server_config['port']
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(f"http://localhost:{port}/control/latency/{latency}") as response:
                if response.status == 200:
                    return {"success": True, "message": f"Server {server_id} latency set to {latency}s"}
        return {"success": False, "error": "Failed to communicate with server"}
    except Exception as e:
        logger.error(f"Error setting latency for server {server_id}: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/port/kill/{port}")
async def kill_port_process(port: int):
    """Kill process using specified port"""
    try:
        if not process_manager.is_port_in_use(port):
            return {"success": False, "error": f"Port {port} is not in use"}
        result = process_manager.kill_process_on_port(port)
        if result:
            return {"success": True, "message": f"Killed process on port {port}"}
        else:
            return {"success": False, "error": f"Failed to kill process on port {port}"}
    except Exception as e:
        logger.error(f"Error killing process on port {port}: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/port/{port}/info")
async def get_port_info(port: int):
    """Get information about process using port"""
    try:
        if not process_manager.is_port_in_use(port):
            return {"in_use": False}
        info = process_manager.get_port_info(port)
        return {"in_use": True, "info": info}
    except Exception as e:
        logger.error(f"Error getting port info for {port}: {e}")
        return {"in_use": False, "error": str(e)}

@app.get("/api/status")
async def get_status():
    """Get overall system status"""
    try:
        server_status = {}
        for server_config in CONFIG['backend_servers']:
            server_id = server_config['id']
            port = server_config['port']
            server_status[server_id] = {
                "port": port,
                "process_running": server_id in backend_processes and backend_processes[server_id].poll() is None,
                "port_in_use": process_manager.is_port_in_use(port)
            }
        
        lb_status = {
            "running": load_balancer is not None and load_balancer.running,
            "port": CONFIG['load_balancer']['port'],
            "port_in_use": process_manager.is_port_in_use(CONFIG['load_balancer']['port'])
        }
        
        return {
            "servers": server_status,
            "load_balancer": lb_status,
            "available_algorithms": CONFIG['load_balancer']['algorithms']
        }
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return {"error": str(e)}

async def broadcast_metrics():
    """Broadcast metrics to connected WebSocket clients"""
    while True:
        try:
            if load_balancer and load_balancer.running:
                stats = load_balancer.get_stats()
                stats['timestamp'] = int(time.time())
                stats['rps'] = load_balancer.metrics.get_request_rate()
                await websocket_handler.broadcast(stats)
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Error broadcasting metrics: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    uvicorn.run(
        "gui_backend.main:app",
        host="localhost",
        port=CONFIG['gui']['port'],
        reload=False,
        log_level="info"
    )