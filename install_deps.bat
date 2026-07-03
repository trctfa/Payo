@echo off
chcp 65001 >nul
echo 正在安裝影片拼接器所需套件...
python -m pip install opencv-python Pillow nvidia-ml-py
if errorlevel 1 (
    echo.
    echo 安裝失敗。請確認 python 已在 PATH，或使用完整路徑：
    echo   "C:\Users\User\AppData\Local\Programs\Python\Python313\python.exe" -m pip install opencv-python Pillow
    pause
    exit /b 1
)
echo.
echo 安裝完成！可以執行程式了。
pause
