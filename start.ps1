[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ServerArguments
)

$ErrorActionPreference = 'Stop'
$serverExitCode = 0
Push-Location -LiteralPath $PSScriptRoot
try {
    if (Get-Command python -ErrorAction SilentlyContinue) {
        & python server.py @ServerArguments
        $serverExitCode = $LASTEXITCODE
    }
    elseif (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 server.py @ServerArguments
        $serverExitCode = $LASTEXITCODE
    }
    else {
        throw 'Python 3.10 or newer is required. Install Python and add it to PATH, then run this script again.'
    }
}
finally {
    Pop-Location
}

exit $serverExitCode
