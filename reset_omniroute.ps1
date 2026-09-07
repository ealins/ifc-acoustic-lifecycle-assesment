# Script to completely reset OmniRoute resilience, cooldowns, and lockouts.
Write-Host "Resetting OmniRoute resilience state..." -ForegroundColor Cyan
node "$PSScriptRoot\reset_resilience.mjs"
Write-Host "Done! All provider cooldowns and rate-limit locks have been cleared." -ForegroundColor Green
