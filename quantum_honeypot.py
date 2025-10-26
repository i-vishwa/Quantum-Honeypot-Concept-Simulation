"""
Quantum Honeypot Simulation GUI
- PyQt6 + matplotlib
- Shows a timeline graph of quantum state (collapsed values after measurement)
- Logs intrusion attempts and measurement events
- Auto-intrusion mode simulates external attackers
"""

import sys
import random
import time
from collections import deque

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QCheckBox, QSpinBox, QMessageBox
)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QTextCursor
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# --- Simulation parameters ---
QSTATES = ["|0⟩", "|1⟩", "|+⟩", "|-⟩"]
MEASURE_OUTCOMES = ["0", "1"]

class QuantumHoneypotModel:
    """Simple model representing a quantum data cell and event logic."""
    def __init__(self):
        self.reset()

    def reset(self):
        self.quantum_state = random.choice(QSTATES)   # abstract pre-measurement state
        self.collapsed = False
        self.collapsed_value = None   # "0" or "1" after measurement
        self.time = 0.0

    def measure(self):
        """Simulate measurement: collapse to 0/1 randomly (50/50)."""
        if not self.collapsed:
            self.collapsed_value = random.choice(MEASURE_OUTCOMES)
            self.collapsed = True
            return self.collapsed_value
        else:
            # repeated measurement returns same collapsed value
            return self.collapsed_value

    def intrusion_attempt(self):
        """
        An intrusion attempt triggers measurement (if not measured).
        Return tuple (measured_now(bool), outcome_or_none).
        """
        if not self.collapsed:
            outcome = self.measure()
            return True, outcome
        else:
            # already collapsed — intrusion still detected but no new collapse
            return False, self.collapsed_value


