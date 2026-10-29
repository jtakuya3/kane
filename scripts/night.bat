@echo off
chcp 65001 > nul
cd /d %~dp0..
set PY=python
where py > nul 2>&1 && set PY=py -3.11
rem 夜：最新版にして、平均出来高・今年の最大出来高を更新（約30分）→ 乖離ラインを表示
rem 追加で見たい銘柄は下の EXTRA にスペース区切りで書く（固定監視銘柄は自動）
set EXTRA=
for /f "tokens=1-3 delims=/ " %%a in ("%date%") do set D=%%a%%b%%c
set OUT=..\kane_data\night_%D%.txt
git pull
echo ---- baseline（平均出来高・年初来最大・終値）---- > "%OUT%"
%PY% -m kane.baseline daily >> "%OUT%" 2>&1
type "%OUT%"
echo.
echo ---- 固定監視銘柄の乖離ライン（30%%・20%%・15%%）---- >> "%OUT%"
%PY% -m kane.line_watch >> "%OUT%"
if not "%EXTRA%"=="" (
  echo ---- 追加銘柄 %EXTRA% ---- >> "%OUT%"
  %PY% -m kane.line %EXTRA% >> "%OUT%"
)
type "%OUT%"
echo.
echo ↑ 同じ内容を %OUT% に保存した。Claude に「規制チェック」と一緒に貼る
pause
