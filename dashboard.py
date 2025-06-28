#!/usr/bin/env python3
"""
Trading Bot Dashboard
A secure Flask web dashboard for managing trading bot scripts
"""

import os
import sys
import subprocess
import psutil
import pandas as pd
import csv
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
import threading
import time
import logging
from pathlib import Path

# Configuration
BASE_PATH = "/root/test_coinmatik/yeni_strateji2"
LOGS_PATH = os.path.join(BASE_PATH, "logs")
DEFAULT_LEVERAGE = 10
DEFAULT_TRADE_AMOUNT = 200

# Flask app setup
app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'

# Login manager setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User class for authentication
class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

# Global variables to store running processes
running_processes = {}
process_lock = threading.Lock()

def get_script_info(script_path):
    """Extract coin name and other info from script path"""
    filename = os.path.basename(script_path)
    if filename.startswith('main_') and filename.endswith('.py'):
        coin = filename[5:-3].upper()  # Remove 'main_' and '.py'
        return {
            'filename': filename,
            'coin': coin,
            'path': script_path,
            'full_path': os.path.join(BASE_PATH, filename)
        }
    return None

def scan_scripts():
    """Scan for main_*.py scripts in the base path"""
    scripts = []
    try:
        if os.path.exists(BASE_PATH):
            for file in os.listdir(BASE_PATH):
                if file.startswith('main_') and file.endswith('.py'):
                    script_info = get_script_info(file)
                    if script_info:
                        scripts.append(script_info)
    except Exception as e:
        print(f"Error scanning scripts: {e}")
    return sorted(scripts, key=lambda x: x['coin'])

def is_script_running(script_name):
    """Check if a script is currently running"""
    with process_lock:
        return script_name in running_processes and running_processes[script_name]['process'].poll() is None

def get_process_info(script_name):
    """Get detailed process information"""
    with process_lock:
        if script_name in running_processes:
            process = running_processes[script_name]['process']
            if process.poll() is None:  # Process is still running
                try:
                    # Get process details using psutil
                    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time', 'memory_info']):
                        if proc.info['pid'] == process.pid:
                            return {
                                'pid': proc.info['pid'],
                                'memory_mb': round(proc.info['memory_info'].rss / 1024 / 1024, 2),
                                'start_time': datetime.fromtimestamp(proc.info['create_time']).strftime('%Y-%m-%d %H:%M:%S'),
                                'status': 'Running'
                            }
                except:
                    pass
            else:
                # Process has finished
                del running_processes[script_name]
    return None

