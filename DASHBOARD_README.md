# Trading Bot Dashboard

A secure Flask web dashboard for managing trading bot scripts with authentication, process management, and log viewing capabilities.

## Features

- 🔐 **Secure Authentication**: Basic authentication with username/password
- 🤖 **Script Management**: Start/stop trading bot scripts
- ⚙️ **Configurable Parameters**: Set leverage and trade amount for each script
- 📊 **Real-time Monitoring**: View running processes and system resources
- 📈 **Log Viewing**: View trades, positions, and application logs
- 🔄 **Auto-refresh**: Automatic status updates every 10 seconds
- 📱 **Responsive Design**: Works on desktop and mobile devices

## Installation

1. **Install Dependencies**:
   ```bash
   pip install -r dashboard_requirements.txt
   ```

2. **Run the Dashboard**:
   ```bash
   python3 dashboard.py
   ```

3. **Access the Dashboard**:
   - URL: `http://46.101.3.218:5000`
   - Username: `eralptest`
   - Password: `eralptest`

## Configuration

### Base Path
The dashboard scans for scripts in `/root/test_coinmatik/yeni_strateji2`

### Logs Path
Log files are read from `/root/test_coinmatik/yeni_strateji2/logs`

### Default Parameters
- **Leverage**: 10 (configurable per script)
- **Trade Amount**: 200 (configurable per script)

## Usage

### 1. Dashboard Overview
- View all available `main_*.py` scripts
- See running status and process information
- Monitor memory usage and start times

### 2. Starting Scripts
1. Click the "Start" button for any stopped script
2. Configure leverage and trade amount in the modal
3. Click "Start Bot" to launch the script

### 3. Stopping Scripts
1. Click the "Stop" button for any running script
2. The script will be terminated gracefully

### 4. Viewing Logs
1. Click the "Logs" button for any script
2. View three types of data:
   - **Trades**: CSV data from `psar_trades_<coin>.csv`
   - **Positions**: CSV data from `psar_positions_<coin>.csv`
   - **Logs**: Last 300 lines from `main_<coin>.log`

## File Structure

```
dashboard.py                 # Main Flask application
templates/
├── dashboard.html          # Main dashboard page
├── login.html             # Login page
└── logs.html              # Logs viewing page
dashboard_requirements.txt  # Python dependencies
DASHBOARD_README.md        # This file
```

## Security Features

- **Authentication Required**: All pages require login
- **Session Management**: Secure session handling
- **Process Isolation**: Each script runs in its own process
- **Input Validation**: All form inputs are validated

## API Endpoints

- `GET /` - Main dashboard
- `GET /login` - Login page
- `POST /login` - Login authentication
- `GET /logout` - Logout
- `POST /start_script` - Start a script
- `POST /stop_script` - Stop a script
- `GET /logs/<coin>` - View logs for specific coin
- `GET /api/process_status` - Get process status (JSON)

## Process Management

### Starting Scripts
- Uses `subprocess.Popen()` for process creation
- Sets proper working directory and environment
- Captures stdout/stderr for debugging

### Stopping Scripts
- Graceful termination with `process.terminate()`
- Force kill if needed with `process.kill()`
- Automatic cleanup of finished processes

### Monitoring
- Real-time process status using `psutil`
- Memory usage tracking
- Process start time recording

## Log File Formats

### Trade CSV Format
Expected columns in `psar_trades_<coin>.csv`:
- Date/Time
- Symbol
- Action
- Direction
- Quantity
- Price
- Details

### Position CSV Format
Expected columns in `psar_positions_<coin>.csv`:
- Timestamp
- Symbol
- Position Type
- Entry Price
- Exit Price
- Price Change %
- Leveraged PnL %
- Status

### Log File Format
Application logs from `main_<coin>.log`:
- Standard Python logging output
- Last 300 lines displayed
- Real-time updates

## Troubleshooting

### Common Issues

1. **Scripts not found**:
   - Check if `/root/test_coinmatik/yeni_strateji2` exists
   - Verify `main_*.py` files are present

2. **Permission denied**:
   - Ensure proper file permissions
   - Check if user can execute Python scripts

3. **Logs not showing**:
   - Verify log files exist in `/root/test_coinmatik/yeni_strateji2/logs`
   - Check file permissions

4. **Process not starting**:
   - Check Python path and dependencies
   - Verify script syntax and imports

### Debug Mode
To enable debug mode, change the last line in `dashboard.py`:
```python
app.run(host='0.0.0.0', port=5000, debug=True)
```

## Customization

### Changing Authentication
Edit the login route in `dashboard.py`:
```python
if username == 'your_username' and password == 'your_password':
```

### Adding New Script Types
Modify the `scan_scripts()` function to detect different patterns:
```python
if file.startswith('your_prefix_') and file.endswith('.py'):
```

### Customizing UI
Edit the HTML templates in the `templates/` directory:
- `dashboard.html` - Main dashboard
- `login.html` - Login page
- `logs.html` - Logs viewing

## Performance

- **Auto-refresh**: 10-second intervals for status updates
- **Process Monitoring**: Efficient process tracking with `psutil`
- **Log Reading**: Optimized file reading with line limits
- **Memory Usage**: Minimal memory footprint

## Security Considerations

- Change default credentials in production
- Use HTTPS in production environments
- Implement rate limiting for API endpoints
- Add IP whitelisting if needed
- Regular security updates for dependencies

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review log files for error messages
3. Verify file permissions and paths
4. Test with debug mode enabled 