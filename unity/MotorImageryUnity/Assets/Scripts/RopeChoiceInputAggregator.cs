using System;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.InputSystem;

public class RopeChoiceInputAggregator : MonoBehaviour
{
    [Serializable]
    public class ChoiceEvent : UnityEvent<int>
    {
    }

    [Header("LSL")]
    [SerializeField] private BciLslStreams streams;
    [SerializeField] private bool initializeStreamsOnStart = true;

    [Header("Decision Window")]
    [SerializeField] private float decisionWindowSeconds = 2.0f;
    [SerializeField] private float expectedSampleIntervalSeconds = 0.25f;
    [SerializeField] private float minimumConfidenceDelta = 0.0f;

    [Header("Keyboard Fallback")]
    [SerializeField] private bool enableKeyboardFallback = true;

    [Header("Debug")]
    [SerializeField] private float accumulatedLeft;
    [SerializeField] private float accumulatedRight;
    [SerializeField] private int samplesInWindow;
    [SerializeField] private string latestDecision = "none";

    public ChoiceEvent OnChoice = new ChoiceEvent();

    public float AccumulatedLeft => accumulatedLeft;
    public float AccumulatedRight => accumulatedRight;
    public int SamplesInWindow => samplesInWindow;
    public string LatestDecision => latestDecision;
    public float DecisionWindowSeconds => decisionWindowSeconds;

    private float windowStartedAt;

    private void Awake()
    {
        if (streams == null)
        {
            streams = FindObjectOfType<BciLslStreams>();
        }
    }

    private void Start()
    {
        ResetWindow();

        if (streams == null)
        {
            streams = gameObject.AddComponent<BciLslStreams>();
        }

        streams.ProbaReceived += HandleProbaReceived;
        streams.StatusReceived += HandleStatusMessage;

        if (initializeStreamsOnStart)
        {
            streams.Initialize();
            streams.PushCommand("start_realtime");
        }
    }

    private void HandleStatusMessage(string message)
    {
        if (!message.StartsWith("service_config:"))
        {
            return;
        }
        string payload = message.Substring("service_config:".Length).Trim();
        var culture = System.Globalization.CultureInfo.InvariantCulture;
        foreach (string pair in payload.Split(','))
        {
            string[] kv = pair.Split('=');
            if (kv.Length != 2)
            {
                continue;
            }
            if (kv[0].Trim() == "realtime_stride_ms"
                && int.TryParse(kv[1].Trim(),
                    System.Globalization.NumberStyles.Integer, culture, out int strideMs))
            {
                expectedSampleIntervalSeconds = strideMs / 1000.0f;
                Debug.Log(
                    $"RopeChoiceInputAggregator: expectedSampleIntervalSeconds " +
                    $"updated from service_config to {expectedSampleIntervalSeconds:F3}s " +
                    $"(stride={strideMs}ms)"
                );
            }
        }
    }

    private void Update()
    {
        if (!enableKeyboardFallback)
        {
            return;
        }

        var keyboard = Keyboard.current;
        if (keyboard == null)
        {
            return;
        }

        if (keyboard.leftArrowKey.wasPressedThisFrame || keyboard.aKey.wasPressedThisFrame)
        {
            PublishChoice(0, "keyboard:left");
        }
        else if (keyboard.rightArrowKey.wasPressedThisFrame || keyboard.dKey.wasPressedThisFrame)
        {
            PublishChoice(1, "keyboard:right");
        }
    }

    private void OnDestroy()
    {
        if (streams != null)
        {
            streams.ProbaReceived -= HandleProbaReceived;
            streams.StatusReceived -= HandleStatusMessage;
        }
    }

    private void HandleProbaReceived(float pLeft, float pRight)
    {
        if (samplesInWindow == 0)
        {
            windowStartedAt = Time.time;
        }

        accumulatedLeft += pLeft;
        accumulatedRight += pRight;
        samplesInWindow++;

        float elapsed = Time.time - windowStartedAt;
        int expectedSamples = Mathf.Max(1, Mathf.RoundToInt(decisionWindowSeconds / Mathf.Max(0.01f, expectedSampleIntervalSeconds)));
        if (elapsed < decisionWindowSeconds && samplesInWindow < expectedSamples)
        {
            return;
        }

        float delta = Mathf.Abs(accumulatedLeft - accumulatedRight);
        if (delta >= minimumConfidenceDelta)
        {
            PublishChoice(accumulatedLeft >= accumulatedRight ? 0 : 1, $"lsl:{accumulatedLeft:F3}/{accumulatedRight:F3}");
        }

        ResetWindow();
    }

    private void PublishChoice(int choice, string source)
    {
        latestDecision = choice == 0 ? $"left ({source})" : $"right ({source})";
        OnChoice.Invoke(choice == 0 ? 0 : 1);
    }

    private void ResetWindow()
    {
        accumulatedLeft = 0.0f;
        accumulatedRight = 0.0f;
        samplesInWindow = 0;
        windowStartedAt = Time.time;
    }
}
