using System.Collections;
using System.Collections.Generic;
using TMPro;
using UnityEngine;
using UnityEngine.UI;
using LSL;

public class BciLslPanel : MonoBehaviour
{
    [Header("UI")]
    public TMP_Text statusText;
    public TMP_Text leftProbaText;
    public TMP_Text rightProbaText;
    public TMP_Text cueText;
    public Button startCalibrationButton;
    public Button shutdownButton;
    public Button startRealtimeButton;
    public Button stopRealtimeButton;

    [Header("Calibration Progress")]
    public RectTransform calibrationProgressTrack;
    public RectTransform calibrationProgressFill;
    public TMP_Text calibrationProgressText;
    public TMP_Text warningText;
    public Color progressFillColor = new Color(0.35f, 0.85f, 1.0f);
    public Color warningColor = new Color(1.0f, 0.25f, 0.25f);

    [Header("Cue Display")]
    public Color leftCueColor = new Color(0.35f, 0.85f, 1.0f);
    public Color rightCueColor = new Color(1.0f, 0.55f, 0.35f);
    public Color restCueColor = new Color(0.8f, 0.8f, 0.8f);
    public Color readyCueColor = Color.white;
    public Color realtimeCueColor = new Color(0.45f, 1.0f, 0.55f);

    [Header("Realtime Display")]
    public RectTransform probaIndicatorTrack;
    public RectTransform probaIndicatorThumb;
    public TMP_Text realtimeHintText;

    [Header("Calibration Markers")]
    public int trialsPerClass = 20;
    public float cueSeconds = 1.0f;
    public float motorImagerySeconds = 4.0f;
    public float restSeconds = 2.0f;
    public int leftMarker = 0;
    public int rightMarker = 1;
    public int restMarker = 99;
    public bool shuffleCalibrationTrials = true;
    public int trialShuffleSeed = 1;

    private StreamInlet statusInlet;
    private StreamInlet probaInlet;
    private StreamOutlet commandOutlet;
    private StreamOutlet markerOutlet;
    private ContinuousResolver statusResolver;
    private ContinuousResolver probaResolver;

    private readonly string[] statusSample = new string[1];
    private readonly float[] probaSample = new float[2];
    private readonly string[] commandSample = new string[1];
    private readonly int[] markerSample = new int[1];
    private string lastStatusMessage = "";
    private string serviceState = "";
    private int calibrationProgressTotal = 40;
    private float nextResolveAt;
    private Coroutine calibrationRoutine;
    private const float ProbaTrackWidth = 360.0f;
    private const float CalibrationTrackWidth = 420.0f;

    private void Start()
    {
        EnsureCueText();
        EnsureCalibrationProgressControls();
        EnsureRealtimeControls();

        statusResolver = new ContinuousResolver("type", "Status");
        probaResolver = new ContinuousResolver("type", "BCI_Proba");

        if (statusText != null)
        {
            statusText.text = "state: ---";
            statusText.color = Color.white;
        }

        if (leftProbaText != null)
        {
            leftProbaText.text = "p_left: ---";
        }

        if (rightProbaText != null)
        {
            rightProbaText.text = "p_right: ---";
        }

        if (cueText != null)
        {
            cueText.raycastTarget = false;
        }
        SetCueText("", readyCueColor);
        SetWarningText("");


        var commandInfo = new StreamInfo(
            "UnityCommands",
            "Commands",
            1,
            LSL.LSL.IRREGULAR_RATE,
            channel_format_t.cf_string,
            "unity_commands"
        );
        commandOutlet = new StreamOutlet(commandInfo);

        var markerInfo = new StreamInfo(
            "UnityMarkers",
            "Markers",
            1,
            LSL.LSL.IRREGULAR_RATE,
            channel_format_t.cf_int32,
            "unity_markers"
        );
        markerOutlet = new StreamOutlet(markerInfo);

        if (startCalibrationButton != null)
        {
            startCalibrationButton.onClick.AddListener(StartCalibration);
        }

        if (shutdownButton != null)
        {
            shutdownButton.onClick.AddListener(Shutdown);
        }

        if (startRealtimeButton != null)
        {
            startRealtimeButton.onClick.AddListener(StartRealtime);
        }

        if (stopRealtimeButton != null)
        {
            stopRealtimeButton.onClick.AddListener(StopRealtime);
        }

        UpdateCalibrationProgress(0, 40);
        UpdateRealtimeIndicator(0.5f, 0.5f);
        UpdateControlInteractivity();
        TryResolveInlets();
    }

