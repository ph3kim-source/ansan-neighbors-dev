@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem 2안 운영 콘솔(Streamlit). data\real 이 있으면 실데이터로 연다(2026-11-20 사용 승인) - 이때는 이 PC(127.0.0.1)에서만 연다.
set PY="C:\Users\master\AppData\Local\Programs\Python\Python313\python.exe"
if not exist "data\synthetic\T38_AMD_INFLOW_TIME_F_POP_202606_4127.csv" %PY% src\gen_synthetic.py
if exist "data\real\STAGED.json" (
  set ANSAN_DATA=real
  %PY% -m streamlit run src\app.py --server.address 127.0.0.1
) else (
  set ANSAN_DATA=synthetic
  %PY% -m streamlit run src\app.py
)
pause
