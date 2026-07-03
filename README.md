# Python 專業影片拼接器

Tkinter 影片/音訊拼接工具，支援預覽、FPS 偵測、快速拼接與音訊輸出。

## 環境需求

- Python 3.10+
- [FFmpeg](https://ffmpeg.org/)（需可在命令列執行 `ffmpeg` 與 `ffprobe`）

## 安裝依賴

在 PowerShell 中，使用你執行程式的那個 Python 直譯器安裝：

```powershell
& C:\Users\User\AppData\Local\Programs\Python\Python313\python.exe -m pip install -r requirements.txt
```

或單獨安裝缺少的套件：

```powershell
& C:\Users\User\AppData\Local\Programs\Python\Python313\python.exe -m pip install opencv-python Pillow
```

## 執行

```powershell
& C:\Users\User\AppData\Local\Programs\Python\Python313\python.exe f:/拼貼/多影片連接.py
```

## 常見錯誤

| 錯誤 | 原因 | 解法 |
|------|------|------|
| `No module named 'cv2'` | 未安裝 OpenCV | `pip install opencv-python` |
| `No module named 'PIL'` | 未安裝 Pillow | `pip install Pillow` |
| ffmpeg 相關錯誤 | 未安裝或未加入 PATH | 安裝 FFmpeg 並重開終端機 |