# --- GUI / Visualization ---
class TimelineCanvas(FigureCanvas):
    """Matplotlib canvas showing timeline of state values and intrusion markers."""
    def __init__(self, max_points=200):
        fig = Figure(figsize=(6, 3), tight_layout=True)
        super().__init__(fig)
        self.ax = fig.add_subplot(111)
        self.max_points = max_points
        self.clear()

    def clear(self):
        self.times = deque(maxlen=self.max_points)
        self.values = deque(maxlen=self.max_points)  # numeric: 0, 1, np.nan for unknown
        self.intrusion_times = []  # list of (t, value_if_known_or_nan)
        self.ax.clear()
        self.ax.set_ylim(-0.2, 1.2)
        self.ax.set_yticks([0, 0.5, 1])
        self.ax.set_yticklabels(["0", "?", "1"])
        self.ax.set_xlabel("Time (s)")
        self.ax.set_title("Quantum Honeypot Timeline (collapsed values after measurement)")
        self.draw()

    def append(self, t, value):
        self.times.append(t)
        self.values.append(value)
        self._redraw()

    def mark_intrusion(self, t, value_at_t):
        self.intrusion_times.append((t, value_at_t))
        self._redraw()

    def _redraw(self):
        self.ax.clear()
        self.ax.set_ylim(-0.2, 1.2)
        self.ax.set_yticks([0, 0.5, 1])
        self.ax.set_yticklabels(["0", "?", "1"])
        self.ax.set_xlabel("Time (s)")
        self.ax.set_title("Quantum Honeypot Timeline (collapsed values after measurement)")

        if len(self.times) > 0:
            times = np.array(self.times)
            values = np.array(self.values)
            known_mask = ~np.isnan(values)
            unknown_mask = np.isnan(values)
            if known_mask.any():
                self.ax.step(times[known_mask], values[known_mask], where="post", color="tab:blue", linewidth=2, label="collapsed value")
                self.ax.scatter(times[known_mask], values[known_mask], color="tab:blue", zorder=3)
            if unknown_mask.any():
                self.ax.plot(times[unknown_mask], np.full(np.sum(unknown_mask), 0.5), linestyle="--", color="gray", label="unknown (pre-measurement)")
            for t, v in self.intrusion_times:
                marker_y = 0.05 if np.isnan(v) else v
                self.ax.plot(t, marker_y, marker="x", color="red", markersize=9, mew=2)
                self.ax.annotate("intrusion", (t, marker_y), textcoords="offset points", xytext=(0,8), ha="center", color="red", fontsize=8)
            self.ax.legend(loc="upper right")
        self.draw()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Quantum Honeypot Simulation")
        self.setMinimumSize(900, 600)

        # Model
        self.model = QuantumHoneypotModel()
        self.start_time = time.time()

        # Central widget/layout
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout()
        central.setLayout(main_layout)

        # Top controls
        control_layout = QHBoxLayout()
        main_layout.addLayout(control_layout)

        self.state_label = QLabel(f"Quantum Data: {self.model.quantum_state} (pre-measurement)")
        self.state_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        control_layout.addWidget(self.state_label, stretch=3)

        self.measure_btn = QPushButton("Measure Quantum Data")
        self.measure_btn.clicked.connect(self.on_measure)
        control_layout.addWidget(self.measure_btn, stretch=1)

        self.intrude_btn = QPushButton("Simulate Intrusion")
        self.intrude_btn.clicked.connect(self.on_intrusion)
        control_layout.addWidget(self.intrude_btn, stretch=1)

        self.reset_btn = QPushButton("Reset System")
        self.reset_btn.clicked.connect(self.on_reset)
        control_layout.addWidget(self.reset_btn, stretch=1)

        # Auto intrusion controls
        auto_layout = QHBoxLayout()
        self.auto_checkbox = QCheckBox("Auto intrusion (every N sec)")
        self.auto_checkbox.stateChanged.connect(self.on_auto_changed)
        auto_layout.addWidget(self.auto_checkbox)
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 60)
        self.interval_spin.setValue(5)
        auto_layout.addWidget(self.interval_spin)
        control_layout.addLayout(auto_layout)

        # Graphical timeline
        self.canvas = TimelineCanvas(max_points=400)
        main_layout.addWidget(self.canvas, stretch=3)

        # Log area
        log_label = QLabel("Security Log:")
        main_layout.addWidget(log_label)
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        main_layout.addWidget(self.log_box, stretch=2)

        # Timer for periodic updates
        self.ui_timer = QTimer()
        self.ui_timer.setInterval(500)
        self.ui_timer.timeout.connect(self._ui_tick)
        self.ui_timer.start()

        # Auto intrusion timer
        self.auto_timer = QTimer()
        self.auto_timer.timeout.connect(self.on_intrusion)

        # initialize
        self._append_graph(np.nan)
        self._log("System initialized. Quantum state set to " + self.model.quantum_state)

    # ----- Helpers -----
    def _current_time(self):
        return round(time.time() - self.start_time, 2)

    def _append_graph(self, value):
        t = self._current_time()
        self.canvas.append(t, value)

    def _log(self, text):
        tstr = time.strftime("%H:%M:%S")
        self.log_box.append(f"[{tstr}] {text}")
        # Fix for PyQt6: Move cursor to end correctly
        self.log_box.moveCursor(QTextCursor.MoveOperation.End)

    # ----- UI actions -----
    def on_measure(self):
        outcome = self.model.measure()
        self.state_label.setText(f"Quantum Data: collapsed → {outcome}")
        self._log(f"Measurement performed: collapsed to {outcome}.")
        self._append_graph(int(outcome))

    def on_intrusion(self):
        measured_now, outcome = self.model.intrusion_attempt()
        t = self._current_time()
        if measured_now:
            self.state_label.setText(f"Quantum Data: collapsed by intrusion → {outcome}")
            self._log(f"⚠ Intrusion: triggered collapse to {outcome}.")
            self.canvas.mark_intrusion(t, int(outcome))
            self._append_graph(int(outcome))
        else:
            self._log(f"⚠ Intrusion detected (post-collapse). Value remains {outcome}.")
            self.canvas.mark_intrusion(t, int(outcome))
        QMessageBox.warning(self, "Intrusion Alert", "Unauthorized access detected!\nQuantum trap triggered.")

    def on_reset(self):
        self.model.reset()
        self.state_label.setText(f"Quantum Data: {self.model.quantum_state} (pre-measurement)")
        self._log("System reset. Quantum state reinitialized.")
        self.canvas.clear()
        self._append_graph(np.nan)

    def on_auto_changed(self, state):
        if state == Qt.CheckState.Checked:
            interval = self.interval_spin.value() * 1000
            self.auto_timer.start(interval)
            self._log(f"Auto intrusion enabled every {self.interval_spin.value()} s.")
        else:
            self.auto_timer.stop()
            self._log("Auto intrusion disabled.")

    def _ui_tick(self):
        if self.model.collapsed:
            val = int(self.model.collapsed_value)
        else:
            val = np.nan
        self._append_graph(val)


# Entry point
def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
