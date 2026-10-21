# THERMALIQ EV — Interface Controls and Keyboard Guide

## 1. Main navigation

- **Overview** — shows six live metric cards, current thermal status, a battery-temperature trend chart, average/peak temperature, thermal score, and simulated cooling demand.
- **Live Monitor** — lets you enter six sensor values manually or populate them with a generated sample, then run an analysis.
- **Thermal History** — displays saved readings in reverse chronological order and exports them as a CSV file. Readings are stored in SQLite and persist after closing the application.
- **Alerts & Insights** — explains the Normal/Warning/Critical rules, shows the latest assessment and recent events, and provides preset scenarios for a project demonstration.
- **System Info** — summarizes the project, OOP design, Python collections, thresholds, controls, and shortcuts.

## 2. Sidebar buttons

| Button | Function |
|---|---|
| **Start Simulation** | Starts a background worker that generates a new simulated sensor sample about every two seconds. The dashboard processes those samples and updates the analysis/history. |
| **Stop Simulation** | Stops future automatic samples. Existing readings and event history remain visible. |
| **New Sensor Sample** | Generates and processes one sample immediately; it does not require continuous simulation to be running. |
| **Export CSV** | Opens a Save dialog and writes the recorded session events to a `.csv` file that can be opened in Excel or similar spreadsheet software. |

## 3. Live Monitor controls

The six input fields are:

- **Battery temperature (°C):** battery pack temperature; this is the main input to thermal classification.
- **Coolant temperature (°C):** temperature of the cooling liquid in the illustrative model.
- **Battery current (A):** simulated electrical current.
- **Battery voltage (V):** simulated pack voltage.
- **State of charge (%):** estimated remaining charge, constrained to 0–100%.
- **Coolant flow (L/min):** illustrative liquid flow through the micro-channels.

**Analyze Entered Values** validates the entries, processes them, updates the dashboard and history, and displays a detailed report. Blank, non-numeric, non-finite, or out-of-range values produce an error dialog instead of being accepted.

**Load Random Sample** generates a sample, fills the six input fields, and analyzes it immediately.

## 4. Alerts & Insights scenario buttons

- **Normal · 34°C** loads a safe-looking example for the normal status.
- **Warning · 41°C** loads a higher-temperature example to demonstrate the warning advisory.
- **Critical · 47°C** loads a high-temperature example to demonstrate the critical advisory.

These are preset demonstration cases, not real battery tests. The program updates the dashboard, history, and recent-event panel when a scenario is selected.

## 5. Keyboard shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl + 1` | Open Overview |
| `Ctrl + 2` | Open Live Monitor |
| `Ctrl + 3` | Open Thermal History |
| `Ctrl + 4` | Open Alerts & Insights |
| `Ctrl + 5` | Open System Info |
| `Ctrl + E` | Export session history to CSV |
| `N` | Generate one new sensor sample |
| `Space` | Start the simulation, or stop it if it is already running |
| `F1` | Open System Info |

Shortcuts are designed for quick navigation/demo. On Windows/Linux, use `Ctrl`; on macOS, use `Command` for the modifier shortcuts. They are ignored while typing into text-entry fields; Space is also ignored when a button has keyboard focus.

## 6. Meaning of the sensor dictionary keys in the code

Each reading is stored in a Python dictionary. The key is the label used to retrieve a value:

| Key | Meaning | Unit |
|---|---|---|
| `battery_temp` | Battery pack temperature | °C |
| `coolant_temp` | Coolant temperature | °C |
| `current` | Battery current | A |
| `voltage` | Battery voltage | V |
| `soc` | State of charge | % |
| `coolant_flow` | Coolant flow rate | L/min |
| `timestamp` | Date and time when the reading was stored | date/time |
| `status` | Rule-based category: Normal, Warning, or Critical | text |
| `thermal_score` | Illustrative score derived from temperature and temperature gap | score |
| `average_temp` | Mean of stored battery temperature samples | °C |
| `cooling_action` | Suggested response for the current thermal category | text |

For example, `reading["battery_temp"]` retrieves the battery-temperature value from a reading dictionary. These dictionary keys are not keyboard keys.

## 7. Thermal decision logic

- **Normal:** battery temperature is below 38°C and the calculated thermal score has not reached the warning threshold.
- **Warning:** battery temperature is at least 38°C, or the score reaches 39.
- **Critical:** battery temperature is at least 45°C, or the score reaches 46.

The score is calculated as battery temperature plus 25% of any positive difference between battery temperature and coolant temperature. Normal recommends no cooling; Warning recommends increased coolant flow; Critical recommends maximum cooling and inspection.

## 8. Important limitation

All sensor values are simulated, and the threshold logic is a transparent educational rule-based demonstration. It is not a trained AI model, not a validated physical battery model, and not suitable for controlling a real electric vehicle.


## 9. SQLite database

The app automatically creates `thermaliq_battery.db` beside the Python script. The `thermal_readings` table stores the timestamp, six sensor values, thermal status, thermal score, average temperature, and cooling recommendation for each processed reading. The dashboard restores saved readings on the next launch. To reset the stored history, close the app and delete `thermaliq_battery.db`; it will be recreated on the next launch. Export CSV remains available for sharing or spreadsheet analysis.
