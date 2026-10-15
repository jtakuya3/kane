@echo off
chcp 65001 > nul
cd /d %~dp0..
set PY=python
where py > nul 2>&1 && set PY=py -3.11
rem 全銘柄の一覧を更新（JPX の data_j.xls を Downloads に置いてから）
%PY% -m kane.universe C:\Users\takuy\Downloads\data_j.xls
pause
