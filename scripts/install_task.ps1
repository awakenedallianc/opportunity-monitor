# Register the Windows scheduled task: 2 minutes after logon + daily 08:30 fallback.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\install_task.ps1
# (File is saved with UTF-8 BOM so Windows PowerShell 5.1 reads the Chinese text correctly.)
$ErrorActionPreference = 'Stop'
$TaskName = 'OpportunityMonitor-Daily'
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$py = Join-Path (Split-Path -Parent (Get-Command python).Source) 'pythonw.exe'
if (-not (Test-Path $py)) { $py = (Get-Command python).Source }
$script = Join-Path $root 'scripts\local_boot.py'

$action = New-ScheduledTaskAction -Execute $py -Argument ('"' + $script + '"') -WorkingDirectory $root
$t1 = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$t1.Delay = 'PT2M'
$t2 = New-ScheduledTaskTrigger -Daily -At 08:30
$settings = New-ScheduledTaskSettingsSet -RunOnlyIfNetworkAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 10) `
  -ExecutionTimeLimit (New-TimeSpan -Minutes 40) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $t1, $t2 -Settings $settings `
  -Description '机会监控：开机后拉取最新数据、本地生成页面并打开；云端过期则触发 GitHub Actions 补跑' -Force | Out-Null
Write-Host ("Registered task '{0}': at logon (+2 min) and daily 08:30." -f $TaskName)
Write-Host ("python: {0}" -f $py)
Write-Host ("script: {0}" -f $script)
Write-Host ("Run now: Start-ScheduledTask -TaskName {0}" -f $TaskName)
Write-Host ("Remove:  Unregister-ScheduledTask -TaskName {0} -Confirm:`$false" -f $TaskName)
