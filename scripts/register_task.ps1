$ErrorActionPreference = 'Stop'
$name = '每日行业日报-每日任务'
$action = New-ScheduledTaskAction -Execute 'G:\code\github-heat\daily-industry-digest\scripts\run_industry_daily.bat' -WorkingDirectory 'G:\code\github-heat\daily-industry-digest'
$trigger = New-ScheduledTaskTrigger -Daily -At '07:20'
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings -Description '每天确认行业日报已提交到 GitHub（云端没产出则本地补跑推送），并镜像到 Gitee / AtomGit / 极狐' -Force | Out-Null
$t = Get-ScheduledTask -TaskName $name
$i = Get-ScheduledTaskInfo -TaskName $name
Write-Output ('已注册任务: ' + $t.TaskName)
Write-Output ('  状态: ' + $t.State)
Write-Output ('  下次运行: ' + $i.NextRunTime)
Write-Output ('  动作: ' + $t.Actions[0].Execute)