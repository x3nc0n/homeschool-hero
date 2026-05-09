[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ComposeArgs
)

$ErrorActionPreference = 'Stop'
$RootDir = Split-Path -Parent $PSScriptRoot
Set-Location $RootDir

if (-not (Test-Path '.env')) {
    Copy-Item '.env.example' '.env'
    $envPath = Join-Path $RootDir '.env'
    $secret = [Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(48))
    $content = Get-Content $envPath -Raw
    $content = $content -replace 'SECRET_KEY=super-secret-change-me', "SECRET_KEY=$secret"
    Set-Content -Path $envPath -Value $content -NoNewline
    Write-Host 'Created .env from .env.example with a generated SECRET_KEY.'
}

& docker compose up --build @ComposeArgs