    private void Update()
    {
        if (Time.time >= nextResolveAt)
        {
            TryResolveInlets();
            nextResolveAt = Time.time + 1.0f;
        }

        PullStatus();
        PullProba();
    }

    private void TryResolveInlets()
    {
        if (statusInlet == null)
        {
            statusInlet = TryOpenInlet(statusResolver, "Status");
        }

        if (probaInlet == null)
        {
            probaInlet = TryOpenInlet(probaResolver, "BCI_Proba");
        }
    }

    private StreamInlet TryOpenInlet(ContinuousResolver resolver, string streamType)
    {
        if (resolver == null)
        {
            return null;
        }

        var streams = resolver.results();
        if (streams.Length == 0)
        {
            return null;
        }

        try
        {
            var inlet = new StreamInlet(streams[0]);
            inlet.open_stream(1.0);
            Debug.Log($"Connected to {streamType} stream: {streams[0].name()}");
            return inlet;
        }
        catch (System.Exception ex)
        {
            Debug.LogWarning($"Could not open {streamType} stream yet: {ex.Message}");
            return null;
        }
    }

    private void PullStatus()
    {
        if (statusInlet == null)
        {
            return;
        }

        try
        {
            double timestamp;
            while ((timestamp = statusInlet.pull_sample(statusSample, 0.0)) != 0.0)
            {
                string message = statusSample[0];
                if (statusText != null)
                {
                    statusText.text = message;
                    statusText.color = message.StartsWith("error:") ? Color.red : Color.white;
                }
                HandleStatusMessage(message);
                if (message != lastStatusMessage)
                {
                    Debug.Log($"Status stream sample: {message}");
                    lastStatusMessage = message;
                }
            }
        }
        catch (LostException)
        {
            Debug.LogWarning("Status stream lost; will try to reconnect.");
            statusInlet.close_stream();
            statusInlet = null;
        }
    }

    private void PullProba()
    {
        if (probaInlet == null || leftProbaText == null || rightProbaText == null)
        {
            return;
        }

        try
        {
            double timestamp;
            while ((timestamp = probaInlet.pull_sample(probaSample, 0.0)) != 0.0)
            {
                leftProbaText.text = $"p_left: {probaSample[0]:0.000}";
                rightProbaText.text = $"p_right: {probaSample[1]:0.000}";
                UpdateRealtimeIndicator(probaSample[0], probaSample[1]);
            }
        }
        catch (LostException)
        {
            Debug.LogWarning("BCI_Proba stream lost; will try to reconnect.");
            probaInlet.close_stream();
            probaInlet = null;
        }
    }

    private void PushCommand(string command)
    {
        if (commandOutlet == null)
        {
            return;
        }

        commandSample[0] = command;
        commandOutlet.push_sample(commandSample, LSL.LSL.local_clock());
        Debug.Log($"Sent command: {command}");
    }

    private void StartCalibration()
    {
        if (calibrationRoutine != null)
        {
            Debug.LogWarning("Calibration marker sequence is already running.");
            return;
        }

        PushCommand("start_calibration:subject=pc2_test");
        serviceState = "CALIBRATING";
        UpdateCalibrationProgress(0, trialsPerClass * 2);
        UpdateControlInteractivity();
        SetCueText("GET READY", readyCueColor);
        calibrationRoutine = StartCoroutine(PublishCalibrationMarkers());
    }

