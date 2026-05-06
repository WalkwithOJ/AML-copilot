$rawInput = [Console]::In.ReadToEnd()
try { $json = $rawInput | ConvertFrom-Json } catch { exit 0 }
$cmd = $json.tool_input.command
if (-not $cmd) { exit 0 }
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"$timestamp  $cmd" | Add-Content "$PSScriptRoot\..\command-log.txt"
exit 0
