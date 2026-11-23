@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem 안산 이웃 시민 앱 - 브라우저에서 http://127.0.0.1:8600 이 열린다. 휴대폰 크기로 보려면 F12 - 기기 툴바(Ctrl+Shift+M).
rem data\real(구글 드라이브에서 옮긴 민간 실데이터)이 있으면 실데이터로 연다 - 고향 사람 지도가 실제 통신 자료로 보인다(2026-11-20 사용 승인).
rem 커뮤니티 DB(data\community.db)는 운영 콘솔(실행.bat, Streamlit)과 같이 쓴다 - 콘솔에서 올린 공지가 앱에 보인다.
set PY="C:\Users\master\AppData\Local\Programs\Python\Python313\python.exe"
if not exist "data\synthetic\T38_AMD_INFLOW_TIME_F_POP_202606_4127.csv" %PY% src\gen_synthetic.py
if not exist "data\public\raw\localdata\general_restaurants_3930000.csv" %PY% pipeline\stage_licenses.py
if not exist "data\public\shops_ansan.csv" %PY% pipeline\stage_shops.py
set ANSAN_DATA=synthetic
if exist "data\real\STAGED.json" set ANSAN_DATA=real
start "" cmd /c "timeout /t 3 >nul & start http://127.0.0.1:8600"
%PY% src\server.py --port 8600
pause
