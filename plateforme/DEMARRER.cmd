@echo off
cd /d "%~dp0"
echo.
echo Recommand - plateforme locale
echo Ouvrez http://localhost:4173 dans votre navigateur.
echo Gardez cette fenetre ouverte. Ctrl+C pour arreter.
echo.
call npm.cmd start
pause
