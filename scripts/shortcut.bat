@echo off
chcp 65001 > nul
rem デスクトップに bat のショートカットを作る（一度だけ実行）
set SRC=%~dp0
powershell -NoProfile -Command ^
  "$d=[Environment]::GetFolderPath('Desktop'); $w=New-Object -ComObject WScript.Shell;" ^
  "foreach($p in @(@('kane 朝 監視','morning.bat'),@('kane 夜 更新','night.bat'),@('kane ライン','line.bat'),@('kane 検証','backtest.bat'),@('kane 答え合わせ','evaluate.bat'))){" ^
  "$s=$w.CreateShortcut(\"$d\\$($p[0]).lnk\"); $s.TargetPath=\"%SRC%$($p[1])\"; $s.WorkingDirectory=\"%SRC%\"; $s.Save()}"
echo デスクトップに「kane 朝 監視」「kane 夜 更新」「kane ライン」「kane 検証」「kane 答え合わせ」を作りました
pause
