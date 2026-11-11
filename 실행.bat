@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PY="C:\Users\master\AppData\Local\Programs\Python\Python313\python.exe"
if not exist "data\synthetic\T37_AMD_STAY_F_POP_202606_4127.csv" %PY% src\gen_synthetic.py
%PY% -m streamlit run src\app.py
pause
