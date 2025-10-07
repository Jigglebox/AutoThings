# Trade Automation Tool

This project automates trade interactions by combining fast screen capture (`mss`), OpenCV-based detection, and simulated input.

## Quick Start

1. Create and activate a Python 3.9+ virtual environment.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Update `config.json` to match your screen layout:
   - Adjust `monitor` bounds to the display you want to capture.
   - For each `trade` entry, set the rectangular `region` containing the gem icon and `start_button` coordinates to click.
   - Place template PNGs (e.g., `templates/start_enabled.png`) relative to the config file if you plan to use template matching.

4. Launch the tool:

   ```bash
   python Auto.py
   ```

   - GUI opens by default (falls back to headless mode if Tkinter is unavailable).
   - Use the configured hotkeys (default `F9` to pause/resume, `F10` to stop the automation loop entirely).

## Headless Mode

Run without GUI:

```bash
python Auto.py --no-gui
```

## Windows Executable

Run the bundled build script to create a standalone `.exe` (PyInstaller required):

```powershell
./build_exe.ps1
```

The executable and supporting files are placed under `dist/`. Edit `dist/config.json` (and copy any template PNGs into `dist/templates/`) before launching `dist/TradeAutomation.exe`. Logs are written next to the executable as `automation.log`.

## Configuration Notes

- `hsv_ranges` defines the red color mask in HSV space. Two entries handle the wraparound for red hues.
- `red_ratio_threshold` controls how much red must be present before a trade is considered a match.
- `timing` values are in seconds.
- `clicks.use_win32` toggles direct Win32 clicks (requires `pywin32`).

Logs are written to `automation.log` in the project directory.
