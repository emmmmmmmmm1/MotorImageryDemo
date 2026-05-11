# MotorImageryDemo

A real-time motor imagery brain–computer interface (BCI) demo. Decodes
left/right hand motor imagery from Emotiv EEG and feeds predictions to a
Unity-based feedback UI.

## Architecture

```
  Emotiv EEG  ──LSL──▶  Python service  ──LSL──▶  Unity UI
  (or EmotivPRO         (apps.service)            (calibration cues,
   simulator)                                      real-time feedback)
```

- Emotiv (or the EmotivPRO simulator) streams EEG over LSL.
- The Python service runs the full pipeline: preprocessing →
  calibration → decoder training → real-time inference.
- Unity sends control commands and displays state, calibration cues,
  and class probabilities.

## Repo structure

| Path              | Purpose                                          |
| ----------------- | ------------------------------------------------ |
| `bci/`            | EEG signal processing, models, LSL I/O           |
| `bci/models/`     | Decoders (CSP+LDA today; registry-based, extensible) |
| `apps/service.py` | Headless inference service (state machine)      |
| `unity/`          | Unity UI project (`MotorImageryUnity`)           |
| `configs/`        | YAML configurations                              |
| `scripts/`        | Development utilities                            |
| `tests/`          | pytest suite                                     |
| `docs/`           | Setup and protocol docs                          |

## Setup

### Python (conda)

```bash
conda env create -f environment.yml
conda activate MotorImageryDemo
```

Python 3.10 is required.

### Unity

- Install Unity `6000.4.5f1` (or a compatible Unity 6 editor).
- Open `unity/MotorImageryUnity` in Unity Hub.
- Main scene: `Assets/MainMenu.unity`.

See [`unity/README.md`](unity/README.md) for details.

## Running

### EEG source

Either:

- A real Emotiv EPOC X headset with the Emotiv app streaming over LSL, or
- EmotivPRO with its built-in simulator / playback streaming over LSL.

### Start the service

```bash
python -m apps.service
```

By default, all 14 EEG channels are used. Subset via the CLI:

```bash
python -m apps.service --channels FC5 FC6
```

…or by editing `channels.selection` in [`configs/default.yaml`](configs/default.yaml).

### Start Unity

Open the Unity project and enter Play mode. When running on separate
PCs, Unity and the Python service must be on the same LAN with LSL
traffic permitted by the firewall.

For two-PC setup details, see
[`docs/phase8_two_pc_instructions.md`](docs/phase8_two_pc_instructions.md).

## LSL stream contract

The service exposes the following LSL streams:

| Stream       | Direction | Format               | Purpose                                  |
| ------------ | --------- | -------------------- | ---------------------------------------- |
| `EEG`        | in        | float32 (n_channels) | EEG samples from Emotiv                  |
| `Markers`    | in        | int                  | Calibration cue labels (0=left, 1=right) |
| `Commands`   | in        | string               | Control commands from Unity              |
| `BCI_Status` | out       | string               | State and progress messages              |
| `BCI_Proba`  | out       | float32 (n_classes)  | Smoothed real-time class probabilities   |

## License

TBD
