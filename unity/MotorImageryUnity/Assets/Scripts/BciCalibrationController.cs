using System.Collections;
using System.Collections.Generic;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

public class BciCalibrationController : MonoBehaviour
{
    public TMP_Text cueText;
    public Button startCalibrationButton;
    public Button shutdownButton;
    public Button saveBundleButton;
    public TMP_InputField subjectIdInput;
    public RectTransform calibrationProgressTrack;
    public RectTransform calibrationProgressFill;
    public TMP_Text calibrationProgressText;
    public TMP_Text warningText;

    public Color warningColor = new Color(1.0f, 0.25f, 0.25f);
    public Color leftCueColor = new Color(0.35f, 0.85f, 1.0f);
    public Color rightCueColor = new Color(1.0f, 0.55f, 0.35f);
    public Color restCueColor = new Color(0.8f, 0.8f, 0.8f);
    public Color readyCueColor = Color.white;
    public Color realtimeCueColor = new Color(0.45f, 1.0f, 0.55f);

    public int trialsPerClass = 20;
    public float cueSeconds = 1.0f;
    public float motorImagerySeconds = 4.0f;
    public float restSeconds = 2.0f;
    public int leftMarker = 0;
    public int rightMarker = 1;
    public int restMarker = 99;
    public bool shuffleCalibrationTrials = true;
    public int trialShuffleSeed = 1;
    // How long to wait for the service to broadcast its service_config
    // before falling back to the Inspector defaults above.
    public float serviceConfigWaitSeconds = 3.0f;

    private BciLslStreams streams;
    private string serviceState = "";
    private string currentSubjectId = "pc2_test";
    private int calibrationProgressCurrent;
    private int calibrationProgressTotal = 40;
    private Coroutine calibrationRoutine;
    private bool initialized;
    private bool serviceConfigReceived;

    private const float FallbackCalibrationTrackWidth = 420.0f;

    public void Initialize(BciLslStreams lslStreams)
    {
        if (initialized)
        {
            return;
        }

        streams = lslStreams;
        if (streams != null)
        {
            streams.StatusReceived += HandleStatusMessage;
        }

        if (cueText != null)
        {
            cueText.raycastTarget = false;
        }

        if (startCalibrationButton != null)
        {
            startCalibrationButton.onClick.AddListener(StartCalibration);
        }

        if (shutdownButton != null)
        {
            shutdownButton.onClick.AddListener(Shutdown);
        }

        if (saveBundleButton != null)
        {
            saveBundleButton.onClick.AddListener(SaveBundle);
        }

        if (subjectIdInput != null)
        {
            if (string.IsNullOrWhiteSpace(subjectIdInput.text))
            {
                subjectIdInput.SetTextWithoutNotify(currentSubjectId);
            }
            else
            {
                currentSubjectId = SanitizeSubjectId(subjectIdInput.text);
            }
            subjectIdInput.onEndEdit.AddListener(UpdateSubjectIdFromInput);
        }

        initialized = true;
        SetCueText("", readyCueColor);
        SetWarningText("");
        UpdateCalibrationProgress(0, 40);
        UpdateControlInteractivity();
    }

    private void StartCalibration()
    {
        if (calibrationRoutine != null)
        {
            Debug.LogWarning("Calibration marker sequence is already running.");
            return;
        }

        currentSubjectId = GetSubjectId();
        streams?.PushCommand($"start_calibration:subject={currentSubjectId}");
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
        streams?.PushCommand("shutdown");
    }

    private void SaveBundle()
    {
        if (serviceState != "READY")
        {
            Debug.LogWarning($"Save Bundle ignored while service state is {serviceState}");
            UpdateControlInteractivity();
            return;
        }

        currentSubjectId = GetSubjectId();
        streams?.PushCommand($"save_bundle:subject={currentSubjectId}");
        SetCueText("SAVING BUNDLE", realtimeCueColor);
    }

