using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UI;

[RequireComponent(typeof(Button))]
public class LoadSceneButton : MonoBehaviour
{
    [SerializeField] private string sceneName = "Game_Scene";

    private Button button;

    private void Awake()
    {
        button = GetComponent<Button>();
        button.onClick.AddListener(LoadScene);
    }

    private void OnDestroy()
    {
        if (button != null)
        {
            button.onClick.RemoveListener(LoadScene);
        }
    }

    private void LoadScene()
    {
        SceneManager.LoadScene(sceneName);
    }
}
