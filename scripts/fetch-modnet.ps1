# Optional: install a MODNet portrait-matting ONNX model for higher-quality
# hair/shoulder edges. This is NOT auto-downloaded by the server because MODNet's
# pretrained weights are commonly released under a NON-COMMERCIAL license
# (e.g. CC BY-NC-SA 4.0). Review the license of whichever weights you use and
# confirm they are cleared for your deployment before relying on them in a
# commercial passport workflow. The MediaPipe selfie segmenter fallback that
# ships with this app is Apache-2.0 and always available.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts/fetch-modnet.ps1 -Url "<direct-onnx-url>"
#
# The model is saved to models/modnet.onnx. The backend expects a MODNet ONNX
# export with a single image input (1x3xHxW, RGB, normalized to [-1, 1]) and a
# single-channel alpha output in [0, 1]. Once present, the server uses it
# automatically and reports it via /api/health and the pipeline panel.

param(
  [string]$Url = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$modelDir = Join-Path $repoRoot "models"
$target = Join-Path $modelDir "modnet.onnx"

if (-not $Url) {
  Write-Host "No -Url provided." -ForegroundColor Yellow
  Write-Host ""
  Write-Host "Pass a direct download URL to a MODNet ONNX export, e.g.:"
  Write-Host "  scripts/fetch-modnet.ps1 -Url ""https://example.com/modnet.onnx"""
  Write-Host ""
  Write-Host "LICENSE NOTE: MODNet pretrained weights are typically non-commercial." -ForegroundColor Yellow
  Write-Host "Verify the weights you choose are licensed for your use. Without this"
  Write-Host "model the app falls back to the bundled MediaPipe segmenter (Apache-2.0)."
  exit 0
}

New-Item -ItemType Directory -Force -Path $modelDir | Out-Null
Write-Host "Downloading MODNet ONNX from $Url ..."
Invoke-WebRequest -Uri $Url -OutFile $target

$size = (Get-Item $target).Length
if ($size -lt 100000) {
  Remove-Item $target -Force
  Write-Error "Downloaded file is too small ($size bytes); not a valid model. Removed."
  exit 1
}

Write-Host "Saved $target ($([math]::Round($size/1MB,1)) MB)." -ForegroundColor Green

# Validate it loads in onnxruntime and has the expected single-input shape.
$py = @"
import sys
try:
    import onnxruntime as ort
    s = ort.InferenceSession(r'$target', providers=['CPUExecutionProvider'])
    i = s.get_inputs()[0]
    o = s.get_outputs()[0]
    print('OK input', i.name, i.shape, '| output', o.name, o.shape)
except Exception as e:
    print('VALIDATION FAILED:', e); sys.exit(1)
"@
python -c $py
if ($LASTEXITCODE -ne 0) {
  Write-Warning "Model saved but failed onnxruntime validation. The server will ignore it and use the MediaPipe fallback."
} else {
  Write-Host "MODNet is ready. Restart the server to use it." -ForegroundColor Green
}
