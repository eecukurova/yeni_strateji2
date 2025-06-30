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
DEFAULT_STRATEGY = "psar_atr_strategy"

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
        if script_name in running_processes:
            process_info = running_processes[script_name]
            pid = process_info.get('pid')
            
            if pid:
                try:
                    # Check if process exists
                    psutil.Process(pid)
                    return True
                except psutil.NoSuchProcess:
                    # Process has finished
                    del running_processes[script_name]
                    return False
            else:
                # Fallback to old method
                process = process_info['process']
                if process.poll() is None:
                    return True
                else:
                    # Process has finished
                    del running_processes[script_name]
                    return False
    return False

def get_process_info(script_name):
    """Get detailed process information"""
    with process_lock:
        if script_name in running_processes:
            process_info = running_processes[script_name]
            pid = process_info.get('pid')
            
            if pid:
                try:
                    # Get process details using psutil
                    proc = psutil.Process(pid)
                    return {
                        'pid': pid,
                        'memory_mb': round(proc.memory_info().rss / 1024 / 1024, 2),
                        'start_time': datetime.fromtimestamp(proc.create_time()).strftime('%Y-%m-%d %H:%M:%S'),
                        'status': 'Running',
                        'strategy': process_info.get('strategy', 'Unknown'),
                        'leverage': process_info.get('leverage', 'Unknown'),
                        'trade_amount': process_info.get('trade_amount', 'Unknown')
                    }
                except psutil.NoSuchProcess:
                    # Process has finished
                    del running_processes[script_name]
                    return None
                except (psutil.AccessDenied, psutil.ZombieProcess):
                    return {
                        'pid': pid,
                        'memory_mb': 0,
                        'start_time': 'Unknown',
                        'status': 'Running (Limited Info)',
                        'strategy': process_info.get('strategy', 'Unknown'),
                        'leverage': process_info.get('leverage', 'Unknown'),
                        'trade_amount': process_info.get('trade_amount', 'Unknown')
                    }
            else:
                # Fallback to old method
                process = process_info['process']
                if process.poll() is None:  # Process is still running
                    try:
                        # Get process details using psutil
                        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time', 'memory_info']):
                            if proc.info['pid'] == process.pid:
                                return {
                                    'pid': proc.info['pid'],
                                    'memory_mb': round(proc.info['memory_info'].rss / 1024 / 1024, 2),
                                    'start_time': datetime.fromtimestamp(proc.info['create_time']).strftime('%Y-%m-%d %H:%M:%S'),
                                    'status': 'Running',
                                    'strategy': process_info.get('strategy', 'Unknown'),
                                    'leverage': process_info.get('leverage', 'Unknown'),
                                    'trade_amount': process_info.get('trade_amount', 'Unknown')
                                }
                    except:
                        pass
                else:
                    # Process has finished
                    del running_processes[script_name]
    return None

