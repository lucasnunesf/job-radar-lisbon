@echo off
REM Fontes que bloqueiam os servidores do GitHub (403) mas funcionam da internet de casa:
REM Glassdoor, Landing.jobs e Google Jobs. Grava direto no Notion; o resumo diario continua vindo do GitHub.
REM
REM Para rodar sozinho todo dia as 23:30 (o PC precisa estar ligado e com internet), rode UMA vez:
REM   run_windows_extra.bat agendar
cd /d "%~dp0"
if /i "%1"=="agendar" (
  schtasks /Create /F /SC DAILY /ST 23:30 /TN "JobRadarLisboaExtra" /TR "\"%~f0\" auto"
  echo Agendado: todo dia as 23:30. Para remover: schtasks /Delete /TN JobRadarLisboaExtra /F
  pause
  exit /b
)
if not exist .venv (
  python -m venv .venv
  call .venv\Scripts\activate.bat
  pip install -r requirements.txt
) else (
  call .venv\Scripts\activate.bat
)
git pull -q 2>nul
if exist .env.bat goto run
set /p NT="Cole seu NOTION_TOKEN: "
echo set NOTION_TOKEN=%NT%> .env.bat
:run
call .env.bat
python -m radar.main --sources glassdoor,landingjobs,google --hours-old 48 --extra-only >> data\extra_local.log 2>&1
if /i not "%1"=="auto" (
  type data\extra_local.log | more
  pause
)
