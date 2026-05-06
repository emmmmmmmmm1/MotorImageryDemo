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
