# Unity Phase 6

Expected Unity project path:

```text
unity/MotorImageryUnity
```

The Phase 6 bridge script lives at:

```text
unity/MotorImageryUnity/Assets/Scripts/BciLslPanel.cs
```

After pulling this repo on PC2:

1. Open `unity/MotorImageryUnity` in Unity.
2. Add LSL4Unity through Package Manager if it is not already installed:
   `https://github.com/labstreaminglayer/LSL4Unity.git`
3. Attach `BciLslPanel` to the `Canvas`.
4. Drag these scene objects into the script fields:
   - `StatusText`
   - `LeftProbaText`
   - `RightProbaText`
   - `StartCalibrationButton`
   - `ShutdownButton`
5. Save `MainMenu`.
