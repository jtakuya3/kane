@echo off
chcp 65001 > nul
cd /d %~dp0..
set PY=python
where py > nul 2>&1 && set PY=py -3.11
rem TDnet（適時開示）の一覧と最新PDFを読んで、R18 の判定が動くか確認する
%PY% -m kane.tdnet --check
pause
