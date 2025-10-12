import asyncio
import time
from typing import Dict, Any, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.align import Align

class TerminalDashboard:
    """Rich-based terminal dashboard for load balancer metrics"""
    
    def __init__(self):
        self.console = Console()
        self.running = False
        self.stats = {}
        self.live: Optional[Live] = None
        
    async def start(self, stats_callback):
        """Start the terminal dashboard"""
        if self.running:
            return
            
        self.running = True
        
        with Live(self._create_layout(), refresh_per_second=2, console=self.console) as live:
            self.live = live
            
            while self.running:
                try:
                    self.stats = await stats_callback()
                    live.update(self._create_layout())
                    await asyncio.sleep(1)
                except Exception as e:
                    self.console.print(f"Dashboard error: {e}", style="red")
                    await asyncio.sleep(1)
                    
    def stop(self):
        """Stop the terminal dashboard"""
        self.running = False
        
    def _create_layout(self) -> Layout:
        """Create the dashboard layout"""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main")
        )
        layout["main"].split_row(
            Layout(name="left"),
            Layout(name="right")
        )
        
        header_text = Text("🚀 Load Balancer Dashboard", style="bold blue", justify="center")
        layout["header"].update(Panel(Align.center(header_text), border_style="blue"))
        layout["left"].update(self._create_server_panel())
        layout["right"].update(self._create_metrics_panel())
        
        return layout
        
    def _create_server_panel(self) -> Panel:
        """Create server metrics panel"""
        table = Table(title="Backend Servers", title_style="bold green")
        table.add_column("ID", justify="center")
        table.add_column("Port", justify="center")
        table.add_column("Status", justify="center")
        table.add_column("Active Conn", justify="right")
        table.add_column("Total Handled", justify="right")
        table.add_column("Avg Latency", justify="right")
        
        if 'servers' in self.stats:
            for server in self.stats['servers']:
                status_style = "green" if server['status'] == 'UP' else "red"
                table.add_row(
                    str(server['id']),
                    str(server['port']),
                    f"[{status_style}]{server['status']}[/{status_style}]",
                    str(server['active_connections']),
                    str(server['total_handled']),
                    f"{server['avg_latency_ms']:.1f}ms"
                )
        else:
            table.add_row("No data", "-", "-", "-", "-", "-")
            
        return Panel(table, border_style="green")
        
    def _create_metrics_panel(self) -> Panel:
        """Create overall metrics panel"""
        if not self.stats:
            content = Text("No metrics available", justify="center")
            return Panel(content, title="Overall Metrics", border_style="yellow")
            
        lines = []
        lines.append(f"📊 Total Requests: {self.stats.get('total_requests', 0)}")
        lines.append(f"🔗 Active Connections: {self.stats.get('active_connections', 0)}")
        lines.append(f"⚡ Request Rate: {self.stats.get('rps', 0):.1f} RPS")
        lines.append("")
        lines.append(f"🕐 Last Updated: {time.strftime('%H:%M:%S')}")
        
        content = Text("\n".join(lines))
        return Panel(content, title="Overall Metrics", border_style="cyan")


async def run_dashboard(stats_callback):
    """Run the terminal dashboard"""
    dashboard = TerminalDashboard()
    await dashboard.start(stats_callback)