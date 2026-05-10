using UnityEngine;
using UnityEngine.UI;

public class BciScreenNavigator : MonoBehaviour
{
    public RectTransform mainMenuPanel;
    public RectTransform calibrationPanel;
    public RectTransform realtimePanel;
    public Button menuCalibrationButton;
    public Button menuRealtimeButton;
    public Button backToMenuFromCalibrationButton;
    public Button backToMenuFromRealtimeButton;

    private bool initialized;

    public void Initialize()
    {
        if (initialized)
        {
            return;
        }

        if (menuCalibrationButton != null)
        {
            menuCalibrationButton.onClick.AddListener(ShowCalibrationScreen);
        }

        if (menuRealtimeButton != null)
        {
            menuRealtimeButton.onClick.AddListener(ShowRealtimeScreen);
        }

        if (backToMenuFromCalibrationButton != null)
        {
            backToMenuFromCalibrationButton.onClick.AddListener(ShowMainMenu);
        }

        if (backToMenuFromRealtimeButton != null)
        {
            backToMenuFromRealtimeButton.onClick.AddListener(ShowMainMenu);
        }

        initialized = true;
        ShowMainMenu();
    }

    public void ShowMainMenu()
    {
        SetScreenActive(mainMenuPanel, true);
        SetScreenActive(calibrationPanel, false);
        SetScreenActive(realtimePanel, false);
    }

    public void ShowCalibrationScreen()
    {
        SetScreenActive(mainMenuPanel, false);
        SetScreenActive(calibrationPanel, true);
        SetScreenActive(realtimePanel, false);
    }

    public void ShowRealtimeScreen()
    {
        SetScreenActive(mainMenuPanel, false);
        SetScreenActive(calibrationPanel, false);
        SetScreenActive(realtimePanel, true);
    }

    private void SetScreenActive(RectTransform panel, bool active)
    {
        if (panel != null)
        {
            panel.gameObject.SetActive(active);
        }
    }

    private void OnDestroy()
    {
        if (menuCalibrationButton != null)
        {
            menuCalibrationButton.onClick.RemoveListener(ShowCalibrationScreen);
        }

        if (menuRealtimeButton != null)
        {
            menuRealtimeButton.onClick.RemoveListener(ShowRealtimeScreen);
        }

        if (backToMenuFromCalibrationButton != null)
        {
            backToMenuFromCalibrationButton.onClick.RemoveListener(ShowMainMenu);
        }

        if (backToMenuFromRealtimeButton != null)
        {
            backToMenuFromRealtimeButton.onClick.RemoveListener(ShowMainMenu);
        }
    }
}
