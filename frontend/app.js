class LoadBalancerApp {
    constructor() {
        this.ws = null;
        this.connected = false;
        this.graphData = {
            timestamps: [],
            servers: {}
        };
        this.graphPaused = false;
        this.autoScroll = true;
        this.modalConfirmCallback = null;
        this.apiBaseUrl = (window.LOAD_BALANCER_CONFIG?.apiBaseUrl || 'http://localhost:8000').replace(/\/+$/, '');
        this.controlTokenRequired = Boolean(window.LOAD_BALANCER_CONFIG?.tokenRequired);
        this.controlToken = sessionStorage.getItem('lb_control_token') || '';
        if (this.controlTokenRequired && !this.controlToken) {
            this.controlToken = prompt('Enter the deployment control token:') || '';
            if (this.controlToken) sessionStorage.setItem('lb_control_token', this.controlToken);
        }
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.setupGraph();
        this.loadStatus().finally(() => this.setupWebSocket());
    }
    
    setupWebSocket() {
        const wsUrl = new URL(this.apiBaseUrl + '/ws');
        wsUrl.protocol = wsUrl.protocol === 'https:' ? 'wss:' : 'ws:';
        
        try {
            const protocols = this.controlTokenRequired ? ['load-balancer', this.controlToken] : undefined;
            this.ws = protocols ? new WebSocket(wsUrl.toString(), protocols) : new WebSocket(wsUrl.toString());
            
            this.ws.onopen = () => {
                this.connected = true;
                this.updateConnectionStatus(true);
                this.addLog('Connected to server', 'success');
            };
            
            this.ws.onclose = () => {
                this.connected = false;
                this.updateConnectionStatus(false);
                this.addLog('Disconnected from server', 'error');
                setTimeout(() => this.setupWebSocket(), 3000);
            };
            
            this.ws.onerror = (error) => {
                this.addLog(`WebSocket error: ${error}`, 'error');
            };
            
            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleMetricsUpdate(data);
                } catch (e) {
                    this.addLog(`Error parsing message: ${e}`, 'error');
                }
            };
        } catch (error) {
            this.addLog(`Failed to connect: ${error}`, 'error');
            setTimeout(() => this.setupWebSocket(), 3000);
        }
    }
    
    updateConnectionStatus(connected) {
        const statusDot = document.getElementById('connection-status');
        const statusText = document.getElementById('connection-text');
        
        if (connected) {
            statusDot.className = 'status-dot online';
            statusText.textContent = 'Connected';
        } else {
            statusDot.className = 'status-dot offline';
            statusText.textContent = 'Disconnected';
        }
    }
    
    setupEventListeners() {
        document.getElementById('start-servers').addEventListener('click', () => this.startServers());
        document.getElementById('stop-servers').addEventListener('click', () => this.stopServers());
        document.getElementById('start-lb').addEventListener('click', () => this.startLoadBalancer());
        document.getElementById('stop-lb').addEventListener('click', () => this.stopLoadBalancer());
        document.getElementById('set-algorithm').addEventListener('click', () => this.setAlgorithm());
        document.getElementById('start-load-test').addEventListener('click', () => this.startLoadTest());
        document.getElementById('check-port').addEventListener('click', () => this.checkPort());
        document.getElementById('kill-port').addEventListener('click', () => this.killPort());
        document.getElementById('pause-graph').addEventListener('click', () => this.toggleGraphPause());
        document.getElementById('clear-graph').addEventListener('click', () => this.clearGraph());
        document.getElementById('clear-logs').addEventListener('click', () => this.clearLogs());
        document.getElementById('auto-scroll').addEventListener('click', () => this.toggleAutoScroll());
        document.getElementById('modal-confirm').addEventListener('click', () => this.confirmModal());
        document.getElementById('modal-cancel').addEventListener('click', () => this.closeModal());
    }
    
    async makeRequest(url, method = 'GET', data = null) {
        try {
            const options = {
                method,
                headers: {
                    'Content-Type': 'application/json',
                    ...(this.controlToken ? { 'X-Control-Token': this.controlToken } : {}),
                },
            };
            
            if (data) {
                options.body = JSON.stringify(data);
            }
            
            const response = await fetch(this.apiBaseUrl + url, options);
            if (response.status === 401 && this.controlTokenRequired) {
                const token = prompt('The control token was rejected. Enter it again:') || '';
                if (!token) throw new Error('A valid control token is required');
                this.controlToken = token;
                sessionStorage.setItem('lb_control_token', token);
                options.headers['X-Control-Token'] = token;
                const retry = await fetch(this.apiBaseUrl + url, options);
                if (!retry.ok) throw new Error('Request failed (' + retry.status + ')');
                return await retry.json();
            }
            if (!response.ok) throw new Error('Request failed (' + response.status + ')');
            const result = await response.json();
            
            if (!result.success && result.error) {
                throw new Error(result.error);
            }
            
            return result;
        } catch (error) {
            this.addLog(`Request failed: ${error.message}`, 'error');
            throw error;
        }
    }
    
    async startServers() {
        try {
            this.addLog('Starting backend servers...', 'info');
            const result = await this.makeRequest('/api/servers/start', 'POST');
            
            if (result.success) {
                this.addLog(result.message, 'success');
            } else if (result.conflict) {
                this.showPortConflictModal(result);
            }
        } catch (error) {
            this.addLog(`Failed to start servers: ${error.message}`, 'error');
        }
    }
    
    async stopServers() {
        try {
            this.addLog('Stopping backend servers...', 'info');
            const result = await this.makeRequest('/api/servers/stop', 'POST');
            this.addLog(result.message, 'success');
        } catch (error) {
            this.addLog(`Failed to stop servers: ${error.message}`, 'error');
        }
    }
    
    async startLoadBalancer() {
        try {
            this.addLog('Starting load balancer...', 'info');
            const result = await this.makeRequest('/api/load-balancer/start', 'POST');
            
            if (result.success) {
                this.addLog(result.message, 'success');
            } else if (result.conflict) {
                this.showPortConflictModal(result);
            }
        } catch (error) {
            this.addLog(`Failed to start load balancer: ${error.message}`, 'error');
        }
    }
    
    async stopLoadBalancer() {
        try {
            this.addLog('Stopping load balancer...', 'info');
            const result = await this.makeRequest('/api/load-balancer/stop', 'POST');
            this.addLog(result.message, 'success');
        } catch (error) {
            this.addLog(`Failed to stop load balancer: ${error.message}`, 'error');
        }
    }
    
    async setAlgorithm() {
        try {
            const algorithm = document.getElementById('algorithm-select').value;
            this.addLog(`Setting algorithm to ${algorithm}...`, 'info');
            const result = await this.makeRequest(`/api/load-balancer/algorithm/${algorithm}`, 'POST');
            this.addLog(result.message, 'success');
        } catch (error) {
            this.addLog(`Failed to set algorithm: ${error.message}`, 'error');
        }
    }
    
    async startLoadTest() {
        try {
            const requests = parseInt(document.getElementById('requests').value);
            const concurrency = parseInt(document.getElementById('concurrency').value);
            const rps = parseInt(document.getElementById('rps').value);
            
            const testConfig = { requests, concurrency, rps };
            
            this.addLog(`Starting load test: ${requests} requests, ${concurrency} concurrent, ${rps} RPS`, 'info');
            const result = await this.makeRequest('/api/load-test/start', 'POST', testConfig);
            this.addLog(result.message, 'success');
        } catch (error) {
            this.addLog(`Failed to start load test: ${error.message}`, 'error');
        }
    }
    
    async checkPort() {
        try {
            const port = parseInt(document.getElementById('port-input').value);
            if (!port || port < 1 || port > 65535) {
                this.addLog('Please enter a valid port number (1-65535)', 'warning');
                return;
            }
            
            const result = await this.makeRequest(`/api/port/${port}/info`);
            const infoBox = document.getElementById('port-info');
            
            if (result.in_use) {
                const info = result.info;
                infoBox.innerHTML = `
                    <strong>Port ${port} is in use:</strong><br>
                    PID: ${info.pid}<br>
                    Process: ${info.name}<br>
                    Command: ${info.cmdline}<br>
                    User: ${info.username}
                `;
                infoBox.className = 'info-box error';
            } else {
                infoBox.innerHTML = `Port ${port} is available`;
                infoBox.className = 'info-box success';
            }
        } catch (error) {
            this.addLog(`Failed to check port: ${error.message}`, 'error');
        }
    }
    
    async killPort() {
        const port = parseInt(document.getElementById('port-input').value);
        if (!port || port < 1 || port > 65535) {
            this.addLog('Please enter a valid port number (1-65535)', 'warning');
            return;
        }
        
        this.showConfirmModal(
            'Kill Process',
            `Are you sure you want to kill the process using port ${port}?`,
            async () => {
                try {
                    const result = await this.makeRequest(`/api/port/${port}/kill`, 'POST');
                    this.addLog(result.message, 'success');
                    this.checkPort();
                } catch (error) {
                    this.addLog(`Failed to kill process: ${error.message}`, 'error');
                }
            }
        );
    }
    
    async simulateServerFailure(serverId) {
        try {
            const result = await this.makeRequest(`/api/server/${serverId}/fail`, 'POST');
            this.addLog(result.message, 'success');
        } catch (error) {
            this.addLog(`Failed to simulate failure for server ${serverId}: ${error.message}`, 'error');
        }
    }
    
    async recoverServer(serverId) {
        try {
            const result = await this.makeRequest(`/api/server/${serverId}/recover`, 'POST');
            this.addLog(result.message, 'success');
        } catch (error) {
            this.addLog(`Failed to recover server ${serverId}: ${error.message}`, 'error');
        }
    }
    
    promptServerLatency(serverId) {
        const latency = prompt(`Enter latency in seconds for Server ${serverId}:`, '0.5');
        if (latency !== null) {
            const latencyValue = parseFloat(latency);
            if (!isNaN(latencyValue) && latencyValue >= 0) {
                this.setServerLatency(serverId, latencyValue);
            } else {
                this.addLog('Invalid latency value', 'warning');
            }
        }
    }
    
    async setServerLatency(serverId, latency) {
        try {
            const result = await this.makeRequest(`/api/server/${serverId}/latency/${latency}`, 'POST');
            this.addLog(result.message, 'success');
        } catch (error) {
            this.addLog(`Failed to set latency for server ${serverId}: ${error.message}`, 'error');
        }
    }
    
    handleMetricsUpdate(data) {
        this.updateMetricsDisplay(data);
        this.updateServerCards(data.servers || []);
        
        if (!this.graphPaused) {
            this.updateGraph(data);
        }
    }
    
    updateMetricsDisplay(data) {
        document.getElementById('total-requests').textContent = data.total_requests || 0;
        document.getElementById('request-rate').textContent = `${(data.rps || 0).toFixed(1)} RPS`;
        document.getElementById('active-connections').textContent = data.active_connections || 0;
    }
    
    updateServerCards(servers) {
        const serverList = document.getElementById('server-list');
        serverList.innerHTML = '';
        
        servers.forEach(server => {
            const card = document.createElement('div');
            card.className = `server-card status-${server.status.toLowerCase()}`;
            
            card.innerHTML = `
                <div class="server-header">
                    <div class="server-id">Server ${server.id}</div>
                    <div class="server-status ${server.status.toLowerCase()}">${server.status}</div>
                </div>
                <div class="server-metrics">
                    <div>Port: ${server.port}</div>
                    <div>Active: ${server.active_connections}</div>
                    <div>Total: ${server.total_handled}</div>
                    <div>Latency: ${server.avg_latency_ms}ms</div>
                </div>
                <div class="server-actions">
                    <button class="btn btn-danger" onclick="app.simulateServerFailure(${server.id})">Fail</button>
                    <button class="btn btn-success" onclick="app.recoverServer(${server.id})">Recover</button>
                    <button class="btn btn-warning" onclick="app.promptServerLatency(${server.id})">Latency</button>
                </div>
            `;
            
            serverList.appendChild(card);
        });
    }
    
    setupGraph() {
        const layout = {
            title: 'Request Distribution Over Time',
            xaxis: { title: 'Time' },
            yaxis: { title: 'Requests' },
            margin: { t: 40, r: 40, b: 40, l: 40 },
            showlegend: true,
            legend: { x: 0, y: 1 }
        };
        
        Plotly.newPlot('request-graph', [], layout, {responsive: true});
    }
    
    updateGraph(data) {
        const now = new Date();
        const servers = data.servers || [];
        
        // Keep only last 60 data points (1 minute at 1-second intervals)
        if (this.graphData.timestamps.length >= 60) {
            this.graphData.timestamps.shift();
            Object.keys(this.graphData.servers).forEach(serverId => {
                if (this.graphData.servers[serverId].length >= 60) {
                    this.graphData.servers[serverId].shift();
                }
            });
        }
        
        this.graphData.timestamps.push(now);
        
        // Update server data
        servers.forEach(server => {
            const serverId = `server-${server.id}`;
            if (!this.graphData.servers[serverId]) {
                this.graphData.servers[serverId] = [];
            }
            this.graphData.servers[serverId].push(server.total_handled);
        });
        
        // Prepare traces for plotting
        const traces = Object.keys(this.graphData.servers).map(serverId => {
            const serverNum = serverId.split('-')[1];
            return {
                x: this.graphData.timestamps,
                y: this.graphData.servers[serverId],
                type: 'scatter',
                mode: 'lines+markers',
                name: `Server ${serverNum}`,
                line: { width: 2 }
            };
        });
        
        Plotly.redraw('request-graph', traces);
    }
    
    toggleGraphPause() {
        this.graphPaused = !this.graphPaused;
        const button = document.getElementById('pause-graph');
        button.textContent = this.graphPaused ? 'Resume' : 'Pause';
        button.className = this.graphPaused ? 'btn btn-success' : 'btn btn-secondary';
    }
    
    clearGraph() {
        this.graphData = {
            timestamps: [],
            servers: {}
        };
        Plotly.redraw('request-graph', []);
        this.addLog('Graph cleared', 'info');
    }
    
    addLog(message, type = 'info') {
        const logContent = document.getElementById('log-content');
        const timestamp = new Date().toLocaleTimeString();
        
        const logEntry = document.createElement('div');
        logEntry.className = `log-entry log-${type}`;
        logEntry.textContent = `[${timestamp}] ${message}`;
        
        logContent.appendChild(logEntry);
        
        // Auto-scroll to bottom if enabled
        if (this.autoScroll) {
            logContent.scrollTop = logContent.scrollHeight;
        }
        
        // Keep only last 100 log entries
        while (logContent.children.length > 100) {
            logContent.removeChild(logContent.firstChild);
        }
    }
    
    clearLogs() {
        document.getElementById('log-content').innerHTML = '';
        this.addLog('Logs cleared', 'info');
    }
    
    toggleAutoScroll() {
        this.autoScroll = !this.autoScroll;
        const button = document.getElementById('auto-scroll');
        button.className = this.autoScroll ? 'btn btn-secondary active' : 'btn btn-secondary';
    }
    
    showConfirmModal(title, message, confirmCallback) {
        document.getElementById('modal-title').textContent = title;
        document.getElementById('modal-message').textContent = message;
        document.getElementById('modal').style.display = 'block';
        
        this.modalConfirmCallback = confirmCallback;
    }
    
    showPortConflictModal(result) {
        const message = `${result.error}\n\nProcess Details:\n${JSON.stringify(result.conflict, null, 2)}\n\nWould you like to kill the conflicting process?`;
        
        this.showConfirmModal('Port Conflict', message, async () => {
            try {
                // Extract port from error message (assuming format "Port X is in use")
                const portMatch = result.error.match(/Port (\d+) is in use/);
                if (portMatch) {
                    const port = parseInt(portMatch[1]);
                    await this.makeRequest(`/api/port/${port}/kill`, 'POST');
                    this.addLog(`Killed conflicting process on port ${port}`, 'success');
                    
                    // Retry the original action after a brief delay
                    setTimeout(() => {
                        if (result.error.includes('Load balancer')) {
                            this.startLoadBalancer();
                        } else if (result.error.includes('Server')) {
                            this.startServers();
                        }
                    }, 1000);
                }
            } catch (error) {
                this.addLog(`Failed to kill conflicting process: ${error.message}`, 'error');
            }
        });
    }
    
    confirmModal() {
        if (this.modalConfirmCallback) {
            this.modalConfirmCallback();
            this.modalConfirmCallback = null;
        }
        this.closeModal();
    }
    
    closeModal() {
        document.getElementById('modal').style.display = 'none';
        this.modalConfirmCallback = null;
    }
    
    async loadStatus() {
        try {
            const result = await this.makeRequest('/api/status');
            this.addLog('Status loaded', 'info');
            
            // Update algorithm selector with current selection if available
            const algorithmSelect = document.getElementById('algorithm-select');
            const availableAlgorithms = result.available_algorithms || [];
            
            algorithmSelect.innerHTML = '';
            availableAlgorithms.forEach(algo => {
                const option = document.createElement('option');
                option.value = algo;
                option.textContent = algo.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
                algorithmSelect.appendChild(option);
            });
            
        } catch (error) {
            this.addLog(`Failed to load status: ${error.message}`, 'error');
        }
    }
}

// Initialize the application when the DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.app = new LoadBalancerApp();
});

// Handle modal clicks outside content
window.addEventListener('click', (event) => {
    const modal = document.getElementById('modal');
    if (event.target === modal) {
        window.app.closeModal();
    }
});