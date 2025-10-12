const { spawn } = require('child_process');
const path = require('path');

console.log('🚀 Starting Load Balancer Project...');

// Function to find the correct Python command
function getPythonCommand() {
    const { execSync } = require('child_process');
    
    // Try python3 first (most common on Linux)
    try {
        execSync('python3 --version', { stdio: 'ignore' });
        return 'python3';
    } catch (error) {
        // Fall back to python
        try {
            execSync('python --version', { stdio: 'ignore' });
            return 'python';
        } catch (error) {
            console.error('❌ Neither python nor python3 found. Please install Python.');
            process.exit(1);
        }
    }
}

const pythonCmd = getPythonCommand();
console.log(`✅ Using Python command: ${pythonCmd}`);

// Start Python GUI backend
const pythonBackend = spawn(pythonCmd, ['-m', 'gui_backend.main'], {
    stdio: 'inherit',
    cwd: __dirname
});

// Start frontend server
const frontend = spawn(pythonCmd, ['-m', 'http.server', '3000'], {
    stdio: 'inherit',
    cwd: path.join(__dirname, 'frontend')
});

console.log('✅ GUI Backend starting on http://localhost:8000');
console.log('✅ Frontend starting on http://localhost:3000');
console.log('📊 Open http://localhost:3000 to access the Load Balancer GUI');

process.on('SIGINT', () => {
    console.log('\n🛑 Shutting down...');
    pythonBackend.kill();
    frontend.kill();
    process.exit(0);
});

pythonBackend.on('error', (err) => {
    console.error('❌ GUI Backend error:', err.message);
    process.exit(1);
});

frontend.on('error', (err) => {
    console.error('❌ Frontend error:', err.message);
    process.exit(1);
});