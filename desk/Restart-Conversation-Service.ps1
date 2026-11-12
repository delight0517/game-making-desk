$ErrorActionPreference='Stop'
$deskRoot=$PSScriptRoot
$deskState=Invoke-RestMethod 'http://127.0.0.1:8767/api/desk' -TimeoutSec 3
if($deskState.agent.status -in @('running','queued')){throw '기획 작업이 실행 중입니다. 완료하거나 앱에서 중지한 후 실행해 주세요.'}
$deskOwner=Get-NetTCPConnection -LocalPort 8767 -State Listen | Select-Object -ExpandProperty OwningProcess -Unique
if(@($deskOwner).Count -ne 1){throw '서버 소유자를 확인할 수 없습니다.'}
$deskServer=Get-CimInstance Win32_Process -Filter "ProcessId=$deskOwner"
$deskSource=Join-Path $deskRoot 'server.py'
if($deskServer.Name -ne 'python.exe' -or -not $deskServer.CommandLine.Contains($deskSource)){throw '다른 서버는 종료하지 않습니다.'}
Stop-Process -Id $deskOwner -ErrorAction Stop
Wait-Process -Id $deskOwner -Timeout 10 -ErrorAction SilentlyContinue
Start-Process -FilePath (Get-Command python).Source -ArgumentList @('-u',('"'+$deskSource+'"')) -WorkingDirectory $deskRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $deskRoot 'server.log') -RedirectStandardError (Join-Path $deskRoot 'server-error.log')
for($deskAttempt=0;$deskAttempt -lt 30;$deskAttempt++){
    Start-Sleep -Milliseconds 200
    try{$deskChat=Invoke-RestMethod 'http://127.0.0.1:8767/api/chat' -TimeoutSec 1;Write-Host '몰입 대화 서비스 적용 완료. 앱을 다시 열 필요는 없습니다.';exit 0}catch{}
}
throw '새 대화 서비스 확인 실패. server-error.log를 확인해 주세요.'
