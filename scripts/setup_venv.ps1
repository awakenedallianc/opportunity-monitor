# Create/refresh the project venv (.venv) with numpy<2 (pandas ABI-compatible), pandas, xlrd, openpyxl, lxml + runtime deps.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\setup_venv.ps1
# Re-run install_task.ps1 afterwards so the scheduled task uses .venv\Scripts\pythonw.exe.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$venv = Join-Path $root '.venv'
$env:PYTHONIOENCODING = 'utf-8'; $env:PYTHONUTF8 = '1'
if (-not (Test-Path (Join-Path $venv 'Scripts\python.exe'))) { python -m venv $venv }
$py = Join-Path $venv 'Scripts\python.exe'
& $py -m pip install --upgrade pip -q
& $py -m pip install -q -r (Join-Path $root 'requirements.txt')
& $py -c "import numpy,pandas,xlrd,openpyxl,lxml; print('venv ok: numpy',numpy.__version__,'pandas',pandas.__version__,'xlrd',xlrd.__version__,'openpyxl',openpyxl.__version__,'lxml',lxml.__version__)"
Write-Host ("venv python: {0}" -f $py)
