@echo off
chcp 65001 > nul
cd /d %~dp0..
set PY=python
where py > nul 2>&1 && set PY=py -3.11
rem 夜：最新版にして、平均出来高・今年の最大出来高を更新（約30分）→ 乖離ラインを表示
rem 追加で見たい銘柄は下の EXTRA にスペース区切りで書く（固定監視銘柄は自動）
set EXTRA=3909 6721 4382 4616 5018
git pull
%PY% -m kane.baseline daily
echo.
echo ---- 固定監視銘柄の乖離ライン（30%%・20%%・15%%）----
%PY% -m kane.line_watch
if not "%EXTRA%"=="" (
  echo.
  echo ---- 追加銘柄 %EXTRA% ----
  %PY% -m kane.line %EXTRA%
)
echo.
echo ↑ この画面を右クリック→「すべて選択」→Enter でコピーして、Claude に「規制チェック」と一緒に貼る
pause
