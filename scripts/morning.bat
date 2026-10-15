@echo off
chcp 65001 > nul
cd /d %~dp0..
set PY=python
where py > nul 2>&1 && set PY=py -3.11
rem 朝：最新版にして監視を起動（落ちても30秒後に再起動）
rem 先に マーケットスピードII にログインし、Excel で「RSS接続」しておくこと
git pull
:loop
%PY% -m kane.monitor
echo 監視が終了しました。30秒後に再起動します（止めるときは Ctrl+C → Y）...
timeout /t 30 > nul
goto loop
