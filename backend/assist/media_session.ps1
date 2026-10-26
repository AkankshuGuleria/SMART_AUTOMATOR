# media_session.ps1 — what is playing right now, from Windows' media session
# (the same source as the volume flyout: Spotify, browsers, any media app).
# Prints one JSON object: {app, title, artist, status} or {"none": true}.
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Runtime.WindowsRuntime

$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
})[0]
function Await($op, [Type]$type) {
    $task = $asTask.MakeGenericMethod($type).Invoke($null, @($op))
    $task.Wait(-1) | Out-Null
    $task.Result
}

[Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager, Windows.Media.Control, ContentType = WindowsRuntime] | Out-Null
$mgr = Await ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]::RequestAsync()) ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager])
$session = $mgr.GetCurrentSession()
if ($null -eq $session) { '{"none": true}'; exit 0 }
$props = Await ($session.TryGetMediaPropertiesAsync()) ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionMediaProperties])
$info = $session.GetPlaybackInfo()
[pscustomobject]@{
    app    = $session.SourceAppUserModelId
    title  = $props.Title
    artist = $props.Artist
    album  = $props.AlbumTitle
    status = "$($info.PlaybackStatus)"
} | ConvertTo-Json -Compress
