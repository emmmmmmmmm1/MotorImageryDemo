# Unity Phase 6

Expected Unity project path:

```text
unity/MotorImageryUnity
```

The Phase 6 bridge script lives at:

```text
unity/MotorImageryUnity/Assets/Scripts/BciLslPanel.cs
```

## Fresh PC setup

This repo is meant to be portable across PCs. Commit Unity source/config files,
then let each PC regenerate its own `Library`, `Temp`, `UserSettings`, `.csproj`,
and `.slnx` files.

1. Install Unity `6000.4.5f1` or open the project with a compatible Unity 6
   editor.
2. Clone or pull this repo.
3. Open `unity/MotorImageryUnity` in Unity Hub.
4. Wait for Package Manager to restore packages from `Packages/manifest.json`
   and `Packages/packages-lock.json`.
5. Confirm LSL4Unity is installed. If Package Manager did not restore it, add:
   `https://github.com/labstreaminglayer/LSL4Unity.git`
6. Open `Assets/MainMenu.unity`.
7. Confirm `BciLslPanel` is attached to `Canvas` and these fields are assigned:
   - `StatusText`
   - `LeftProbaText`
   - `RightProbaText`
   - `StartCalibrationButton`
   - `ShutdownButton`
8. Press Play once and check that the Unity Console has no red compile errors.

## Smoke tests

Run from the repository root in a `MotorImageryDemo` conda environment.

### BCI_Proba display

Start Unity Play, then run:

```powershell
python scripts/dev_lsl_loopback.py --duration-s 30
```

Expected Unity Console messages include:

```text
Connected to BCI_Proba stream: LoopbackProba
```

Expected UI:

```text
p_left: 0.xxx
p_right: 0.xxx
```

### Commands button

Terminal 1:

```powershell
python scripts/dev_fake_lsl_stream.py --mode alternating
```

Terminal 2:

```powershell
python scripts/dev_fake_markers.py --trials-per-class 2 --cue-s 10 --mi-s 1.5 --rest-s 0.4
```

Start Unity Play.

Terminal 3:

```powershell
python -m apps.service --channels FC5 FC6
```

When Unity shows `state:IDLE`, press the `Shutdown` button. The service should
log `cmd: shutdown {}` and then `service stopped`.

### Calibration markers

`BciLslPanel` publishes a Unity `Markers` stream while Play is running. Pressing
`StartCalibrationButton` sends:

```text
start_calibration:subject=pc2_test
```

Then Unity publishes balanced left/right cue markers plus rest markers:

- left cue: `0`
- right cue: `1`
- rest: `99`

The script defaults match `configs/default.yaml`:

- `trialsPerClass`: `20`
- `cueSeconds`: `1.0`
- `motorImagerySeconds`: `4.0`
- `restSeconds`: `2.0`

During a full calibration, the service should report `state:CALIBRATING`,
`calibration_progress:x/40`, then `state:TRAINING`, and finally `state:READY`.

Unity also shows the current cue in a large `CueText` overlay. If no `CueText`
is assigned in the scene, `BciLslPanel` creates one under the Canvas at runtime.
Expected cue display:

- `GET READY`
- `LEFT`
- `RIGHT`
- `REST`
- `WAITING FOR TRAINING`

### Realtime

After calibration reaches `state:READY`, press `Start Realtime`. If no realtime
buttons are assigned in the scene, `BciLslPanel` creates `Start Realtime` and
`Stop Realtime` buttons at runtime.

Expected service status:

```text
state:RUNNING
realtime_warming_up
realtime_ready
```

Expected Unity display:

- `p_left` / `p_right` update continuously.
- The probability indicator moves left or right with the stronger class.

Press `Stop Realtime` to send `stop_realtime` and return the service to
`state:READY`.

## What to commit

Keep these in git:

- `Assets/`
- `Packages/manifest.json`
- `Packages/packages-lock.json`
- `ProjectSettings/`

Do not commit generated/local files:

- `Library/`
- `Temp/`
- `UserSettings/`
- `Logs/`
- `.csproj`
- `.sln`
- `.slnx`
- `.vscode/`