    private IEnumerator PublishCalibrationMarkers()
    {
        // Normally service_config arrived at connect time, long before
        // Start was clicked. This wait is just a safety net for the case
        // where calibration is triggered before the service has answered
        // our initial query_config (e.g. service restarted mid-session).
        // Falls back to Inspector defaults on timeout rather than
        // deadlocking the calibration flow.
        float waitStart = Time.realtimeSinceStartup;
        while (!serviceConfigReceived
               && Time.realtimeSinceStartup - waitStart < serviceConfigWaitSeconds)
        {
            yield return null;
        }
        if (!serviceConfigReceived)
        {
            Debug.LogWarning(
                $"service_config not received within {serviceConfigWaitSeconds}s; " +
                $"using Inspector defaults (cue={cueSeconds}s, mi={motorImagerySeconds}s, " +
                $"rest={restSeconds}s, trials/class={trialsPerClass})."
            );
        }

        var labels = BuildCalibrationLabels();
        Debug.Log($"Calibration marker sequence started: {labels.Count} cue markers");

        yield return new WaitForSecondsRealtime(cueSeconds);

        for (int index = 0; index < labels.Count; index++)
        {
            int label = labels[index];

            // Cue phase: show LEFT/RIGHT. Subject starts imagining as soon as
            // the cue appears; this first cueSeconds window is intentionally
            // dropped from the training data (warmup) by withholding the
            // marker until MI onset. The display does not change at the
            // boundary ? only the LSL marker draws it.
            SetCueForMarker(label);
            Debug.Log($"Calibration trial {index + 1}/{labels.Count} cue: marker={label}");

            yield return new WaitForSecondsRealtime(cueSeconds);

            // MI phase: marker timestamp = MI onset = start of the slice used
            // for training. Screen stays on LEFT/RIGHT.
            streams?.PushMarker(label);
            Debug.Log($"Calibration trial {index + 1}/{labels.Count} MI onset: marker={label}");

            yield return new WaitForSecondsRealtime(motorImagerySeconds);

            SetCueText("REST", restCueColor);
            streams?.PushMarker(restMarker);
            Debug.Log($"Calibration rest marker={restMarker}");

            yield return new WaitForSecondsRealtime(restSeconds);
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
        else if (message.StartsWith("service_config:"))
        {
            ParseServiceConfig(message);
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
        else if (message.StartsWith("bundle_saved:"))
        {
            SetWarningText("");
            SetCueText("BUNDLE SAVED", realtimeCueColor);
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

        if (startCalibrationButton != null)
        {
            startCalibrationButton.interactable = isIdle && calibrationRoutine == null;
        }

        if (saveBundleButton != null)
        {
            saveBundleButton.interactable = isReady;
        }
    }

    private void ParseServiceConfig(string message)
    {
        string payload = message.Substring("service_config:".Length).Trim();
        var culture = System.Globalization.CultureInfo.InvariantCulture;
        foreach (string pair in payload.Split(','))
        {
            string[] kv = pair.Split('=');
            if (kv.Length != 2)
            {
                continue;
            }
            string key = kv[0].Trim();
            string value = kv[1].Trim();
            switch (key)
            {
                case "cue_s":
                    if (float.TryParse(value, System.Globalization.NumberStyles.Float, culture, out float cs))
                    {
                        cueSeconds = cs;
                    }
                    break;
                case "mi_s":
                    if (float.TryParse(value, System.Globalization.NumberStyles.Float, culture, out float mis))
                    {
                        motorImagerySeconds = mis;
                    }
                    break;
                case "rest_s":
                    if (float.TryParse(value, System.Globalization.NumberStyles.Float, culture, out float rs))
                    {
                        restSeconds = rs;
                    }
                    break;
                case "trials_per_class":
                    if (int.TryParse(value, System.Globalization.NumberStyles.Integer, culture, out int tpc))
                    {
                        trialsPerClass = tpc;
                    }
                    break;
                // Other keys (realtime_stride_ms, window_s) are consumed
                // by RopeChoiceInputAggregator. Ignore here.
            }
        }
        serviceConfigReceived = true;
        UpdateCalibrationProgress(calibrationProgressCurrent, trialsPerClass * 2);
        Debug.Log(
            $"Received service_config: cue={cueSeconds}s mi={motorImagerySeconds}s " +
            $"rest={restSeconds}s trials/class={trialsPerClass}"
        );
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
        calibrationProgressCurrent = safeCurrent;
        calibrationProgressTotal = safeTotal;
        float ratio = Mathf.Clamp01((float)safeCurrent / safeTotal);

        if (calibrationProgressFill != null)
        {
            float trackWidth = GetRectWidth(calibrationProgressTrack, FallbackCalibrationTrackWidth);
            calibrationProgressFill.sizeDelta = new Vector2(
                trackWidth * ratio,
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

    private void UpdateSubjectIdFromInput(string value)
    {
        currentSubjectId = SanitizeSubjectId(value);
        if (subjectIdInput != null && subjectIdInput.text != currentSubjectId)
        {
            subjectIdInput.SetTextWithoutNotify(currentSubjectId);
        }
    }

    private string GetSubjectId()
    {
        if (subjectIdInput != null)
        {
            UpdateSubjectIdFromInput(subjectIdInput.text);
        }
        return currentSubjectId;
    }

    private string SanitizeSubjectId(string raw)
    {
        string value = (raw ?? "").Trim();
        if (string.IsNullOrEmpty(value))
        {
            return "pc2_test";
        }

        var chars = new List<char>(value.Length);
        foreach (char ch in value)
        {
            if (char.IsLetterOrDigit(ch) || ch == '_' || ch == '-')
            {
                chars.Add(ch);
            }
            else if (char.IsWhiteSpace(ch))
            {
                chars.Add('_');
            }
        }

        return chars.Count == 0 ? "pc2_test" : new string(chars.ToArray());
    }

    private float GetRectWidth(RectTransform rect, float fallback)
    {
        if (rect == null)
        {
            return fallback;
        }

        if (rect.rect.width > 0.1f)
        {
            return rect.rect.width;
        }

        return Mathf.Abs(rect.sizeDelta.x) > 0.1f ? Mathf.Abs(rect.sizeDelta.x) : fallback;
    }

    private void OnDestroy()
    {
        if (calibrationRoutine != null)
        {
            StopCoroutine(calibrationRoutine);
            calibrationRoutine = null;
        }

        if (streams != null)
        {
            streams.StatusReceived -= HandleStatusMessage;
        }

        if (startCalibrationButton != null)
        {
            startCalibrationButton.onClick.RemoveListener(StartCalibration);
            startCalibrationButton.interactable = true;
        }

        if (shutdownButton != null)
        {
            shutdownButton.onClick.RemoveListener(Shutdown);
        }

        if (saveBundleButton != null)
        {
            saveBundleButton.onClick.RemoveListener(SaveBundle);
        }

        if (subjectIdInput != null)
        {
            subjectIdInput.onEndEdit.RemoveListener(UpdateSubjectIdFromInput);
        }
    }
}