    private void Shutdown()
    {
        if (calibrationRoutine != null)
        {
            StopCoroutine(calibrationRoutine);
            calibrationRoutine = null;
        }

        SetCueText("SHUTDOWN", restCueColor);
        PushCommand("shutdown");
    }

    private void StartRealtime()
    {
        if (serviceState != "READY")
        {
            Debug.LogWarning($"Start Realtime ignored while service state is {serviceState}");
            UpdateControlInteractivity();
            return;
        }

        PushCommand("start_realtime");
        serviceState = "RUNNING";
        UpdateControlInteractivity();
        SetCueText("REALTIME STARTING", realtimeCueColor);
        if (realtimeHintText != null)
        {
            realtimeHintText.text = "Realtime starting";
        }
    }

    private void StopRealtime()
    {
        if (serviceState != "RUNNING")
        {
            Debug.LogWarning($"Stop Realtime ignored while service state is {serviceState}");
            UpdateControlInteractivity();
            return;
        }

        PushCommand("stop_realtime");
        serviceState = "READY";
        UpdateControlInteractivity();
        SetCueText("REALTIME STOPPED", restCueColor);
        if (realtimeHintText != null)
        {
            realtimeHintText.text = "Realtime stopped";
        }
    }

    private IEnumerator PublishCalibrationMarkers()
    {
        var labels = BuildCalibrationLabels();
        Debug.Log($"Calibration marker sequence started: {labels.Count} cue markers");

        yield return new WaitForSecondsRealtime(cueSeconds);

        for (int index = 0; index < labels.Count; index++)
        {
            int label = labels[index];
            SetCueForMarker(label);
            PushMarker(label);
            Debug.Log($"Calibration cue {index + 1}/{labels.Count}: marker={label}");

            yield return new WaitForSecondsRealtime(motorImagerySeconds);

            SetCueText("REST", restCueColor);
            PushMarker(restMarker);
            Debug.Log($"Calibration rest marker={restMarker}");

            yield return new WaitForSecondsRealtime(restSeconds + cueSeconds);
        }

        Debug.Log("Calibration marker sequence complete.");
        SetCueText("WAITING FOR TRAINING", readyCueColor);
        calibrationRoutine = null;
        UpdateControlInteractivity();
    }

    private List<int> BuildCalibrationLabels()
    {
        int nPerClass = Mathf.Max(1, trialsPerClass);
        var labels = new List<int>(nPerClass * 2);
        for (int i = 0; i < nPerClass; i++)
        {
            labels.Add(leftMarker);
            labels.Add(rightMarker);
        }

        if (shuffleCalibrationTrials)
        {
            var rng = new System.Random(trialShuffleSeed);
            for (int i = labels.Count - 1; i > 0; i--)
            {
                int j = rng.Next(i + 1);
                int tmp = labels[i];
                labels[i] = labels[j];
                labels[j] = tmp;
            }
        }

        return labels;
    }

    private void PushMarker(int marker)
    {
        if (markerOutlet == null)
        {
            return;
        }

        markerSample[0] = marker;
        markerOutlet.push_sample(markerSample, LSL.LSL.local_clock());
    }

    private void HandleStatusMessage(string message)
    {
        if (message.StartsWith("state:"))
        {
            string nextState = message.Substring("state:".Length).Trim();
            bool enteredCalibration = serviceState != "CALIBRATING"
                && nextState == "CALIBRATING";
            bool changedState = serviceState != nextState;

            serviceState = nextState;
            if (changedState)
            {
                SetWarningText("");
            }
            if (enteredCalibration)
            {
                UpdateCalibrationProgress(0, trialsPerClass * 2);
            }
            UpdateControlInteractivity();
        }
        else if (message.StartsWith("calibration_progress:"))
        {
            SetWarningText("");
            if (TryParseCalibrationProgress(message, out int current, out int total))
            {
                UpdateCalibrationProgress(current, total);
            }
        }
        else if (message.StartsWith("calibration_done:"))
        {
            SetWarningText("");
            UpdateCalibrationProgress(calibrationProgressTotal, calibrationProgressTotal);
        }
        else if (message.StartsWith("error:"))
        {
            SetWarningText(message);
            UpdateControlInteractivity();
        }
        else
        {
            UpdateControlInteractivity();
        }
    }

