@echo off
REM Duplo-clique neste arquivo para atualizar o site com o conteudo mais recente dos .md
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 sync.py
  goto fim
)
python sync.py
:fim
echo.
echo Se der erro "python nao reconhecido", instale o Python em https://www.python.org/downloads/
pause
