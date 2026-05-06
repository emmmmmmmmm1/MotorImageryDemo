using System;
using System.Linq;
using System.Reflection;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

public class BciLslPanel : MonoBehaviour
{
    [Header("UI")]
    public TMP_Text statusText;
    public TMP_Text leftProbaText;
    public TMP_Text rightProbaText;
    public Button startCalibrationButton;
    public Button shutdownButton;

    private Type lslType;
    private Type streamInfoType;
    private Type streamInletType;
    private Type streamOutletType;
    private Type channelFormatType;
    private object statusInlet;
    private object probaInlet;
    private object commandOutlet;
    private MethodInfo statusPullSample;
    private MethodInfo probaPullSample;
    private MethodInfo pushCommandSample;
    private readonly string[] statusSample = new string[1];
    private readonly float[] probaSample = new float[2];
    private float nextResolveAt;

    private void Start()
    {
        SetInitialText();
        if (!FindLslTypes())
        {
            SetStatus("error:lsl4unity_types_missing", Color.red);
            return;
        }

        CreateCommandOutlet();
        WireButtons();
        TryResolveInlets();
    }

    private void Update()
    {
        if (lslType == null)
        {
            return;
        }

        if (Time.time >= nextResolveAt)
        {
            TryResolveInlets();
            nextResolveAt = Time.time + 1.0f;
        }

        PullStatus();
        PullProba();
    }

    private void SetInitialText()
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
    }

    private bool FindLslTypes()
    {
        lslType = FindType("LSL4Unity.LSL") ?? FindType("LSL4Unity.liblsl");
        streamInfoType = FindType("LSL4Unity.StreamInfo") ?? FindType("LSL4Unity.liblsl+StreamInfo");
        streamInletType = FindType("LSL4Unity.StreamInlet") ?? FindType("LSL4Unity.liblsl+StreamInlet");
        streamOutletType = FindType("LSL4Unity.StreamOutlet") ?? FindType("LSL4Unity.liblsl+StreamOutlet");
        channelFormatType = FindType("LSL4Unity.ChannelFormat") ?? FindType("LSL4Unity.liblsl+channel_format_t");

        if (lslType == null || streamInfoType == null || streamInletType == null || streamOutletType == null || channelFormatType == null)
        {
            Debug.LogError(
                "Could not find LSL4Unity runtime types. Make sure the LSL4Unity package is installed."
            );
            return false;
        }

        Debug.Log($"LSL types: {lslType.FullName}, {streamInfoType.FullName}");
        return true;
    }

    private static Type FindType(string fullName)
    {
        foreach (var assembly in AppDomain.CurrentDomain.GetAssemblies())
        {
            var type = assembly.GetType(fullName);
            if (type != null)
            {
                return type;
            }
        }

        return null;
    }

    private void CreateCommandOutlet()
    {
        var stringFormat = GetStringChannelFormat();
        var info = Activator.CreateInstance(
            streamInfoType,
            "UnityCommands",
            "Commands",
            1,
            0.0,
            stringFormat,
            "unity_commands"
        );
        commandOutlet = Activator.CreateInstance(streamOutletType, info);
        pushCommandSample = streamOutletType.GetMethods()
            .FirstOrDefault(m =>
            {
                if (m.Name != "PushSample") return false;
                var ps = m.GetParameters();
                return ps.Length >= 1 && ps[0].ParameterType == typeof(string[]);
            });

        if (pushCommandSample == null)
        {
            Debug.LogError("Could not find StreamOutlet.PushSample(string[])");
        }
    }

    private object GetStringChannelFormat()
    {
        var names = Enum.GetNames(channelFormatType);
        var name = names.FirstOrDefault(n => n == "Str" || n == "cf_string");
        if (name == null)
        {
            throw new InvalidOperationException("Could not find string channel format enum value");
        }

        return Enum.Parse(channelFormatType, name);
    }

    private void WireButtons()
    {
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
    }

    private void TryResolveInlets()
    {
        if (statusInlet == null)
        {
            statusInlet = ResolveInlet("Status");
            if (statusInlet != null)
            {
                statusPullSample = FindPullSample(statusInlet, typeof(string[]));
                Debug.Log("Connected to Status stream");
            }
        }

        if (probaInlet == null)
        {
            probaInlet = ResolveInlet("BCI_Proba");
            if (probaInlet != null)
            {
                probaPullSample = FindPullSample(probaInlet, typeof(float[]));
                Debug.Log("Connected to BCI_Proba stream");
            }
        }
    }

    private object ResolveInlet(string streamType)
    {
        var resolve = lslType.GetMethods(BindingFlags.Public | BindingFlags.Static)
            .FirstOrDefault(m =>
            {
                if (m.Name != "ResolveStream") return false;
                var ps = m.GetParameters();
                return ps.Length >= 4
                    && ps[0].ParameterType == typeof(string)
                    && ps[1].ParameterType == typeof(string);
            });
        if (resolve == null)
        {
            Debug.LogError("Could not find LSL ResolveStream(prop, value, minimum, timeout)");
            return null;
        }

        var streams = (Array)resolve.Invoke(null, new object[] { "type", streamType, 1, 0.1 });
        if (streams == null || streams.Length == 0)
        {
            return null;
        }

        var inlet = Activator.CreateInstance(streamInletType, streams.GetValue(0), 1);
        var open = streamInletType.GetMethods().FirstOrDefault(m => m.Name == "OpenStream");
        open?.Invoke(inlet, new object[] { 1.0 });
        return inlet;
    }

    private static MethodInfo FindPullSample(object inlet, Type sampleType)
    {
        return inlet.GetType().GetMethods()
            .FirstOrDefault(m =>
            {
                if (m.Name != "PullSample") return false;
                var ps = m.GetParameters();
                return ps.Length >= 1 && ps[0].ParameterType == sampleType;
            });
    }

    private void PullStatus()
    {
        if (statusInlet == null || statusPullSample == null || statusText == null)
        {
            return;
        }

        while (true)
        {
            var timestamp = (double)statusPullSample.Invoke(statusInlet, new object[] { statusSample, 0.0 });
            if (timestamp == 0.0) break;
            var message = statusSample[0];
            SetStatus(message, message.StartsWith("error:") ? Color.red : Color.white);
        }
    }

    private void PullProba()
    {
        if (probaInlet == null || probaPullSample == null || leftProbaText == null || rightProbaText == null)
        {
            return;
        }

        while (true)
        {
            var timestamp = (double)probaPullSample.Invoke(probaInlet, new object[] { probaSample, 0.0 });
            if (timestamp == 0.0) break;
            leftProbaText.text = $"p_left: {probaSample[0]:0.000}";
            rightProbaText.text = $"p_right: {probaSample[1]:0.000}";
        }
    }

    private void PushCommand(string command)
    {
        if (commandOutlet == null || pushCommandSample == null)
        {
            return;
        }

        pushCommandSample.Invoke(commandOutlet, new object[] { new[] { command } });
        Debug.Log($"Sent command: {command}");
    }

    private void SetStatus(string message, Color color)
    {
        if (statusText == null)
        {
            return;
        }

        statusText.text = message;
        statusText.color = color;
    }

    private void OnDestroy()
    {
        CloseInlet(statusInlet);
        CloseInlet(probaInlet);
    }

    private static void CloseInlet(object inlet)
    {
        if (inlet == null)
        {
            return;
        }

        inlet.GetType().GetMethod("CloseStream")?.Invoke(inlet, null);
    }
}
