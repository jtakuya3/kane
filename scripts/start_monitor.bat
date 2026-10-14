@echo off
rem kane 監視：落ちても30秒後に自動再起動
chcp 65001 > nul
cd /d %~dp0..
:loop
python -m kane.monitor
echo 監視が終了しました。30秒後に再起動します...
timeout /t 30 > nul
goto loop