    private void UpdateControlInteractivity()
    {
        bool isIdle = serviceState == "IDLE";
        bool isReady = serviceState == "READY";
        bool isRunning = serviceState == "RUNNING";

        if (startCalibrationButton != null)
        {
            startCalibrationButton.interactable = isIdle && calibrationRoutine == null;
        }

        if (startRealtimeButton != null)
        {
            startRealtimeButton.interactable = isReady;
        }

        if (stopRealtimeButton != null)
        {
            stopRealtimeButton.interactable = isRunning;
        }
    }

    private bool TryParseCalibrationProgress(string message, out int current, out int total)
    {
        current = 0;
        total = 0;
        string payload = message.Substring("calibration_progress:".Length).Trim();
        string[] parts = payload.Split('/');
        if (parts.Length != 2)
        {
            return false;
        }

        return int.TryParse(parts[0], out current)
            && int.TryParse(parts[1], out total)
            && total > 0;
    }

    private void UpdateCalibrationProgress(int current, int total)
    {
        int safeTotal = Mathf.Max(1, total);
        int safeCurrent = Mathf.Clamp(current, 0, safeTotal);
        calibrationProgressTotal = safeTotal;
        float ratio = Mathf.Clamp01((float)safeCurrent / safeTotal);

        if (calibrationProgressFill != null)
        {
            calibrationProgressFill.sizeDelta = new Vector2(
                CalibrationTrackWidth * ratio,
                calibrationProgressFill.sizeDelta.y
            );
        }

        if (calibrationProgressText != null)
        {
            calibrationProgressText.text = $"Calibration {safeCurrent} / {safeTotal}";
        }
    }

    private void SetWarningText(string message)
    {
        if (warningText == null)
        {
            return;
        }

        warningText.text = message;
        warningText.color = warningColor;
        warningText.gameObject.SetActive(!string.IsNullOrEmpty(message));
    }

    private void UpdateRealtimeIndicator(float leftProba, float rightProba)
    {
        if (probaIndicatorThumb != null)
        {
            float clampedLeft = Mathf.Clamp01(leftProba);
            float clampedRight = Mathf.Clamp01(rightProba);
            float balance = clampedRight - clampedLeft;
            float x = balance * (ProbaTrackWidth * 0.5f);
            probaIndicatorThumb.anchoredPosition = new Vector2(
                x,
                probaIndicatorThumb.anchoredPosition.y
            );
        }

        if (realtimeHintText != null)
        {
            string side = leftProba >= rightProba ? "LEFT" : "RIGHT";
            realtimeHintText.text = $"{side} {Mathf.Max(leftProba, rightProba):0.000}";
        }
    }

    private void SetCueForMarker(int marker)
    {
        if (marker == leftMarker)
        {
            SetCueText("LEFT", leftCueColor);
        }
        else if (marker == rightMarker)
        {
            SetCueText("RIGHT", rightCueColor);
        }
        else
        {
            SetCueText($"MARKER {marker}", readyCueColor);
        }
    }

    private void SetCueText(string text, Color color)
    {
        if (cueText == null)
        {
            return;
        }

        cueText.text = text;
        cueText.color = color;
    }

    private void EnsureCueText()
    {
        if (cueText != null)
        {
            return;
        }

        var canvas = GetComponentInParent<Canvas>();
        if (canvas == null)
        {
            return;
        }

        var go = new GameObject("CueText", typeof(RectTransform));
        go.transform.SetParent(canvas.transform, false);
        cueText = go.AddComponent<TextMeshProUGUI>();
        cueText.alignment = TextAlignmentOptions.Center;
        cueText.fontSize = 64.0f;
        cueText.fontStyle = FontStyles.Bold;
        cueText.raycastTarget = false;

        var rect = cueText.rectTransform;
        rect.anchorMin = new Vector2(0.0f, 0.35f);
        rect.anchorMax = new Vector2(1.0f, 0.65f);
        rect.offsetMin = Vector2.zero;
        rect.offsetMax = Vector2.zero;
    }

