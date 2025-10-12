import psutil
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class ProcessManager:
    """Manages system processes and ports"""
    
    def is_port_in_use(self, port: int) -> bool:
        """Check if a port is in use"""
        try:
            for conn in psutil.net_connections():
                if conn.laddr.port == port and conn.status == psutil.CONN_LISTEN:
                    return True
            return False
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            return False
            
    def get_port_info(self, port: int) -> Optional[Dict[str, Any]]:
        """Get information about the process using a port"""
        try:
            for conn in psutil.net_connections():
                if conn.laddr.port == port and conn.status == psutil.CONN_LISTEN:
                    if conn.pid:
                        try:
                            process = psutil.Process(conn.pid)
                            return {
                                "pid": conn.pid,
                                "name": process.name(),
                                "cmdline": " ".join(process.cmdline()),
                                "username": process.username(),
                                "create_time": process.create_time()
                            }
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            return {"pid": conn.pid, "name": "Unknown", "cmdline": "Access Denied"}
            return None
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            return None
            
    def kill_process_on_port(self, port: int) -> bool:
        """Kill the process using the specified port"""
        try:
            for conn in psutil.net_connections():
                if conn.laddr.port == port and conn.status == psutil.CONN_LISTEN:
                    if conn.pid:
                        try:
                            process = psutil.Process(conn.pid)
                            process.terminate()
                            try:
                                process.wait(timeout=5)
                            except psutil.TimeoutExpired:
                                process.kill()
                            logger.info(f"Killed process {conn.pid} on port {port}")
                            return True
                        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                            logger.error(f"Failed to kill process {conn.pid}: {e}")
                            return False
            return False
        except Exception as e:
            logger.error(f"Error killing process on port {port}: {e}")
            return False