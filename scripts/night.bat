@echo off
chcp 65001 > nul
cd /d %~dp0..
set PY=python
where py > nul 2>&1 && set PY=py -3.11
rem 夜：最新版にして、平均出来高・今年の最大出来高を更新（約30分）→ 乖離ラインを表示
git pull
%PY% -m kane.baseline daily
echo.
echo ---- 固定監視銘柄の乖離ライン（30%%・20%%・15%%）----
%PY% -m kane.line_watch
pause