    private void EnsureCalibrationProgressControls()
    {
        var canvas = GetComponentInParent<Canvas>();
        if (canvas == null)
        {
            return;
        }

        if (calibrationProgressTrack == null)
        {
            calibrationProgressTrack = CreateProgressTrack(canvas.transform);
        }

        if (calibrationProgressFill == null && calibrationProgressTrack != null)
        {
            calibrationProgressFill = CreateProgressFill(calibrationProgressTrack);
        }

        if (calibrationProgressText == null)
        {
            calibrationProgressText = CreateRuntimeText(
                canvas.transform,
                "CalibrationProgressText",
                "Calibration 0 / 40",
                22.0f,
                new Vector2(0.0f, 255.0f),
                new Vector2(460.0f, 36.0f)
            );
        }

        if (warningText == null)
        {
            warningText = CreateRuntimeText(
                canvas.transform,
                "WarningText",
                "",
                20.0f,
                new Vector2(0.0f, 190.0f),
                new Vector2(700.0f, 34.0f)
            );
            warningText.color = warningColor;
        }
    }

    private void EnsureRealtimeControls()
    {
        var canvas = GetComponentInParent<Canvas>();
        if (canvas == null)
        {
            return;
        }

        if (startRealtimeButton == null)
        {
            startRealtimeButton = CreateRuntimeButton(
                canvas.transform,
                "StartRealtimeButton",
                "Start Realtime",
                new Vector2(-120.0f, -250.0f)
            );
        }

        if (stopRealtimeButton == null)
        {
            stopRealtimeButton = CreateRuntimeButton(
                canvas.transform,
                "StopRealtimeButton",
                "Stop Realtime",
                new Vector2(120.0f, -250.0f)
            );
        }

        if (probaIndicatorTrack == null)
        {
            probaIndicatorTrack = CreateRealtimeTrack(canvas.transform);
        }

        if (probaIndicatorThumb == null && probaIndicatorTrack != null)
        {
            probaIndicatorThumb = CreateRealtimeThumb(probaIndicatorTrack);
        }

        if (realtimeHintText == null)
        {
            realtimeHintText = CreateRuntimeText(
                canvas.transform,
                "RealtimeHintText",
                "Realtime idle",
                24.0f,
                new Vector2(0.0f, -175.0f),
                new Vector2(420.0f, 44.0f)
            );
        }
    }

    private Button CreateRuntimeButton(
        Transform parent,
        string objectName,
        string label,
        Vector2 anchoredPosition
    )
    {
        var go = new GameObject(objectName, typeof(RectTransform));
        go.transform.SetParent(parent, false);

        var rect = go.GetComponent<RectTransform>();
        rect.anchorMin = new Vector2(0.5f, 0.5f);
        rect.anchorMax = new Vector2(0.5f, 0.5f);
        rect.sizeDelta = new Vector2(190.0f, 52.0f);
        rect.anchoredPosition = anchoredPosition;

        var image = go.AddComponent<Image>();
        image.color = new Color(0.12f, 0.12f, 0.12f, 0.92f);

        var button = go.AddComponent<Button>();
        var colors = button.colors;
        colors.normalColor = image.color;
        colors.highlightedColor = new Color(0.20f, 0.20f, 0.20f, 0.95f);
        colors.pressedColor = new Color(0.08f, 0.08f, 0.08f, 1.0f);
        colors.selectedColor = colors.highlightedColor;
        button.colors = colors;

        CreateRuntimeText(
            go.transform,
            $"{objectName}Text",
            label,
            20.0f,
            Vector2.zero,
            rect.sizeDelta
        );
        return button;
    }

