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
    public Button startCalibrationButton;
    public Button shutdownButton;

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
    private float nextResolveAt;
    private Coroutine calibrationRoutine;

    private void Start()
    {
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
        if (statusInlet == null || statusText == null)
        {
            return;
        }

        try
        {
            double timestamp;
            while ((timestamp = statusInlet.pull_sample(statusSample, 0.0)) != 0.0)
            {
                string message = statusSample[0];
                statusText.text = message;
                statusText.color = message.StartsWith("error:") ? Color.red : Color.white;
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
        calibrationRoutine = StartCoroutine(PublishCalibrationMarkers());
    }

    private void Shutdown()
    {
        if (calibrationRoutine != null)
        {
            StopCoroutine(calibrationRoutine);
            calibrationRoutine = null;
        }

        PushCommand("shutdown");
    }

    private IEnumerator PublishCalibrationMarkers()
    {
        var labels = BuildCalibrationLabels();
        Debug.Log($"Calibration marker sequence started: {labels.Count} cue markers");

        yield return new WaitForSecondsRealtime(cueSeconds);

        for (int index = 0; index < labels.Count; index++)
        {
            int label = labels[index];
            PushMarker(label);
            Debug.Log($"Calibration cue {index + 1}/{labels.Count}: marker={label}");

            yield return new WaitForSecondsRealtime(motorImagerySeconds);

            PushMarker(restMarker);
            Debug.Log($"Calibration rest marker={restMarker}");

            yield return new WaitForSecondsRealtime(restSeconds + cueSeconds);
        }

        Debug.Log("Calibration marker sequence complete.");
        calibrationRoutine = null;
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

    private void OnDestroy()
    {
        if (calibrationRoutine != null)
        {
            StopCoroutine(calibrationRoutine);
            calibrationRoutine = null;
        }

        statusInlet?.close_stream();
        probaInlet?.close_stream();
        commandOutlet?.Dispose();
        markerOutlet?.Dispose();
        statusResolver?.Dispose();
        probaResolver?.Dispose();
    }
}
