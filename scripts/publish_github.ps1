# One-shot publish to GitHub Pages (requires an authenticated gh: gh auth status)
# Usage: powershell -ExecutionPolicy Bypass -File scripts\publish_github.ps1 -Repo opportunity-monitor [-Private]
# Saved with UTF-8 BOM so Windows PowerShell 5.1 reads the Chinese text correctly.
param(
  [string]$Repo = 'opportunity-monitor',
  [switch]$Private
)
$ErrorActionPreference = 'Continue'   # native commands write progress to stderr; check $LASTEXITCODE instead
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

function Invoke-Native { param([string]$Cmd) Invoke-Expression $Cmd; return $LASTEXITCODE }

if (-not (Test-Path '.git')) { git init -b main *> $null }
# CLAUDE.md 约定：永远不 git add -A —— 首发布也走白名单（与 scripts/release.py 一致），数据快照单列
$paths = @('src','config','scripts','tests','run.py','requirements.txt','README.md','PROGRESS.md','HANDOVER.md',
           'CLAUDE.md','.gitignore','.github','learning','docs/assets/echarts.min.js','docs/.nojekyll',
           'data/snapshots','data/news_archive') | Where-Object { Test-Path $_ }
git add -- $paths *> $null
git -c user.name='monitor' -c user.email='monitor@local' commit -m "init: opportunity monitor" *> $null

$owner = (gh api user --jq .login)
if (-not $owner) { Write-Host 'gh is not authenticated. Run: gh auth login'; exit 1 }
$vis = if ($Private) { '--private' } else { '--public' }

gh repo view "$owner/$Repo" *> $null
$exists = ($LASTEXITCODE -eq 0)
if (-not $exists) {
  # Create WITHOUT pushing so Pages can be enabled before the first workflow run
  gh repo create $Repo $vis --description "Daily opportunity monitor built from three deep-research reports (rules engine, no LLM)"
  if ($LASTEXITCODE -ne 0) { Write-Host 'gh repo create failed'; exit 1 }
}
$hasOrigin = (git remote) -contains 'origin'
if (-not $hasOrigin) { git remote add origin "https://github.com/$owner/$Repo.git" }

# Pages: source = GitHub Actions (POST for new site; PUT with full body if it already exists)
$body = '{"build_type":"workflow","source":{"branch":"main","path":"/"}}'
$tmp = [System.IO.Path]::GetTempFileName()
Set-Content -Path $tmp -Value $body -Encoding ascii
gh api -X POST "repos/$owner/$Repo/pages" --input $tmp *> $null
if ($LASTEXITCODE -ne 0) {
  gh api -X PUT "repos/$owner/$Repo/pages" --input $tmp *> $null
  if ($LASTEXITCODE -ne 0) { Write-Host 'Warning: could not set Pages source to GitHub Actions via API; the workflow uses configure-pages enablement as a fallback.' }
}
Remove-Item $tmp -ErrorAction SilentlyContinue

git push -u origin main
if ($LASTEXITCODE -ne 0) { Write-Host 'git push failed'; exit 1 }

Write-Host ''
Write-Host ("Pushed to https://github.com/{0}/{1}" -f $owner, $Repo)
Write-Host ("Site (first deploy takes 5-10 minutes; the push itself triggers the workflow): https://{0}.github.io/{1}/" -f $owner, $Repo)
Write-Host 'Watch runs: gh run list --workflow daily.yml'
if (-not $Private) { Write-Host 'Note: a public repo means a public site; docs/reports/ (original reports) is NOT uploaded by default.' }
else { Write-Host 'Note: GitHub Pages on a private repo requires GitHub Pro; on a Free account use a public repo.' }
