$rawInput = [Console]::In.ReadToEnd()
try { $json = $rawInput | ConvertFrom-Json } catch { exit 0 }
$file = $json.tool_input.file_path
if (-not $file) { exit 0 }
if ($file -match "\.py$") {
    python -m black $file 2>$null
}
exit 0
