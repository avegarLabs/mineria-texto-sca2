@echo off
REM ============================================================
REM  Instalacion del entorno (Windows) para el pipeline de
REM  mineria de texto. Doble clic o ejecutar en CMD / PowerShell.
REM ============================================================
setlocal

REM --- Detectar el interprete de Python (py, luego python) ---
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY ( where python >nul 2>nul && set "PY=python" )
if not defined PY (
    echo [error] No se encontro Python. Instalalo desde https://www.python.org/downloads/
    echo         y marca "Add Python to PATH" durante la instalacion.
    pause
    exit /b 1
)

echo.
echo ^>^> Creando entorno virtual (.venv) ...
%PY% -m venv .venv
if errorlevel 1 ( echo [error] No se pudo crear el entorno virtual. & pause & exit /b 1 )

echo ^>^> Actualizando pip e instalando dependencias (nucleo) ...
call ".venv\Scripts\python.exe" -m pip install --upgrade pip
call ".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 ( echo [error] Fallo la instalacion de dependencias. & pause & exit /b 1 )

echo.
echo ============================================================
echo  Listo. Para empezar, en esta misma carpeta:
echo.
echo    .venv\Scripts\activate
echo    python run_pipeline.py data\sample_corpus.csv -o salida --title "Mi corpus"
echo.
echo  (Opcional) Mineria semantica con BERTopic:
echo    .venv\Scripts\python.exe -m pip install bertopic sentence-transformers umap-learn hdbscan
echo    python run_pipeline.py data\sample_corpus.csv -o salida --use-bertopic
echo ============================================================
echo.
pause
endlocal
