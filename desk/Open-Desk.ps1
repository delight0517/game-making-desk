$ErrorActionPreference = 'Stop'
$deskRoot = $PSScriptRoot
$deskUrl = 'http://127.0.0.1:8767/'
$deskRunning = $false
try {
    $deskResponse = Invoke-RestMethod -Uri ($deskUrl + 'api/desk') -TimeoutSec 2
    $deskRunning = $deskResponse.brief.project -eq '용암 요새'
} catch { }
if (-not $deskRunning) {
    if (Get-NetTCPConnection -LocalPort 8767 -ErrorAction SilentlyContinue | Where-Object { $_.State -eq 'Listen' -and $_.OwningProcess -gt 0 }) {
        throw '8767 포트를 다른 앱이 사용 중입니다. 서버를 임의로 종료하지 않았습니다.'
    }
    $deskPython = (Get-Command python -ErrorAction Stop).Source
    Start-Process -FilePath $deskPython -ArgumentList @('-u', ('"' + (Join-Path $deskRoot 'server.py') + '"')) -WorkingDirectory $deskRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $deskRoot 'server.log') -RedirectStandardError (Join-Path $deskRoot 'server-error.log') | Out-Null
    for ($deskAttempt = 0; $deskAttempt -lt 25; $deskAttempt++) {
        Start-Sleep -Milliseconds 200
        try { $deskResponse = Invoke-RestMethod -Uri ($deskUrl + 'api/desk') -TimeoutSec 1; $deskRunning = $deskResponse.brief.project -eq '용암 요새'; if ($deskRunning) { break } } catch { }
    }
    if (-not $deskRunning) { throw '작업판 서버가 시작되지 않았습니다. server-error.log를 확인해 주세요.' }
}
$deskNotifier = Join-Path $deskRoot 'notifications\DeskNotifier.exe'
if (Test-Path -LiteralPath $deskNotifier) {
    $deskNotifierRunning = Get-Process DeskNotifier -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $deskNotifier }
    if (-not $deskNotifierRunning) { Start-Process -FilePath $deskNotifier -WorkingDirectory $deskRoot -WindowStyle Hidden | Out-Null }
}
$deskApp = Join-Path $deskRoot 'app\GameMakingDesk.exe'
if (Test-Path -LiteralPath $deskApp) {
    if(Get-Process GameMakingDesk -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $deskApp -and $_.MainWindowHandle -ne 0 }) { return }
    Start-Process -FilePath $deskApp -WorkingDirectory $deskRoot | Out-Null
    return
}
$deskEdge = @('C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe','C:\Program Files\Microsoft\Edge\Application\msedge.exe') | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $deskEdge) { throw '작업판을 열 Microsoft Edge를 찾지 못했습니다.' }
$deskProfile = [IO.Path]::GetFullPath((Join-Path $deskRoot '..\..\work\game-making-desk-profile'))
Start-Process -FilePath $deskEdge -ArgumentList @('--app=' + $deskUrl, '--user-data-dir="' + $deskProfile + '"', '--window-size=1280,900', '--no-first-run', '--no-default-browser-check') | Out-Null
