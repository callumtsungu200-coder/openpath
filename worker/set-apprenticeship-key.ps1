# Saves the GOV.UK Display Advert API key to worker/.env. Typing stays hidden on screen.
$secure = Read-Host -AsSecureString 'Paste your Display Advert API key, then press Enter'
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
$key = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer).Trim()
[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
if (-not $key) { Write-Host 'Nothing entered, so nothing was saved.'; exit 1 }

$path = Join-Path $PSScriptRoot '.env'
$lines = @()
if (Test-Path $path) { $lines = @(Get-Content $path | Where-Object { $_ -notmatch '^\s*FIND_APPRENTICESHIP_API_KEY\s*=' }) }
$lines += "FIND_APPRENTICESHIP_API_KEY=$key"
[IO.File]::WriteAllLines($path, $lines)
Write-Host 'Saved. Go back to the chat and say it is done.'
