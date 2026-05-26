# File: tools/realtime_logger.py

import json
from pathlib import Path
from datetime import datetime
import threading

class RealtimeLogger:
    """Write logs to file in real-time with auto-flush"""
    
    def __init__(self, output_dir='output'):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.logs_dir = self.output_dir / 'logs'
        self.logs_dir.mkdir(exist_ok=True)
        
        # Log file
        self.log_file = self.logs_dir / f'sdlc_run_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        
        # Status file (for UI to read)
        self.status_file = self.output_dir / 'current_status.json'
        
        # Initialize
        self.current_status = {
            'timestamp': datetime.now().isoformat(),
            'iteration': 0,
            'running_agents': [],
            'completed_agents': [],
            'last_message': ''
        }
        
        self._write_status()
    
    def log(self, agent: str, message: str):
        """Log message and flush to file immediately"""
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"{timestamp} - [{agent}] {message}"
        
        # Write to file with immediate flush
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_message + '\n')
            f.flush()  # Force write to disk
        
        # Update current status
        self.current_status['timestamp'] = datetime.now().isoformat()
        self.current_status['last_message'] = message
        self._write_status()
        
        # Also print to console (encode safely for Windows terminals)
        print(log_message.encode('utf-8', errors='replace').decode('utf-8', errors='replace'))
    
    def set_running_agents(self, agents: list):
        """Set which agents are currently running"""
        self.current_status['running_agents'] = agents
        self._write_status()
    
    def set_completed_agents(self, agents: list):
        """Set which agents are completed"""
        self.current_status['completed_agents'] = agents
        self._write_status()
    
    def set_iteration(self, iteration: int):
        """Set current iteration number"""
        self.current_status['iteration'] = iteration
        self._write_status()
    
    def _write_status(self):
        """Write current status to JSON file for UI to read"""
        with open(self.status_file, 'w', encoding='utf-8') as f:
            json.dump(self.current_status, f)
            f.flush()

    def clear_on_complete(self):
        """Call at end of run — clears running_agents so UI shows correct final state."""
        self.current_status['running_agents'] = []
        self._write_status()
