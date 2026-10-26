@echo off
chcp 65001 > nul
cd /d %~dp0..
set PY=python
where py > nul 2>&1 && set PY=py -3.11
rem 朝：MS2 と Excel（RSSブック）を開く → RSS接続を押してもらう → 最新版にして監視を起動（落ちても30秒後に再起動）
set MS2=
for %%p in ("C:\Program Files (x86)\Rakuten\MarketSpeed2\MarketSpeed2.exe" "C:\Program Files\Rakuten\MarketSpeed2\MarketSpeed2.exe" "%LOCALAPPDATA%\Rakuten\MarketSpeed2\MarketSpeed2.exe" "C:\Program Files (x86)\MarketSpeedII\MarketSpeedII.exe") do (
  if exist %%p if "%MS2%"=="" set MS2=%%~p
)
if "%MS2%"=="" (
  echo マーケットスピードII の場所が見つからないので手で起動してください（見つけたら morning.bat の MS2= に書く）
) else (
  echo マーケットスピードII を起動: %MS2%
  start "" "%MS2%"
)
timeout /t 8 > nul
set XLS=C:\Users\takuy\Desktop\08_開発案件\kane_data\kane_rss.xlsx
if exist "%XLS%" (
  echo Excel（RSSブック）を開く: %XLS%
  start "" "%XLS%"
)
git pull
echo.
echo ================================================================
echo  1) マーケットスピードII にログイン
echo  2) Excel のリボン「楽天RSS」→「RSS接続」を押す
echo  3) この窓に戻って Enter ^（監視が始まる^）
echo ================================================================
pause
:loop
%PY% -m kane.monitor
echo 監視が終了しました。30秒後に再起動します（止めるときは Ctrl+C → Y）...
timeout /t 30 > nul
goto loop
