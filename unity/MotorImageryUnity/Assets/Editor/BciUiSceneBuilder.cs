using TMPro;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.UI;

public static class BciUiSceneBuilder
{
    private const string MainMenuScenePath = "Assets/MainMenu.unity";

    [MenuItem("Motor Imagery/Rebuild Editable Main Menu UI")]
    public static void RebuildEditableMainMenuUi()
    {
        var scene = EditorSceneManager.OpenScene(MainMenuScenePath, OpenSceneMode.Single);
        var canvas = Object.FindFirstObjectByType<Canvas>();
        if (canvas == null)
        {
            var canvasGo = new GameObject("Canvas", typeof(RectTransform));
            canvas = canvasGo.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            canvasGo.AddComponent<CanvasScaler>();
            canvasGo.AddComponent<GraphicRaycaster>();
        }

        var panel = canvas.GetComponent<BciLslPanel>();
        if (panel == null)
        {
            panel = canvas.gameObject.AddComponent<BciLslPanel>();
        }

        DeleteIfExists(canvas.transform, "MainMenuPanel");
        DeleteIfExists(canvas.transform, "CalibrationPanel");
        DeleteIfExists(canvas.transform, "RealtimePanel");
        DeleteIfExists(canvas.transform, "StatusText");
        DeleteIfExists(canvas.transform, "LeftProbaText");
        DeleteIfExists(canvas.transform, "RightProbaText");
        DeleteIfExists(canvas.transform, "StartCalibrationButton");
        DeleteIfExists(canvas.transform, "ShutdownButton");

        var mainMenuPanel = CreatePanel(canvas.transform, "MainMenuPanel", true);
        var calibrationPanel = CreatePanel(canvas.transform, "CalibrationPanel", false);
        var realtimePanel = CreatePanel(canvas.transform, "RealtimePanel", false);

        var statusText = CreateText(
            canvas.transform,
            "StatusText",
            "state: ---",
            22.0f,
            new Vector2(0.0f, 350.0f),
            new Vector2(760.0f, 34.0f)
        );

        CreateText(
            mainMenuPanel,
            "MainMenuTitle",
            "Motor Imagery BCI",
            42.0f,
            new Vector2(0.0f, 160.0f),
            new Vector2(620.0f, 70.0f)
        );
        var menuCalibrationButton = CreateButton(
            mainMenuPanel,
            "MenuCalibrationButton",
            "Calibration",
            new Vector2(0.0f, 55.0f)
        );
        var menuRealtimeButton = CreateButton(
            mainMenuPanel,
            "MenuRealtimeButton",
            "Realtime",
            new Vector2(0.0f, -15.0f)
        );
        var shutdownButton = CreateButton(
            mainMenuPanel,
            "ShutdownButton",
            "Shutdown",
            new Vector2(0.0f, -110.0f)
        );

        CreateText(
            calibrationPanel,
            "CalibrationTitle",
            "Calibration",
            34.0f,
            new Vector2(0.0f, 315.0f),
            new Vector2(520.0f, 52.0f)
        );
        CreateText(
            calibrationPanel,
            "SubjectIdLabel",
            "Subject ID",
            20.0f,
            new Vector2(-210.0f, 275.0f),
            new Vector2(160.0f, 34.0f)
        );
        var subjectIdInput = CreateInputField(
            calibrationPanel,
            "SubjectIdInput",
            "pc2_test",
            new Vector2(45.0f, 275.0f),
            new Vector2(300.0f, 42.0f)
        );
        var startCalibrationButton = CreateButton(
            calibrationPanel,
            "StartCalibrationButton",
            "Start Calibration",
            new Vector2(0.0f, 110.0f)
        );
        var calibrationProgressText = CreateText(
            calibrationPanel,
            "CalibrationProgressText",
            "Calibration 0 / 40",
            22.0f,
            new Vector2(0.0f, 75.0f),
            new Vector2(460.0f, 36.0f)
        );
        var calibrationProgressTrack = CreateBarTrack(
            calibrationPanel,
            "CalibrationProgressTrack",
            new Vector2(420.0f, 18.0f),
            new Vector2(0.0f, 45.0f)
        );
        var calibrationProgressFill = CreateBarFill(
            calibrationProgressTrack,
            "CalibrationProgressFill",
            new Color(0.35f, 0.85f, 1.0f),
            new Vector2(0.0f, 18.0f)
        );
        var warningText = CreateText(
            calibrationPanel,
            "WarningText",
            "",
            20.0f,
            new Vector2(0.0f, 5.0f),
            new Vector2(700.0f, 34.0f)
        );
        warningText.color = new Color(1.0f, 0.25f, 0.25f);
        var cueText = CreateText(
            calibrationPanel,
            "CueText",
            "",
            64.0f,
            Vector2.zero,
            new Vector2(760.0f, 160.0f)
        );
        cueText.fontStyle = FontStyles.Bold;
        var saveBundleButton = CreateButton(
            calibrationPanel,
            "SaveBundleButton",
            "Save Model",
            new Vector2(0.0f, -255.0f)
        );
        var backCalibrationButton = CreateButton(
            calibrationPanel,
            "BackToMenuFromCalibrationButton",
            "Back",
            new Vector2(0.0f, -325.0f)
        );

        var leftProbaText = CreateText(
            realtimePanel,
            "LeftProbaText",
            "p_left: ---",
            28.0f,
            new Vector2(-140.0f, 120.0f),
            new Vector2(260.0f, 44.0f)
        );
        var rightProbaText = CreateText(
            realtimePanel,
            "RightProbaText",
            "p_right: ---",
            28.0f,
            new Vector2(140.0f, 120.0f),
            new Vector2(260.0f, 44.0f)
        );
        var realtimeHintText = CreateText(
            realtimePanel,
            "RealtimeHintText",
            "Realtime idle",
            24.0f,
            new Vector2(0.0f, -175.0f),
            new Vector2(420.0f, 44.0f)
        );
        var probaIndicatorTrack = CreateBarTrack(
            realtimePanel,
            "ProbaIndicatorTrack",
            new Vector2(360.0f, 18.0f),
            new Vector2(0.0f, -210.0f)
        );
        var probaIndicatorThumb = CreateBarThumb(
            probaIndicatorTrack,
            "ProbaIndicatorThumb",
            new Color(0.45f, 1.0f, 0.55f)
        );
        var startRealtimeButton = CreateButton(
            realtimePanel,
            "StartRealtimeButton",
            "Start Realtime",
            new Vector2(-120.0f, -250.0f)
        );
        var stopRealtimeButton = CreateButton(
            realtimePanel,
            "StopRealtimeButton",
            "Stop Realtime",
            new Vector2(120.0f, -250.0f)
        );
        var backRealtimeButton = CreateButton(
            realtimePanel,
            "BackToMenuFromRealtimeButton",
            "Back",
            new Vector2(0.0f, -325.0f)
        );

        panel.statusText = statusText;
        panel.leftProbaText = leftProbaText;
        panel.rightProbaText = rightProbaText;
        panel.cueText = cueText;
        panel.startCalibrationButton = startCalibrationButton;
        panel.shutdownButton = shutdownButton;
        panel.startRealtimeButton = startRealtimeButton;
        panel.stopRealtimeButton = stopRealtimeButton;
        panel.saveBundleButton = saveBundleButton;
        panel.mainMenuPanel = mainMenuPanel;
        panel.calibrationPanel = calibrationPanel;
        panel.realtimePanel = realtimePanel;
        panel.menuCalibrationButton = menuCalibrationButton;
        panel.menuRealtimeButton = menuRealtimeButton;
        panel.backToMenuFromCalibrationButton = backCalibrationButton;
        panel.backToMenuFromRealtimeButton = backRealtimeButton;
        panel.subjectIdInput = subjectIdInput;
        panel.calibrationProgressTrack = calibrationProgressTrack;
        panel.calibrationProgressFill = calibrationProgressFill;
        panel.calibrationProgressText = calibrationProgressText;
        panel.warningText = warningText;
        panel.probaIndicatorTrack = probaIndicatorTrack;
        panel.probaIndicatorThumb = probaIndicatorThumb;
        panel.realtimeHintText = realtimeHintText;

        EditorUtility.SetDirty(panel);
        EditorSceneManager.MarkSceneDirty(scene);
        EditorSceneManager.SaveScene(scene);
        Debug.Log("Rebuilt editable Motor Imagery UI in MainMenu.unity");
    }

