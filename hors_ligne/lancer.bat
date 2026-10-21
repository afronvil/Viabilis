@echo off
rem Viabilis hors ligne (Windows) : double-cliquez sur ce fichier. Voir LISEZMOI.txt.
chcp 65001 >nul
cd /d "%~dp0"
set "KIT=kit.json"
if not exist "%KIT%" for %%f in (viabilis_kit_*.json) do set "KIT=%%f"
if not exist "%KIT%" (
  echo Kit introuvable : copiez dans ce dossier le fichier telecharge par votre enseignant ^(kit.json^).
  pause
  exit /b 1
)
set "PY="
if exist "python\python.exe" set "PY=python\python.exe"
if not defined PY ( where py >nul 2>nul && set "PY=py -3" )
if not defined PY ( where python >nul 2>nul && set "PY=python" )
if not defined PY (
  echo Python 3 est necessaire : installez-le depuis python.org, ou placez une version portable dans le dossier python. Voir LISEZMOI.txt.
  pause
  exit /b 1
)
%PY% ..\serveur\serveur.py --hors-ligne "%KIT%" --port 8765
pause
