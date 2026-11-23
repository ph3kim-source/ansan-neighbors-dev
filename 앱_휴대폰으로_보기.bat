@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem 같은 와이파이의 휴대폰에서 시민 앱을 연다. 처음에 Windows 방화벽 창이 뜨면 '개인 네트워크'만 허용한다.
rem data\real 이 있으면 실데이터로 연다(2026-11-20 사용 승인). 집 · 사무실 와이파이에서만 쓰고, 공용 와이파이에서는 열지 않는다.
set PY="C:\Users\master\AppData\Local\Programs\Python\Python313\python.exe"
if not exist "data\synthetic\T38_AMD_INFLOW_TIME_F_POP_202606_4127.csv" %PY% src\gen_synthetic.py
if not exist "data\public\raw\localdata\general_restaurants_3930000.csv" %PY% pipeline\stage_licenses.py
if not exist "data\public\shops_ansan.csv" %PY% pipeline\stage_shops.py
set ANSAN_DATA=synthetic
if exist "data\real\STAGED.json" set ANSAN_DATA=real
echo.
echo 휴대폰 브라우저 주소창에 아래 IPv4 주소 중 와이파이 쪽 주소를 넣고 :8600 을 붙인다 (예: http://192.168.0.12:8600)
ipconfig | findstr /i "IPv4"
echo.
%PY% src\server.py --lan --port 8600
pause
