import subprocess
import sys
import time
import signal
import os
from pathlib import Path

def check_dependencies():
    """Check if required dependencies are installed"""
    try:
        import fastapi
        import uvicorn
        import rich
        import psutil
        print("✅ Python dependencies verified")
        return True
    except ImportError as e:
        print(f"❌ Missing Python dependency: {e}")
        print("Please run: pip install -r requirements.txt")
        return False

def start_processes():
    """Start the GUI backend and frontend processes"""
    processes = []
    
    try:
        # Start GUI backend
        print("🚀 Starting GUI Backend...")
        gui_process = subprocess.Popen([
            sys.executable, "-m", "gui_backend.main"
        ], cwd=Path(__file__).parent)
        processes.append(("GUI Backend", gui_process))
        time.sleep(2)
        
        # Start frontend server
        print("🚀 Starting Frontend Server...")
        frontend_process = subprocess.Popen([
            sys.executable, "-m", "http.server", "3000"
        ], cwd=Path(__file__).parent / "frontend")
        processes.append(("Frontend", frontend_process))
        time.sleep(1)
        
        print("\n" + "="*50)
        print("🎉 Load Balancer Project Started Successfully!")
        print("="*50)
        print("📊 GUI Backend: http://localhost:8000")
        print("🌐 Frontend:    http://localhost:3000")
        print("💻 Open http://localhost:3000 to access the Load Balancer GUI")
        print("="*50)
        print("Press Ctrl+C to stop all services")
        print("")
        
        # Wait for processes and handle shutdown
        def signal_handler(signum, frame):
            print("\n🛑 Shutting down...")
            for name, process in processes:
                if process.poll() is None:
                    print(f"   Stopping {name}...")
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
            sys.exit(0)
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Keep running until interrupted
        while True:
            time.sleep(1)
            # Check if any process died unexpectedly
            for name, process in processes:
                if process.poll() is not None:
                    print(f"❌ {name} process died unexpectedly!")
                    signal_handler(None, None)
                    
    except Exception as e:
        print(f"❌ Error starting processes: {e}")
        # Clean up any started processes
        for name, process in processes:
            if process.poll() is None:
                process.terminate()
        sys.exit(1)

if __name__ == "__main__":
    print("🚀 Load Balancer Project Startup")
    print("-" * 30)
    
    if not check_dependencies():
        sys.exit(1)
        
    start_processes()