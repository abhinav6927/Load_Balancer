import asyncio
import json
import logging
from typing import List, Dict, Any
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class WebSocketHandler:
    """Handles WebSocket connections and broadcasting"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        
    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total connections: {len(self.active_connections)}")
        
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            await self.disconnect(websocket)
            
    async def disconnect(self, websocket: WebSocket):
        """Handle WebSocket disconnection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Total connections: {len(self.active_connections)}")
            
    async def broadcast(self, data: Dict[str, Any]):
        """Broadcast data to all connected clients"""
        if not self.active_connections:
            return
            
        message = json.dumps(data)
        disconnected = []
        
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                disconnected.append(connection)
                
        for connection in disconnected:
            await self.disconnect(connection)
            
    async def close_all(self):
        """Close all WebSocket connections"""
        for connection in self.active_connections:
            try:
                await connection.close()
            except:
                pass
        self.active_connections.clear()
