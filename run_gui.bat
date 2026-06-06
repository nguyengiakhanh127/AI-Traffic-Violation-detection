@echo off
cd /d "%~dp0"
set OPENCV_VIDEOIO_PRIORITY_MSMF=0
C:\Users\tungu\AppData\Local\Programs\Python\Python311\python.exe gui/main_window.py
pause
