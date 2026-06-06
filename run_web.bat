@echo off
cd /d "%~dp0"
echo Dang khoi dong Web Dashboard tai http://localhost:8000 ...
C:\Users\tungu\AppData\Local\Programs\Python\Python311\python.exe -m uvicorn web.backend.main:app --host 0.0.0.0 --port 8000 --reload
pause
