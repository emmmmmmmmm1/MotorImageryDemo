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

    private StreamInlet statusInlet;
    private StreamInlet probaInlet;
    private StreamOutlet commandOutlet;

    private readonly string[] statusSample = new string[1];
    private readonly float[] probaSample = new float[2];
    private readonly string[] commandSample = new string[1];
    private string lastStatusMessage = "";
    private float nextResolveAt;

    private void Start()
    {
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

        if (startCalibrationButton != null)
        {
            startCalibrationButton.onClick.AddListener(() =>
            {
                PushCommand("start_calibration:subject=pc2_test");
            });
        }

        if (shutdownButton != null)
        {
            shutdownButton.onClick.AddListener(() => PushCommand("shutdown"));
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
            var streams = LSL.LSL.resolve_stream("type", "Status", 1, 0.1);
            if (streams.Length > 0)
            {
                statusInlet = new StreamInlet(streams[0]);
                statusInlet.open_stream(1.0);
                Debug.Log("Connected to Status stream");
            }
        }

        if (probaInlet == null)
        {
            var streams = LSL.LSL.resolve_stream("type", "BCI_Proba", 1, 0.1);
            if (streams.Length > 0)
            {
                probaInlet = new StreamInlet(streams[0]);
                probaInlet.open_stream(1.0);
                Debug.Log("Connected to BCI_Proba stream");
            }
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

    private void OnDestroy()
    {
        statusInlet?.close_stream();
        probaInlet?.close_stream();
    }
}