    private static RectTransform CreatePanel(Transform parent, string objectName, bool active)
    {
        var go = new GameObject(objectName, typeof(RectTransform));
        go.transform.SetParent(parent, false);
        var rect = go.GetComponent<RectTransform>();
        rect.anchorMin = Vector2.zero;
        rect.anchorMax = Vector2.one;
        rect.offsetMin = Vector2.zero;
        rect.offsetMax = Vector2.zero;
        go.SetActive(active);
        return rect;
    }

    private static TMP_Text CreateText(
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

    private static Button CreateButton(
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
        button.targetGraphic = image;
        CreateText(go.transform, $"{objectName}Text", label, 20.0f, Vector2.zero, rect.sizeDelta);
        return button;
    }

    private static TMP_InputField CreateInputField(
        Transform parent,
        string objectName,
        string text,
        Vector2 anchoredPosition,
        Vector2 size
    )
    {
        var go = new GameObject(objectName, typeof(RectTransform));
        go.transform.SetParent(parent, false);
        var rect = go.GetComponent<RectTransform>();
        rect.anchorMin = new Vector2(0.5f, 0.5f);
        rect.anchorMax = new Vector2(0.5f, 0.5f);
        rect.sizeDelta = size;
        rect.anchoredPosition = anchoredPosition;
        var image = go.AddComponent<Image>();
        image.color = new Color(0.08f, 0.08f, 0.08f, 0.92f);
        var input = go.AddComponent<TMP_InputField>();
        input.targetGraphic = image;

        var textComponent = CreateText(go.transform, "Text", text, 20.0f, Vector2.zero, size);
        textComponent.alignment = TextAlignmentOptions.MidlineLeft;
        textComponent.rectTransform.offsetMin = new Vector2(12.0f, 4.0f);
        textComponent.rectTransform.offsetMax = new Vector2(-12.0f, -4.0f);
        var placeholder = CreateText(go.transform, "Placeholder", "S001", 20.0f, Vector2.zero, size);
        placeholder.alignment = TextAlignmentOptions.MidlineLeft;
        placeholder.color = new Color(1.0f, 1.0f, 1.0f, 0.45f);
        placeholder.rectTransform.offsetMin = new Vector2(12.0f, 4.0f);
        placeholder.rectTransform.offsetMax = new Vector2(-12.0f, -4.0f);
        input.textComponent = textComponent;
        input.placeholder = placeholder;
        input.text = text;
        return input;
    }

    private static RectTransform CreateBarTrack(
        Transform parent,
        string objectName,
        Vector2 size,
        Vector2 anchoredPosition
    )
    {
        var go = new GameObject(objectName, typeof(RectTransform));
        go.transform.SetParent(parent, false);
        var rect = go.GetComponent<RectTransform>();
        rect.anchorMin = new Vector2(0.5f, 0.5f);
        rect.anchorMax = new Vector2(0.5f, 0.5f);
        rect.sizeDelta = size;
        rect.anchoredPosition = anchoredPosition;
        var image = go.AddComponent<Image>();
        image.color = new Color(0.20f, 0.20f, 0.20f, 0.85f);
        image.raycastTarget = false;
        return rect;
    }

    private static RectTransform CreateBarFill(
        RectTransform parent,
        string objectName,
        Color color,
        Vector2 size
    )
    {
        var go = new GameObject(objectName, typeof(RectTransform));
        go.transform.SetParent(parent, false);
        var rect = go.GetComponent<RectTransform>();
        rect.anchorMin = new Vector2(0.0f, 0.5f);
        rect.anchorMax = new Vector2(0.0f, 0.5f);
        rect.pivot = new Vector2(0.0f, 0.5f);
        rect.sizeDelta = size;
        rect.anchoredPosition = Vector2.zero;
        var image = go.AddComponent<Image>();
        image.color = color;
        image.raycastTarget = false;
        return rect;
    }

    private static RectTransform CreateBarThumb(RectTransform parent, string objectName, Color color)
    {
        var go = new GameObject(objectName, typeof(RectTransform));
        go.transform.SetParent(parent, false);
        var rect = go.GetComponent<RectTransform>();
        rect.anchorMin = new Vector2(0.5f, 0.5f);
        rect.anchorMax = new Vector2(0.5f, 0.5f);
        rect.sizeDelta = new Vector2(24.0f, 36.0f);
        rect.anchoredPosition = Vector2.zero;
        var image = go.AddComponent<Image>();
        image.color = color;
        image.raycastTarget = false;
        return rect;
    }

    private static void DeleteIfExists(Transform parent, string objectName)
    {
        var child = parent.Find(objectName);
        if (child != null)
        {
            Object.DestroyImmediate(child.gameObject);
        }
    }
}
