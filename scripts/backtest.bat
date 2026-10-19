@echo off
chcp 65001 > nul
cd /d %~dp0..
set PY=python
where py > nul 2>&1 && set PY=py -3.11
rem 過去データで検証（early＝早期検知とショート側 / kisei＝規制ライン付近 / float＝浮動株回転率 / backtest＝通常）
set DATA=C:\Users\takuy\Downloads\_backtest_data\intraday_agg*.parquet
if "%~1"=="kisei" (
  %PY% -m kane.kisei "%DATA%"
) else if "%~1"=="float" (
  %PY% -m kane.float_study "%DATA%" %2 %3 %4 %5 %6 %7 %8 %9
) else if "%~1"=="backtest" (
  %PY% -m kane.backtest "%DATA%"
) else (
  %PY% -m kane.early "%DATA%"
)
pause
