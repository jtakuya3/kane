# デスクトップに bat のショートカットを作る
param([string]$Src)
$d = [Environment]::GetFolderPath('Desktop')
$w = New-Object -ComObject WScript.Shell
$list = @(
  @('kane 朝 監視', 'morning.bat'),
  @('kane 夜 更新', 'night.bat'),
  @('kane ライン', 'line.bat'),
  @('kane 検証', 'backtest.bat'),
  @('kane 答え合わせ', 'evaluate.bat')
)
foreach ($p in $list) {
  $s = $w.CreateShortcut((Join-Path $d ($p[0] + '.lnk')))
  $s.TargetPath = Join-Path $Src $p[1]
  $s.WorkingDirectory = $Src
  $s.Save()
  Write-Host ("作成: " + (Join-Path $d ($p[0] + '.lnk')))
}
Write-Host ("デスクトップ: " + $d)
