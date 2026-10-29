@echo off
REM Plano B: roda o radar no Windows (precisa do Python 3.10+ instalado).
cd /d "%~dp0"
if not exist .venv (
  python -m venv .venv
  call .venv\Scripts\activate.bat
  pip install -r requirements.txt
) else (
  call .venv\Scripts\activate.bat
)
if exist .env.bat goto run
set /p NT="Cole seu NOTION_TOKEN: "
echo set NOTION_TOKEN=%NT%> .env.bat
:run
call .env.bat
python -m radar.main
echo.
echo Ranking salvo em data\latest.md
pause
