$ErrorActionPreference='Stop'
$deskRoot=Join-Path $PSScriptRoot 'desk'
$deskInstall=Join-Path $deskRoot 'app/GameMakingDesk.exe'
$deskNotifier=Join-Path $deskRoot 'notifications/DeskNotifier.exe'
foreach($deskName in @('GameMakingDesk','DeskNotifier')){
 if(Get-Process $deskName -ErrorAction SilentlyContinue | Where-Object {$_.Path -in @($deskInstall,$deskNotifier)}){throw 'Close this checkout app and its notification tray helper before building. User data is preserved.'}
}
dotnet publish (Join-Path $PSScriptRoot 'native/desk') -c Release --self-contained false ("-p:ApplicationIcon="+(Join-Path $deskRoot 'app-icon.ico')) -o (Join-Path $deskRoot 'app')
if($LASTEXITCODE -ne 0){throw 'App build failed'}
dotnet publish (Join-Path $PSScriptRoot 'native/notifier') -c Release --self-contained false -o (Join-Path $deskRoot 'notifications')
if($LASTEXITCODE -ne 0){throw 'Notifier build failed'}
Write-Host 'Built. Run: pwsh -File desk/Open-Desk.ps1'