def start_script(script_name, leverage, trade_amount):
    """Start a trading bot script"""
    script_path = os.path.join(BASE_PATH, script_name)
    
    if not os.path.exists(script_path):
        return False, f"Script {script_name} not found"
    
    # Check if already running
    if is_script_running(script_name):
        return False, f"Script {script_name} is already running"
    
    try:
        # Change to the script directory
        env = os.environ.copy()
        env['PYTHONPATH'] = BASE_PATH
        
        # Start the process
        process = subprocess.Popen(
            [sys.executable, script_path],
            cwd=BASE_PATH,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        with process_lock:
            running_processes[script_name] = {
                'process': process,
                'leverage': leverage,
                'trade_amount': trade_amount,
                'start_time': datetime.now()
            }
        
        return True, f"Script {script_name} started successfully (PID: {process.pid})"
    
    except Exception as e:
        return False, f"Error starting script {script_name}: {str(e)}"

def stop_script(script_name):
    """Stop a running trading bot script"""
    with process_lock:
        if script_name in running_processes:
            process = running_processes[script_name]['process']
            try:
                # Try graceful termination first
                process.terminate()
                time.sleep(2)
                
                # Force kill if still running
                if process.poll() is None:
                    process.kill()
                
                del running_processes[script_name]
                return True, f"Script {script_name} stopped successfully"
            except Exception as e:
                return False, f"Error stopping script {script_name}: {str(e)}"
        else:
            return False, f"Script {script_name} is not running"

def read_csv_file(file_path, max_rows=100):
    """Read CSV file and return as list of dictionaries"""
    try:
        if not os.path.exists(file_path):
            return []
        
        data = []
        with open(file_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for i, row in enumerate(reader):
                if i >= max_rows:
                    break
                data.append(row)
        return data
    except Exception as e:
        return [{'error': f'Error reading file: {str(e)}'}]

def read_log_file(file_path, lines=300):
    """Read log file and return last N lines"""
    try:
        if not os.path.exists(file_path):
            return []
        
        with open(file_path, 'r', encoding='utf-8') as file:
            all_lines = file.readlines()
            return all_lines[-lines:] if len(all_lines) > lines else all_lines
    except Exception as e:
        return [f'Error reading log file: {str(e)}']

# Routes
@app.route('/')
@login_required
def dashboard():
    """Main dashboard page"""
    scripts = scan_scripts()
    
    # Get status for each script
    for script in scripts:
        script['running'] = is_script_running(script['filename'])
        script['process_info'] = get_process_info(script['filename'])
    
    return render_template('dashboard.html', scripts=scripts)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Simple authentication (in production, use database)
        if username == 'eralptest' and password == 'eralptest':
            user = User(username)
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """Logout"""
    logout_user()
    return redirect(url_for('login'))

@app.route('/start_script', methods=['POST'])
@login_required
def start_script_route():
    """Start a script"""
    script_name = request.form['script_name']
    leverage = int(request.form.get('leverage', DEFAULT_LEVERAGE))
    trade_amount = int(request.form.get('trade_amount', DEFAULT_TRADE_AMOUNT))
    
    success, message = start_script(script_name, leverage, trade_amount)
    
    if success:
        flash(f'✅ {message}', 'success')
    else:
        flash(f'❌ {message}', 'error')
    
    return redirect(url_for('dashboard'))

@app.route('/stop_script', methods=['POST'])
@login_required
def stop_script_route():
    """Stop a script"""
    script_name = request.form['script_name']
    
    success, message = stop_script(script_name)
    
    if success:
        flash(f'✅ {message}', 'success')
    else:
        flash(f'❌ {message}', 'error')
    
    return redirect(url_for('dashboard'))

@app.route('/logs/<coin>')
@login_required
def view_logs(coin):
    """View logs for a specific coin"""
    coin_lower = coin.lower()
    
    # File paths
    trades_file = os.path.join(LOGS_PATH, f'psar_trades_{coin_lower}.csv')
    positions_file = os.path.join(LOGS_PATH, f'psar_positions_{coin_lower}.csv')
    log_file = os.path.join(LOGS_PATH, f'main_{coin_lower}.log')
    
    # Read data
    trades_data = read_csv_file(trades_file)
    positions_data = read_csv_file(positions_file)
    log_lines = read_log_file(log_file)
    
    return render_template('logs.html', 
                         coin=coin,
                         trades_data=trades_data,
                         positions_data=positions_data,
                         log_lines=log_lines)

@app.route('/api/process_status')
@login_required
def api_process_status():
    """API endpoint for process status updates"""
    scripts = scan_scripts()
    status = {}
    
    for script in scripts:
        script_name = script['filename']
        status[script_name] = {
            'running': is_script_running(script_name),
            'process_info': get_process_info(script_name)
        }
    
    return jsonify(status)

# HTML Templates
@app.route('/templates/<template_name>')
def get_template(template_name):
    """Serve HTML templates"""
    if template_name == 'dashboard.html':
        return '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Trading Bot Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        .status-running { color: #28a745; }
        .status-stopped { color: #dc3545; }
        .card-header { background-color: #f8f9fa; }
        .table-responsive { max-height: 400px; overflow-y: auto; }
        .log-content { 
            background-color: #f8f9fa; 
            border: 1px solid #dee2e6; 
            border-radius: 0.375rem; 
            padding: 1rem; 
            font-family: 'Courier New', monospace; 
            font-size: 0.875rem; 
            max-height: 500px; 
            overflow-y: auto; 
        }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container-fluid">
            <a class="navbar-brand" href="/">
                <i class="fas fa-robot"></i> Trading Bot Dashboard
            </a>
            <div class="navbar-nav ms-auto">
                <span class="navbar-text me-3">
                    <i class="fas fa-user"></i> {{ current_user.id }}
                </span>
                <a class="nav-link" href="/logout">
                    <i class="fas fa-sign-out-alt"></i> Logout
                </a>
            </div>
        </div>
    </nav>

    <div class="container-fluid mt-4">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ 'success' if category == 'success' else 'danger' }} alert-dismissible fade show" role="alert">
                        {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <div class="row">
            <div class="col-12">
                <div class="card">
                    <div class="card-header">
                        <h5 class="mb-0">
                            <i class="fas fa-list"></i> Trading Bot Scripts
                        </h5>
                    </div>
                    <div class="card-body">
                        <div class="row">
                            {% for script in scripts %}
                            <div class="col-md-6 col-lg-4 mb-4">
                                <div class="card h-100">
                                    <div class="card-header d-flex justify-content-between align-items-center">
                                        <h6 class="mb-0">
                                            <i class="fas fa-coins"></i> {{ script.coin }}
                                        </h6>
                                        <span class="badge bg-{{ 'success' if script.running else 'secondary' }}">
                                            <i class="fas fa-{{ 'play' if script.running else 'stop' }}"></i>
                                            {{ 'Running' if script.running else 'Stopped' }}
                                        </span>
                                    </div>
                                    <div class="card-body">
                                        <p class="card-text">
                                            <strong>Script:</strong> {{ script.filename }}<br>
                                            {% if script.process_info %}
                                                <strong>PID:</strong> {{ script.process_info.pid }}<br>
                                                <strong>Memory:</strong> {{ script.process_info.memory_mb }} MB<br>
                                                <strong>Started:</strong> {{ script.process_info.start_time }}
                                            {% endif %}
                                        </p>
                                        
                                        {% if script.running %}
                                            <form method="POST" action="/stop_script" class="d-inline">
                                                <input type="hidden" name="script_name" value="{{ script.filename }}">
                                                <button type="submit" class="btn btn-danger btn-sm">
                                                    <i class="fas fa-stop"></i> Stop
                                                </button>
                                            </form>
                                        {% else %}
                                            <button type="button" class="btn btn-success btn-sm" 
                                                    data-bs-toggle="modal" 
                                                    data-bs-target="#startModal{{ loop.index }}">
                                                <i class="fas fa-play"></i> Start
                                            </button>
                                        {% endif %}
                                        
                                        <a href="/logs/{{ script.coin }}" class="btn btn-info btn-sm">
                                            <i class="fas fa-file-alt"></i> Logs
                                        </a>
                                    </div>
                                </div>
                            </div>

                            <!-- Start Modal for each script -->
                            <div class="modal fade" id="startModal{{ loop.index }}" tabindex="-1">
                                <div class="modal-dialog">
                                    <div class="modal-content">
                                        <div class="modal-header">
                                            <h5 class="modal-title">Start {{ script.coin }} Bot</h5>
                                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                                        </div>
                                        <form method="POST" action="/start_script">
                                            <div class="modal-body">
                                                <input type="hidden" name="script_name" value="{{ script.filename }}">
                                                
                                                <div class="mb-3">
                                                    <label for="leverage{{ loop.index }}" class="form-label">Leverage</label>
                                                    <input type="number" class="form-control" id="leverage{{ loop.index }}" 
                                                           name="leverage" value="10" min="1" max="100">
                                                </div>
                                                
                                                <div class="mb-3">
                                                    <label for="trade_amount{{ loop.index }}" class="form-label">Trade Amount</label>
                                                    <input type="number" class="form-control" id="trade_amount{{ loop.index }}" 
                                                           name="trade_amount" value="200" min="1">
                                                </div>
                                            </div>
                                            <div class="modal-footer">
                                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                                                <button type="submit" class="btn btn-success">
                                                    <i class="fas fa-play"></i> Start Bot
                                                </button>
                                            </div>
                                        </form>
                                    </div>
                                </div>
                            </div>
                            {% endfor %}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // Auto-refresh process status every 10 seconds
        setInterval(function() {
            fetch('/api/process_status')
                .then(response => response.json())
                .then(data => {
                    // Update status badges and process info
                    Object.keys(data).forEach(scriptName => {
                        const status = data[scriptName];
                        const card = document.querySelector(`[data-script="${scriptName}"]`);
                        if (card) {
                            const badge = card.querySelector('.badge');
                            const statusText = status.running ? 'Running' : 'Stopped';
                            const statusClass = status.running ? 'success' : 'secondary';
                            badge.className = `badge bg-${statusClass}`;
                            badge.innerHTML = `<i class="fas fa-${status.running ? 'play' : 'stop'}"></i> ${statusText}`;
                        }
                    });
                });
        }, 10000);
    </script>
</body>
</html>
        '''
    elif template_name == 'login.html':
        return '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Trading Bot Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f8f9fa; }
        .login-container {
            max-width: 400px;
            margin: 100px auto;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="login-container">
            <div class="card">
                <div class="card-header text-center">
                    <h4><i class="fas fa-robot"></i> Trading Bot Dashboard</h4>
                </div>
                <div class="card-body">
                    {% with messages = get_flashed_messages() %}
                        {% if messages %}
                            {% for message in messages %}
                                <div class="alert alert-danger">{{ message }}</div>
                            {% endfor %}
                        {% endif %}
                    {% endwith %}
                    
                    <form method="POST">
                        <div class="mb-3">
                            <label for="username" class="form-label">Username</label>
                            <input type="text" class="form-control" id="username" name="username" required>
                        </div>
                        <div class="mb-3">
                            <label for="password" class="form-label">Password</label>
                            <input type="password" class="form-control" id="password" name="password" required>
                        </div>
                        <button type="submit" class="btn btn-primary w-100">Login</button>
                    </form>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
        '''
    elif template_name == 'logs.html':
        return '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ coin }} Logs - Trading Bot Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        .table-responsive { max-height: 400px; overflow-y: auto; }
        .log-content { 
            background-color: #f8f9fa; 
            border: 1px solid #dee2e6; 
            border-radius: 0.375rem; 
            padding: 1rem; 
            font-family: 'Courier New', monospace; 
            font-size: 0.875rem; 
            max-height: 500px; 
            overflow-y: auto; 
        }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container-fluid">
            <a class="navbar-brand" href="/">
                <i class="fas fa-robot"></i> Trading Bot Dashboard
            </a>
            <div class="navbar-nav ms-auto">
                <a class="nav-link" href="/">
                    <i class="fas fa-arrow-left"></i> Back to Dashboard
                </a>
                <a class="nav-link" href="/logout">
                    <i class="fas fa-sign-out-alt"></i> Logout
                </a>
            </div>
        </div>
    </nav>

    <div class="container-fluid mt-4">
        <h2><i class="fas fa-coins"></i> {{ coin }} Logs</h2>
        
        <ul class="nav nav-tabs" id="logTabs" role="tablist">
            <li class="nav-item" role="presentation">
                <button class="nav-link active" id="trades-tab" data-bs-toggle="tab" data-bs-target="#trades" type="button" role="tab">
                    <i class="fas fa-chart-line"></i> Trades
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="positions-tab" data-bs-toggle="tab" data-bs-target="#positions" type="button" role="tab">
                    <i class="fas fa-chart-bar"></i> Positions
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="logs-tab" data-bs-toggle="tab" data-bs-target="#logs" type="button" role="tab">
                    <i class="fas fa-file-alt"></i> Logs
                </button>
            </li>
        </ul>
        
        <div class="tab-content mt-3" id="logTabsContent">
            <div class="tab-pane fade show active" id="trades" role="tabpanel">
                <div class="card">
                    <div class="card-header">
                        <h5>Trade History</h5>
                    </div>
                    <div class="card-body">
                        {% if trades_data %}
                            <div class="table-responsive">
                                <table class="table table-striped table-sm">
                                    <thead>
                                        <tr>
                                            {% for header in trades_data[0].keys() %}
                                                <th>{{ header }}</th>
                                            {% endfor %}
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {% for row in trades_data %}
                                            <tr>
                                                {% for value in row.values() %}
                                                    <td>{{ value }}</td>
                                                {% endfor %}
                                            </tr>
                                        {% endfor %}
                                    </tbody>
                                </table>
                            </div>
                        {% else %}
                            <p class="text-muted">No trade data available.</p>
                        {% endif %}
                    </div>
                </div>
            </div>
            
            <div class="tab-pane fade" id="positions" role="tabpanel">
                <div class="card">
                    <div class="card-header">
                        <h5>Position History</h5>
                    </div>
                    <div class="card-body">
                        {% if positions_data %}
                            <div class="table-responsive">
                                <table class="table table-striped table-sm">
                                    <thead>
                                        <tr>
                                            {% for header in positions_data[0].keys() %}
                                                <th>{{ header }}</th>
                                            {% endfor %}
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {% for row in positions_data %}
                                            <tr>
                                                {% for value in row.values() %}
                                                    <td>{{ value }}</td>
                                                {% endfor %}
                                            </tr>
                                        {% endfor %}
                                    </tbody>
                                </table>
                            </div>
                        {% else %}
                            <p class="text-muted">No position data available.</p>
                        {% endif %}
                    </div>
                </div>
            </div>
            
            <div class="tab-pane fade" id="logs" role="tabpanel">
                <div class="card">
                    <div class="card-header">
                        <h5>Application Logs (Last 300 lines)</h5>
                    </div>
                    <div class="card-body">
                        <div class="log-content">
                            {% if log_lines %}
                                {% for line in log_lines %}
                                    <div>{{ line.rstrip() }}</div>
                                {% endfor %}
                            {% else %}
                                <p class="text-muted">No log data available.</p>
                            {% endif %}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
        '''
    else:
        return "Template not found", 404

if __name__ == '__main__':
    # Ensure logs directory exists
    os.makedirs(LOGS_PATH, exist_ok=True)
    
    print(f"🚀 Starting Trading Bot Dashboard...")
    print(f"📁 Base path: {BASE_PATH}")
    print(f"📁 Logs path: {LOGS_PATH}")
    print(f"🌐 Dashboard will be available at: http://46.101.3.218:5000")
    print(f"👤 Login credentials: eralptest / eralptest")
    
    # Start the Flask app
    app.run(host='0.0.0.0', port=5000, debug=False) 