    private TMP_Text CreateRuntimeText(
        Transform parent,
        string objectName,
        string text,
        float fontSize,
        Vector2 anchoredPosition,
        Vector2 size
    )
    {
        var go = new GameObject(objectName, typeof(RectTransform));
        go.transform.SetParent(parent, false);
        var tmp = go.AddComponent<TextMeshProUGUI>();
        tmp.text = text;
        tmp.fontSize = fontSize;
        tmp.alignment = TextAlignmentOptions.Center;
        tmp.color = Color.white;
        tmp.raycastTarget = false;

        var rect = tmp.rectTransform;
        rect.anchorMin = new Vector2(0.5f, 0.5f);
        rect.anchorMax = new Vector2(0.5f, 0.5f);
        rect.sizeDelta = size;
        rect.anchoredPosition = anchoredPosition;
        return tmp;
    }

    private RectTransform CreateProgressTrack(Transform parent)
    {
        var go = new GameObject("CalibrationProgressTrack", typeof(RectTransform));
        go.transform.SetParent(parent, false);

        var rect = go.GetComponent<RectTransform>();
        rect.anchorMin = new Vector2(0.5f, 0.5f);
        rect.anchorMax = new Vector2(0.5f, 0.5f);
        rect.sizeDelta = new Vector2(CalibrationTrackWidth, 18.0f);
        rect.anchoredPosition = new Vector2(0.0f, 225.0f);

        var image = go.AddComponent<Image>();
        image.color = new Color(0.20f, 0.20f, 0.20f, 0.85f);
        image.raycastTarget = false;
        return rect;
    }

    private RectTransform CreateProgressFill(Transform parent)
    {
        var go = new GameObject("CalibrationProgressFill", typeof(RectTransform));
        go.transform.SetParent(parent, false);

        var rect = go.GetComponent<RectTransform>();
        rect.anchorMin = new Vector2(0.0f, 0.5f);
        rect.anchorMax = new Vector2(0.0f, 0.5f);
        rect.pivot = new Vector2(0.0f, 0.5f);
        rect.sizeDelta = new Vector2(0.0f, 18.0f);
        rect.anchoredPosition = Vector2.zero;

        var image = go.AddComponent<Image>();
        image.color = progressFillColor;
        image.raycastTarget = false;
        return rect;
    }

    private RectTransform CreateRealtimeTrack(Transform parent)
    {
        var go = new GameObject("ProbaIndicatorTrack", typeof(RectTransform));
        go.transform.SetParent(parent, false);

        var rect = go.GetComponent<RectTransform>();
        rect.anchorMin = new Vector2(0.5f, 0.5f);
        rect.anchorMax = new Vector2(0.5f, 0.5f);
        rect.sizeDelta = new Vector2(ProbaTrackWidth, 18.0f);
        rect.anchoredPosition = new Vector2(0.0f, -210.0f);

        var image = go.AddComponent<Image>();
        image.color = new Color(0.25f, 0.25f, 0.25f, 0.85f);
        image.raycastTarget = false;
        return rect;
    }

    private RectTransform CreateRealtimeThumb(Transform parent)
    {
        var go = new GameObject("ProbaIndicatorThumb", typeof(RectTransform));
        go.transform.SetParent(parent, false);

        var rect = go.GetComponent<RectTransform>();
        rect.anchorMin = new Vector2(0.5f, 0.5f);
        rect.anchorMax = new Vector2(0.5f, 0.5f);
        rect.sizeDelta = new Vector2(24.0f, 36.0f);
        rect.anchoredPosition = Vector2.zero;

        var image = go.AddComponent<Image>();
        image.color = realtimeCueColor;
        image.raycastTarget = false;
        return rect;
    }

    private void OnDestroy()
    {
        if (calibrationRoutine != null)
        {
            StopCoroutine(calibrationRoutine);
            calibrationRoutine = null;
        }

        if (startCalibrationButton != null)
        {
            startCalibrationButton.interactable = true;
        }

        statusInlet?.close_stream();
        probaInlet?.close_stream();
        commandOutlet?.Dispose();
        markerOutlet?.Dispose();
        statusResolver?.Dispose();
        probaResolver?.Dispose();
    }
}
