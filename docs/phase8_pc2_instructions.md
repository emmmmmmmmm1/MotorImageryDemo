# Phase 8 PC2 Instructions

Phase 8 is the first real Emotiv calibration pass. Phase 7 proved the Unity,
Python service, LSL command/status/probability streams, and bundle saving work
with dummy EEG. The next goal is to replace dummy EEG with the real Emotiv EEG
stream and confirm calibration can finish with an acceptable CV score.

Current code path:

- Unity runs on PC2.
- Python service runs on PC2.
- Emotiv/LSL stream is read by Python service.
- Current Python receiver supports the EPOC X-shaped stream: 19 total channels,
  14 EEG channels, then select `FC5 FC6` with `--channels FC5 FC6`.
- Do not commit generated `data/`, `bundles/`, or `logs/` files.

## Goal

Finish Phase 8.1 to 8.3:

- Emotiv EEG stream is visible over LSL.
- `python -m apps.service --channels FC5 FC6` connects to the real stream.
- Unity calibration reaches `state:READY`.
- Pressing `Save Bundle` writes `bundles/pc2_test_*.joblib`.
- Trial-level GroupKFold accuracy is at least `0.60`.

If accuracy is below `0.60`, Phase 8.4 starts.

## Before Starting

On PC2:

```powershell
cd C:\Users\yuta0\Projects\MotorImageryDemo
git pull
conda activate MotorImageryDemo
pytest -q
```

Expected:

```text
100% passed
```

If Unity files changed after opening Unity, check:

```powershell
git status --short
```

Only commit source/config files. Do not commit:

- `data/`
- `bundles/`
- `logs/`
- `Library/`
- `Temp/`
- `UserSettings/`
- `.csproj`
- `.sln`
- `.slnx`

## 8.1 Emotiv LSL Stream Check

1. Start the Emotiv app that exposes LSL.
2. Wear the headset and confirm signal quality is stable.
3. Enable the EEG LSL outlet in the Emotiv app.
4. In PC2 terminal:

```powershell
conda activate MotorImageryDemo
python realTimePlotEmotivLSL.py
```

Expected:

- The script finds the Emotiv EEG stream.
- EEG traces move continuously.
- Signal is not flat, saturated, or full of huge spikes.

If this script cannot find the stream:

- Confirm the Emotiv app is still running.
- Confirm LSL outlet/export is enabled.
- Restart the Emotiv app.
- Restart the terminal and try again.
- Do not move to 8.2 until the stream is visible.

## 8.2 Python Service Connection Check

Keep the Emotiv LSL stream running.

In a terminal on PC2:

```powershell
cd C:\Users\yuta0\Projects\MotorImageryDemo
conda activate MotorImageryDemo
python -m apps.service --channels FC5 FC6
```

Expected log near startup:

```text
EEGReceiver connected: {... 'n_channels': 2, 'channel_names': ['FC5', 'FC6'], ...}
MarkerReceiver connected to type=Markers
CommandReceiver connected to type=Commands
status: state:IDLE
```

Important:

- If it says `No LSL stream of type='Markers'`, start Unity Play first, then
  rerun the service.
- If it says `No LSL stream of type='Commands'`, start Unity Play first, then
  rerun the service.
- If it says the EEG layout is unexpected, copy the full `EEGReceiver connected`
  or error log and stop. The receiver code may need to support that Emotiv
  stream layout before calibration.

## 8.3 Real Calibration With Unity

Use two PC2 windows:

- Unity Editor
- PowerShell terminal running `apps.service`

Steps:

1. Open Unity project:

```text
C:\Users\yuta0\Projects\MotorImageryDemo\unity\MotorImageryUnity
```

2. Open `Assets/MainMenu.unity`.
3. Press Play in Unity.
4. Start the service after Unity Play is active:

```powershell
cd C:\Users\yuta0\Projects\MotorImageryDemo
conda activate MotorImageryDemo
python -m apps.service --channels FC5 FC6
```

5. Wait until Unity shows:

```text
state:IDLE
```

6. Press `Start Calibration` in Unity.
7. Follow the cue text:

- `LEFT`: imagine left-hand movement.
- `RIGHT`: imagine right-hand movement.
- `REST`: relax and avoid movement.

Do not press keys, click around, talk, move shoulders, blink hard, or adjust the
headset during trials if avoidable.

8. Wait for:

```text
Calibration 40 / 40
state:TRAINING
calibration_done:acc=...
state:READY
```

9. Press `Save Bundle` in Unity.

Expected service log:

```text
cmd: save_bundle {'subject': 'pc2_test'}
status: bundle_saved:path=C:\Users\yuta0\Projects\MotorImageryDemo\bundles\pc2_test_YYYYMMDDTHHMMSSZ.joblib
```

10. Confirm the bundle exists:

```powershell
dir bundles\pc2_test_*.joblib
```

## Pass Criteria

Phase 8.3 passes if:

- Calibration reaches `state:READY`.
- `bundle_saved:path=...pc2_test_*.joblib` appears.
- `calibration_done:acc=...` is `0.60` or higher.

Example pass:

```text
status: calibration_done:acc=0.650
status: state:READY
status: bundle_saved:path=...\bundles\pc2_test_*.joblib
```

## If Accuracy Is Below 0.60

This is not a code failure. Move to Phase 8.4.

Record these values:

- `calibration_done:acc=...`
- headset/contact quality
- whether FC5/FC6 looked clean in `realTimePlotEmotivLSL.py`
- whether you moved, blinked, or adjusted the headset during trials

Then try one improvement at a time:

1. Re-seat the headset/electrodes and improve contact quality.
2. Repeat calibration once with the same settings.
3. If still low, try calmer, more consistent motor imagery.
4. If still low, ask Codex to adjust calibration settings, for example longer
   MI duration or a different bandpass.

Do not change several things at once, because then we cannot tell what helped.

## After The Test

Stop running processes with `Ctrl + C`.

Check git:

```powershell
git status --short
```

Usually, `data/`, `bundles/`, and `logs/` should not be committed.

If source files changed intentionally:

```powershell
git add <changed-source-files>
git commit -m "Describe the Phase 8 change"
git push origin main
```

Send Codex:

- `calibration_done:acc=...`
- `bundle_saved:path=...`
- `git status --short`
- any red Unity Console errors, if present
