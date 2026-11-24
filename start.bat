@echo off
REM Duplo-clique: sincroniza, abre o navegador e serve o projeto (a pasta que contem agLocalSite) em http://localhost:8000/
REM Feche a janela ou Ctrl+C para parar. Outra porta: start.bat 8001
cd /d "%~dp0"
REM Um unico interpretador: "py" (instalador oficial) ou, se nao houver, "python". Nunca os dois em sequencia,
REM senao um erro ou Ctrl+C no primeiro abriria uma segunda copia do servidor.
where py >nul 2>nul
if not errorlevel 1 (
  py -3 serve.py %*
  goto fim
)
python serve.py %*
:fim
echo.
echo Se der erro "python nao reconhecido", instale o Python em https://www.python.org/downloads/
pause
