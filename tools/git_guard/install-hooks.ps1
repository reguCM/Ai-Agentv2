# Optional hook installer — refuses non-sandbox targets unless -IUnderstand

param(
  [switch]$IUnderstand
)

$ErrorActionPreference = "Stop"
$Target = $env:GIT_GUARD_HOOK_TARGET
if (-not $Target) {
  Write-Error "Set GIT_GUARD_HOOK_TARGET to a .git/hooks directory"
  exit 1
}

$TargetFull = [System.IO.Path]::GetFullPath($Target)
$SandboxPrefix = "D:\AI-Agent-worktrees\sandboxes\"
$underSandbox = $TargetFull.StartsWith($SandboxPrefix, [System.StringComparison]::OrdinalIgnoreCase)

if (-not $underSandbox -and -not $IUnderstand) {
  Write-Error @"
Refusing to install hooks outside Dedicated Sandbox parent.
Target: $TargetFull
Re-run with -IUnderstand if you really intend this (still never recommended for stabilize / AI-Agent.git).
"@
  exit 1
}

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
New-Item -ItemType Directory -Force -Path $TargetFull | Out-Null
Copy-Item -Force (Join-Path $Root "hooks\pre-commit.sample") (Join-Path $TargetFull "pre-commit")
Copy-Item -Force (Join-Path $Root "hooks\pre-push.sample") (Join-Path $TargetFull "pre-push")
Write-Host "Installed pre-commit and pre-push into $TargetFull"
Write-Host "Remember to set GIT_GUARD_ROOT=$Root and GIT_GUARD_CONFIG=..."