def start_script(script_name, leverage, trade_amount, strategy):
    """Start a trading bot script using nohup for proper logging"""
    script_path = os.path.join(BASE_PATH, script_name)
    
    if not os.path.exists(script_path):
        return False, f"Script {script_name} not found"
    
    # Check if already running
    if is_script_running(script_name):
        return False, f"Script {script_name} is already running"
    
    try:
        # Create logs directory if it doesn't exist
        os.makedirs(LOGS_PATH, exist_ok=True)
        
        # Prepare log file path
        log_file = os.path.join(LOGS_PATH, f'{script_name.replace(".py", "")}.log')
        
        # Build the nohup command
        nohup_command = f'nohup python3 {script_name} > {log_file} 2>&1 &'
        
        # Set environment variables
        env = os.environ.copy()
        env['LEVERAGE'] = str(leverage)
        env['TRADE_AMOUNT'] = str(trade_amount)
        env['STRATEGY'] = str(strategy)
        
        # Execute the command with environment variables
        result = subprocess.run(
            nohup_command,
            shell=True,
            cwd=BASE_PATH,
            env=env,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            # Get the PID from the output or find it by process name
            time.sleep(1)  # Give the process time to start
            
            # Find the process by script name
            script_pid = None
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = proc.info['cmdline']
                    if cmdline and script_name in ' '.join(cmdline):
                        script_pid = proc.info['pid']
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            if script_pid:
                # Create a dummy process object for tracking
                class DummyProcess:
                    def __init__(self, pid):
                        self.pid = pid
                    
                    def poll(self):
                        try:
                            psutil.Process(self.pid)
                            return None  # Still running
                        except psutil.NoSuchProcess:
                            return 0  # Finished
                
                dummy_process = DummyProcess(script_pid)
                
                with process_lock:
                    running_processes[script_name] = {
                        'process': dummy_process,
                        'leverage': leverage,
                        'trade_amount': trade_amount,
                        'strategy': strategy,
                        'start_time': datetime.now(),
                        'pid': script_pid
                    }
                
                return True, f"Script {script_name} started successfully (PID: {script_pid})"
            else:
                return False, f"Script {script_name} started but PID not found"
        else:
            return False, f"Error starting script {script_name}: {result.stderr}"
    
    except Exception as e:
        return False, f"Error starting script {script_name}: {str(e)}"

def stop_script(script_name):
    """Stop a running trading bot script"""
    with process_lock:
        if script_name in running_processes:
            process_info = running_processes[script_name]
            try:
                # Get the PID
                pid = process_info.get('pid')
                if pid:
                    # Try to kill the process using kill command
                    kill_result = subprocess.run(
                        f'kill {pid}',
                        shell=True,
                        capture_output=True,
                        text=True
                    )
                    
                    if kill_result.returncode == 0:
                        # Wait a bit and check if process is still running
                        time.sleep(2)
                        
                        # Force kill if still running
                        try:
                            psutil.Process(pid)
                            # Process still running, force kill
                            subprocess.run(f'kill -9 {pid}', shell=True)
                        except psutil.NoSuchProcess:
                            pass  # Process already stopped
                        
                        del running_processes[script_name]
                        return True, f"Script {script_name} stopped successfully"
                    else:
                        return False, f"Error stopping script {script_name}: {kill_result.stderr}"
                else:
                    # Fallback to old method if PID not available
                    process = process_info['process']
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
                        
            except Exception as e:
                return False, f"Error stopping script {script_name}: {str(e)}"
        else:
            return False, f"Script {script_name} is not running"

def read_csv_file(file_path, max_rows=100):
    """Read CSV file and return as list of dictionaries"""
    try:
        if not os.path.exists(file_path):
            return [{'error': f'File not found: {file_path}'}]
        
        data = []
        
        # Try different encodings
        encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as file:
                    # Read first few lines to detect format
                    first_lines = [file.readline() for _ in range(5)]
                    file.seek(0)  # Reset to beginning
                    
                    # Try to read as CSV
                    reader = csv.DictReader(file)
                    
                    # Read all rows first
                    all_rows = []
                    for row in reader:
                        # Clean up the data
                        cleaned_row = {}
                        for key, value in row.items():
                            if key:  # Skip empty column names
                                cleaned_row[key.strip()] = value.strip() if value else ''
                        all_rows.append(cleaned_row)
                    
                    # Return last max_rows
                    data = all_rows[-max_rows:] if len(all_rows) > max_rows else all_rows
                    
                # If we get here, reading was successful
                break
                
            except UnicodeDecodeError:
                continue
            except Exception as e:
                # Try reading as plain text if CSV fails
                try:
                    file.seek(0)
                    lines = file.readlines()
                    if lines:
                        # Assume first line is header
                        headers = lines[0].strip().split(',')
                        all_rows = []
                        for line in lines[1:]:
                            values = line.strip().split(',')
                            if len(values) == len(headers):
                                row = dict(zip(headers, values))
                                all_rows.append(row)
                        
                        # Return last max_rows
                        data = all_rows[-max_rows:] if len(all_rows) > max_rows else all_rows
                except:
                    pass
                break
        
        if not data:
            return [{'error': f'Could not read CSV file: {file_path}. Tried encodings: {encodings}'}]
        
        return data
        
    except Exception as e:
        return [{'error': f'Error reading file {file_path}: {str(e)}'}]

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
    
    # Available strategies
    strategies = [
        {'value': 'psar_atr_strategy', 'name': 'PSAR ATR Strategy'},
        {'value': 'atr_strategy', 'name': 'ATR Strategy'},
        {'value': 'eralp_strateji2', 'name': 'Eralp Strategy 2'},
        {'value': 'skorlama_strategy', 'name': 'Skorlama Strategy'}
    ]
    
    return render_template('dashboard.html', scripts=scripts, strategies=strategies)

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
    strategy = request.form.get('strategy', DEFAULT_STRATEGY)
    
    success, message = start_script(script_name, leverage, trade_amount, strategy)
    
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
    # Try different coin name formats
    coin_variants = [
        coin.lower(),  # bnb
        coin.upper(),  # BNB
        coin.lower() + 'usdt',  # bnbusdt
        coin.upper() + 'USDT',  # BNBUSDT
        coin.lower() + 'usdt',  # bnbusdt (lowercase)
    ]
    
    trades_data = []
    positions_data = []
    telegram_data = []
    log_lines = []
    
    # Try to find trades file - check all possible formats
    trades_file = None
    trades_file_patterns = [
        f'psar_trades_{coin.lower()}.csv',  # PSAR ATR Strategy
        f'atr_trades_{coin.lower()}.csv',   # ATR Strategy
        f'trades_{coin.lower()}.csv',       # Skorlama Strategy
        f'psar_trades_{coin.upper()}.csv',  # PSAR ATR Strategy (uppercase)
        f'atr_trades_{coin.upper()}.csv',   # ATR Strategy (uppercase)
        f'trades_{coin.upper()}.csv',       # Skorlama Strategy (uppercase)
    ]
    
    # Add USDT variants
    for variant in coin_variants:
        trades_file_patterns.extend([
            f'psar_trades_{variant}.csv',
            f'atr_trades_{variant}.csv',
            f'trades_{variant}.csv',
        ])
    
    # Search for trades file
    for pattern in trades_file_patterns:
        potential_file = os.path.join(LOGS_PATH, pattern)
        if os.path.exists(potential_file):
            trades_file = potential_file
            break
    
    # Try to find positions file - check all possible formats
    positions_file = None
    positions_file_patterns = [
        f'psar_positions_{coin.lower()}.csv',  # PSAR ATR Strategy
        f'atr_positions_{coin.lower()}.csv',   # ATR Strategy
        f'positions_{coin.lower()}.csv',       # Skorlama Strategy
        f'psar_positions_{coin.upper()}.csv',  # PSAR ATR Strategy (uppercase)
        f'atr_positions_{coin.upper()}.csv',   # ATR Strategy (uppercase)
        f'positions_{coin.upper()}.csv',       # Skorlama Strategy (uppercase)
    ]
    
    # Add USDT variants
    for variant in coin_variants:
        positions_file_patterns.extend([
            f'psar_positions_{variant}.csv',
            f'atr_positions_{variant}.csv',
            f'positions_{variant}.csv',
        ])
    
    # Search for positions file
    for pattern in positions_file_patterns:
        potential_file = os.path.join(LOGS_PATH, pattern)
        if os.path.exists(potential_file):
            positions_file = potential_file
            break
    
    # Try to find telegram file - also check for general telegram file
    telegram_file = None
    for variant in coin_variants:
        potential_file = os.path.join(LOGS_PATH, f'telegram_{variant}.csv')
        if os.path.exists(potential_file):
            telegram_file = potential_file
            break
    
    # If specific telegram file not found, try general telegram file
    if not telegram_file:
        general_telegram_file = os.path.join(LOGS_PATH, 'telegram_general.csv')
        if os.path.exists(general_telegram_file):
            telegram_file = general_telegram_file
    
    # Try to find log file
    log_file = None
    for variant in coin_variants:
        potential_file = os.path.join(LOGS_PATH, f'main_{variant}.log')
        if os.path.exists(potential_file):
            log_file = potential_file
            break
    
    # Read data if files exist
    if trades_file:
        trades_data = read_csv_file(trades_file, max_rows=300)  # Show last 300 rows
    else:
        # Debug: list available files
        available_files = [f for f in os.listdir(LOGS_PATH) if 'trades' in f.lower()]
        trades_data = [{'error': f'Trades file not found. Available files: {available_files}'}]
    
    if positions_file:
        positions_data = read_csv_file(positions_file, max_rows=300)  # Show last 300 rows
    else:
        # Debug: list available files
        available_files = [f for f in os.listdir(LOGS_PATH) if 'positions' in f.lower()]
        positions_data = [{'error': f'Positions file not found. Available files: {available_files}'}]
    
    if telegram_file:
        telegram_data = read_csv_file(telegram_file, max_rows=300)  # Show last 300 rows
    else:
        # Debug: list available files
        available_files = [f for f in os.listdir(LOGS_PATH) if f.startswith('telegram_')]
        telegram_data = [{'error': f'Telegram file not found. Available files: {available_files}'}]
    
    if log_file:
        log_lines = read_log_file(log_file, lines=300)
    else:
        # Debug: list available files
        available_files = [f for f in os.listdir(LOGS_PATH) if f.startswith('main_')]
        log_lines = [f'Log file not found. Available files: {available_files}']
    
    # Signal control data - ortak dosya
    signal_control_file = os.path.join(LOGS_PATH, 'sinyal_kontrol.csv')
    signal_control_data = []
    if os.path.exists(signal_control_file):
        signal_control_data = read_csv_file(signal_control_file, max_rows=500)  # Show last 500 rows
    else:
        signal_control_data = [{'error': 'Signal control file not found. Signals will appear after first detection.'}]
    
    return render_template('logs.html', 
                         coin=coin,
                         trades_data=trades_data,
                         positions_data=positions_data,
                         telegram_data=telegram_data,
                         signal_control_data=signal_control_data,
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

@app.route('/strategies')
@login_required
def strategies():
    """Strategies page"""
    strategies_info = [
        {
            'id': 'psar_atr_strategy',
            'name': 'PSAR ATR Strategy',
            'name_tr': 'PSAR ATR Stratejisi',
            'description_tr': 'PSAR ATR Stratejisi, Parabolic SAR ve Average True Range (ATR) göstergelerini birleştiren gelişmiş bir momentum tabanlı trading stratejisidir. Bu strateji, trend yönünü belirlemek için PSAR noktalarını kullanırken, ATR ile volatilite bazlı stop-loss ve take-profit seviyeleri belirler. Özellikle güçlü trendlerde yüksek kazanç potansiyeli sunar ve ani fiyat hareketlerine karşı koruma sağlar. Strateji, 15 dakikalık timeframe\'de çalışarak hem kısa vadeli fırsatları yakalar hem de trend devam ederken pozisyonları korur.',
            'description_en': 'The PSAR ATR Strategy is an advanced momentum-based trading strategy that combines Parabolic SAR and Average True Range (ATR) indicators. This strategy uses PSAR points to determine trend direction while employing ATR for volatility-based stop-loss and take-profit levels. It offers high profit potential in strong trends while providing protection against sudden price movements. The strategy operates on 15-minute timeframes, capturing both short-term opportunities and maintaining positions as trends continue.',
            'risk_level': 'Orta',
            'best_performance': 'Güçlü trendlerde'
        },
        {
            'id': 'atr_strategy',
            'name': 'ATR Strategy',
            'name_tr': 'ATR Stratejisi',
            'description_tr': 'ATR Stratejisi, Average True Range göstergesine dayalı volatilite odaklı bir trading yaklaşımıdır. Bu strateji, piyasa volatilitesini analiz ederek optimal giriş ve çıkış noktalarını belirler. ATR değerlerine göre dinamik stop-loss seviyeleri ayarlar ve risk yönetimini volatilite bazlı yapar. Strateji, düşük volatilite dönemlerinde daha konservatif, yüksek volatilite dönemlerinde ise daha agresif pozisyonlar alır. Bu yaklaşım, piyasa koşullarına adapte olarak tutarlı performans sağlar.',
            'description_en': 'The ATR Strategy is a volatility-focused trading approach based on the Average True Range indicator. This strategy analyzes market volatility to determine optimal entry and exit points. It sets dynamic stop-loss levels based on ATR values and implements volatility-based risk management. The strategy takes more conservative positions during low volatility periods and more aggressive positions during high volatility periods. This approach adapts to market conditions to provide consistent performance.',
            'risk_level': 'Düşük-Orta',
            'best_performance': 'Değişken piyasalarda'
        },
        {
            'id': 'eralp_strateji2',
            'name': 'Eralp Strategy 2',
            'name_tr': 'Eralp Strateji 2',
            'description_tr': 'Eralp Strategy 2, özel olarak geliştirilmiş çoklu gösterge tabanlı bir trading stratejisidir. Bu strateji, RSI, MACD, Bollinger Bands ve özel momentum göstergelerini entegre ederek kapsamlı bir piyasa analizi yapar. Sinyal onaylama mekanizması ile yanlış sinyalleri minimize eder ve yüksek doğruluk oranı hedefler. Strateji, hem trend takibi hem de karşı-trend fırsatlarını değerlendirir. Gelişmiş risk yönetimi ve pozisyon boyutlandırma algoritmaları ile maksimum kazanç potansiyeli sunar.',
            'description_en': 'Eralp Strategy 2 is a specially developed multi-indicator based trading strategy. This strategy integrates RSI, MACD, Bollinger Bands, and custom momentum indicators to perform comprehensive market analysis. It minimizes false signals through signal confirmation mechanisms and targets high accuracy rates. The strategy evaluates both trend-following and counter-trend opportunities. It offers maximum profit potential through advanced risk management and position sizing algorithms.',
            'risk_level': 'Orta-Yüksek',
            'best_performance': 'Tüm piyasa koşullarında'
        },
        {
            'id': 'skorlama_strategy',
            'name': 'Skorlama Strategy',
            'name_tr': 'Skorlama Stratejisi',
            'description_tr': 'Skorlama Stratejisi, Pine Script\'teki "Psar ATR With Zone + Donchian + Smart Filter STRATEGY" stratejisinin Python implementasyonudur. Bu strateji, PSAR, ATR Zone, Donchian Channel, EMA 50/200, ADX ve RSI göstergelerini birleştirerek kapsamlı bir skorlama sistemi oluşturur. Minimum 71 skor gerektiren bu strateji, sadece güçlü sinyallerde işlem yapar. Trend durumu, volatilite, hacim ve momentum faktörlerini değerlendirerek yüksek doğruluk oranı hedefler. Adaptive Early Exit sistemi ile trend dönüşlerinde erken çıkış yaparak riski minimize eder.',
            'description_en': 'The Skorlama Strategy is the Python implementation of the "Psar ATR With Zone + Donchian + Smart Filter STRATEGY" from Pine Script. This strategy combines PSAR, ATR Zone, Donchian Channel, EMA 50/200, ADX, and RSI indicators to create a comprehensive scoring system. Requiring a minimum score of 71, this strategy only trades on strong signals. It evaluates trend conditions, volatility, volume, and momentum factors to target high accuracy rates. The Adaptive Early Exit system minimizes risk by exiting early on trend reversals.',
            'risk_level': 'Orta',
            'best_performance': 'Güçlü trendlerde ve yüksek skorlu sinyallerde'
        }
    ]
    
    return render_template('strategies.html', strategies=strategies_info)

@app.route('/request_strategy', methods=['POST'])
@login_required
def request_strategy():
    """Request a strategy via Telegram"""
    strategy_id = request.form.get('strategy_id')
    strategy_name = request.form.get('strategy_name')
    username = current_user.id
    
    try:
        # Import telegram notifier
        from core.telegram.telegram_notifier import TelegramNotifier
        
        # Create telegram message
        message = f"🤖 **Strateji Talebi**\n\n👤 **Kullanıcı:** {username}\n📊 **Talep Edilen Strateji:** {strategy_name}\n⏰ **Tarih:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\nBu kullanıcı yukarıdaki stratejiyi talep etmektedir."
        
        # Send telegram message
        telegram = TelegramNotifier(symbol="GENERAL")
        success = telegram.send_notification(message)
        
        if success:
            flash(f'✅ Strateji talebiniz başarıyla gönderildi: {strategy_name}', 'success')
        else:
            flash(f'❌ Strateji talebi gönderilemedi. Lütfen daha sonra tekrar deneyin.', 'error')
            
    except Exception as e:
        flash(f'❌ Hata oluştu: {str(e)}', 'error')
    
    return redirect(url_for('strategies'))

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
                <button class="nav-link" id="telegram-tab" data-bs-toggle="tab" data-bs-target="#telegram" type="button" role="tab">
                    <i class="fas fa-comments"></i> Telegram
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
            
            <div class="tab-pane fade" id="telegram" role="tabpanel">
                <div class="card">
                    <div class="card-header">
                        <h5>Telegram Messages</h5>
                    </div>
                    <div class="card-body">
                        {% if telegram_data %}
                            <div class="table-responsive">
                                <table class="table table-striped table-sm">
                                    <thead>
                                        <tr>
                                            {% for header in telegram_data[0].keys() %}
                                                <th>{{ header }}</th>
                                            {% endfor %}
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {% for row in telegram_data %}
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
                            <p class="text-muted">No telegram data available.</p>
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
    elif template_name == 'strategies.html':
        return '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Strategies - Trading Bot Dashboard</title>
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
                            <i class="fas fa-list"></i> Trading Bot Strategies
                        </h5>
                    </div>
                    <div class="card-body">
                        <div class="row">
                            {% for strategy in strategies %}
                            <div class="col-md-6 col-lg-4 mb-4">
                                <div class="card h-100">
                                    <div class="card-header d-flex justify-content-between align-items-center">
                                        <h6 class="mb-0">
                                            <i class="fas fa-coins"></i> {{ strategy.name }}
                                        </h6>
                                        <span class="badge bg-{{ 'success' if strategy.running else 'secondary' }}">
                                            <i class="fas fa-{{ 'play' if strategy.running else 'stop' }}"></i>
                                            {{ 'Running' if strategy.running else 'Stopped' }}
                                        </span>
                                    </div>
                                    <div class="card-body">
                                        <p class="card-text">
                                            <strong>Description:</strong> {{ strategy.description_tr }}<br>
                                            {% if strategy.process_info %}
                                                <strong>PID:</strong> {{ strategy.process_info.pid }}<br>
                                                <strong>Memory:</strong> {{ strategy.process_info.memory_mb }} MB<br>
                                                <strong>Started:</strong> {{ strategy.process_info.start_time }}
                                            {% endif %}
                                        </p>
                                        
                                        {% if strategy.running %}
                                            <form method="POST" action="/stop_script" class="d-inline">
                                                <input type="hidden" name="script_name" value="{{ strategy.filename }}">
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
                                        
                                        <a href="/logs/{{ strategy.coin }}" class="btn btn-info btn-sm">
                                            <i class="fas fa-file-alt"></i> Logs
                                        </a>
                                    </div>
                                </div>
                            </div>

                            <!-- Start Modal for each strategy -->
                            <div class="modal fade" id="startModal{{ loop.index }}" tabindex="-1">
                                <div class="modal-dialog">
                                    <div class="modal-content">
                                        <div class="modal-header">
                                            <h5 class="modal-title">Start {{ strategy.name }} Bot</h5>
                                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                                        </div>
                                        <form method="POST" action="/start_script">
                                            <div class="modal-body">
                                                <input type="hidden" name="script_name" value="{{ strategy.filename }}">
                                                
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