"""
Logging System for SDLC Agent
SDLCLogger is now a unified wrapper around RealtimeLogger so both the
standard Python logging interface and the real-time JSON status file
are available from a single object.
"""

import logging
import os
from datetime import datetime
from pathlib import Path

from tools.realtime_logger import RealtimeLogger


class SDLCLogger:
    """
    Unified logger that combines:
    - Standard Python logging (file + console, structured format)
    - RealtimeLogger (live JSON status file for the Streamlit dashboard)

    Usage is identical to the original SDLCLogger API.
    """

    def __init__(self, logs_dir: str, output_dir: str = None):
        self.logs_dir = logs_dir
        Path(logs_dir).mkdir(parents=True, exist_ok=True)

        # ── Standard Python logger ────────────────────────────────────
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = os.path.join(logs_dir, f"sdlc_run_{timestamp}.log")

        self._logger = logging.getLogger("SDLC_Agent")
        self._logger.setLevel(logging.DEBUG)

        if not self._logger.handlers:          # avoid duplicate handlers on reload
            fh = logging.FileHandler(self.log_file, encoding='utf-8')
            fh.setLevel(logging.DEBUG)

            ch = logging.StreamHandler()
            ch.setLevel(logging.INFO)

            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            fh.setFormatter(formatter)
            ch.setFormatter(formatter)

            self._logger.addHandler(fh)
            self._logger.addHandler(ch)

        # ── RealtimeLogger (JSON status file for dashboard) ───────────
        _output_dir = output_dir or os.path.dirname(logs_dir)
        self._realtime = RealtimeLogger(_output_dir)

    # ── Standard logging interface ────────────────────────────────────

    def info(self, message: str):
        self._logger.info(message)

    def debug(self, message: str):
        self._logger.debug(message)

    def warning(self, message: str):
        self._logger.warning(message)

    def error(self, message: str):
        self._logger.error(message)

    def success(self, message: str, duration: float = None):
        """Log a successful step with optional duration."""
        msg = f"✅ {message} (completed in {duration:.1f}s)" if duration else f"✅ {message}"
        self._logger.info(msg)
        print(msg)

    def step(self, agent_name: str, action: str):
        """Log the start of an agent step."""
        msg = f"▶️  [{agent_name}] {action}"
        self._logger.info(msg)
        print(msg)

    def get_log_file_path(self) -> str:
        return self.log_file

    # ── RealtimeLogger passthrough (for dashboard compatibility) ──────

    def log(self, agent: str, message: str):
        """Write a timestamped line to the real-time log file and update status JSON."""
        self._realtime.log(agent, message)
        self._logger.info(f"[{agent}] {message}")

    def set_running_agents(self, agents: list):
        self._realtime.set_running_agents(agents)

    def set_completed_agents(self, agents: list):
        self._realtime.set_completed_agents(agents)

    def set_iteration(self, iteration: int):
        self._realtime.set_iteration(iteration)
