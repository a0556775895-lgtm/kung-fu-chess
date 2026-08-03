# Run the full suite from the repository root and keep generated test files in DOCS/tests.
$projectRoot = Split-Path -Parent $PSScriptRoot
$reportsDirectory = Join-Path $PSScriptRoot "tests\reports"
New-Item -ItemType Directory -Force -Path $reportsDirectory | Out-Null

Push-Location $projectRoot
try {
    python -m pytest DOCS/tests `
        -o cache_dir=DOCS/tests/.pytest_cache `
        --cov=. `
        --cov-config=DOCS/config/coverage.ini `
        --cov-report=term-missing `
        --cov-report=html:DOCS/tests/reports/coverage `
        @args
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
