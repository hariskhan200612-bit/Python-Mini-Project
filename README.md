# THERMALIQ EV — Battery Thermal Management Dashboard

## Run
1. Install Python 3.9 or newer.
2. Save `battery_thermal_dashboard.py` to your computer.
3. Run in a terminal:
   ```bash
   python battery_thermal_dashboard.py
   ```
   On some systems, use `python3 battery_thermal_dashboard.py`.
4. Tkinter is usually included with standard Python. On Linux, you may need your distribution's `python3-tk` package.
5. The app creates `thermaliq_battery.db` automatically beside the Python script on first run. SQLite is included with standard Python; no separate database server or package installation is required.
6. Keep `thermaliq_battery_dataset.csv` in the same folder as the script to use the supplied sample dataset.

## Features
- Enhanced dark-theme Tkinter dashboard with Overview, Live Monitor, Thermal History, Alerts & Insights, and System Info pages.
- Simulated sensor inputs: battery temperature, coolant temperature, current, voltage, state of charge, and coolant flow.
- Six live metric cards, temperature trend chart, thermal diagnostics, Normal / Warning / Critical classification, and cooling recommendations.
- Manual sensor input with validation, random sample button, threaded live simulation, preset thermal scenarios, recent-event panel, keyboard shortcuts, and CSV export.
- OOP concepts: classes, objects, encapsulation, inheritance, abstraction, polymorphism, method overriding.
- Python collections and functional programming: list, tuple, dictionary, set, lambda, map, filter, reduce.
- SQLite persistence via Python’s built-in `sqlite3`: every processed reading and thermal decision is saved in `thermaliq_battery.db` and restored when the app restarts.
- String formatting, exception handling, `threading`, `queue`, and modular class design.

## Controls guide

See `CONTROLS_GUIDE.md` for explanations of every navigation item and button, keyboard shortcuts, sensor fields, dictionary keys, and the thermal decision rules.

## Important limitation
This is an educational simulation with illustrative, rule-based thresholds. It does not use a trained AI model, does not connect to actual battery sensors, and must not be used to control or assess a real electric vehicle battery. Real thermal management requires validated electro-thermal models, calibrated sensors, hardware safeguards, and engineering review.

## Suggested demo for evaluation
1. Open **Overview** and explain the six sensor cards, trend chart, and thermal diagnostics.
2. Start **Simulation** to demonstrate background sensor updates.
3. Open **Live Monitor** and enter a battery temperature such as 36, 41, then 47 °C to show Normal, Warning, and Critical states.
4. Open **Alerts & Insights** and click Normal, Warning, and Critical scenarios to demonstrate all three states.
5. Open **Thermal History** and show timestamped entries, then export the history as CSV.
6. Open **System Info** to explain how the OOP experiments map to the project. See `CONTROLS_GUIDE.md` for the keyboard shortcuts and button-by-button explanation.
