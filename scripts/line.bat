@echo off
chcp 65001 > nul
cd /d %~dp0..
set PY=python
where py > nul 2>&1 && set PY=py -3.11
rem 乖離ラインを計算：line.bat 4498 3909 6721 のように銘柄コードを付けて実行（省略時は固定監視銘柄）
for /f "tokens=1-3 delims=/ " %%a in ("%date%") do set D=%%a%%b%%c
set OUT=..\kane_data\line_%D%.txt
if "%~1"=="" (
  %PY% -m kane.line_watch > "%OUT%"
) else (
  %PY% -m kane.line %* > "%OUT%"
)
type "%OUT%"
echo.
echo ↑ %OUT% に保存した
pause
