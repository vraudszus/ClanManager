# 2>NUL & @CLS & PUSHD "%~dp0" & "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -nol -nop -ep bypass "[IO.File]::ReadAllText('%~f0')|iex" & POPD & EXIT /B
# used to make PowerShell script double-clickable by turning it into a BAT script

poetry run player-ranking

# Define the path to the .env file
$envFilePath = ".env"

# Check if the file exists
if (-Not (Test-Path $envFilePath)) {
    Write-Error "The .env file was not found."
    exit
}

# Read the contents of the .env file
$envFileContent = Get-Content $envFilePath

# Look for the GSHEET_SPREADSHEET_ID variable
$spreadsheetId = $envFileContent | ForEach-Object {
    if ($_ -match "^GSHEET_SPREADSHEET_ID=(.*)$") {
        return $matches[1]
    }
} | Select-Object -First 1

# Check if the GSHEET_SPREADSHEET_ID variable was found
if (-Not $spreadsheetId) {
    Write-Error "The GSHEET_SPREADSHEET_ID variable was not found in the .env file."
    exit
}

# Construct the URL
$url = "https://docs.google.com/spreadsheets/d/$spreadsheetId"

# Open the URL in the default browser
Start-Process $url

Write-Output "Opened URL: $url"

while ($true) {
    $input = Read-Host "Enter 'update' to recompute ranking or leave blank to exit"
    switch ($input.ToLower()) {
        'update' {
            Write-Host "Rerunning PlayerRanking..."
            poetry run player-ranking
        }
        default {
            Write-Host "Exiting the script..."
            exit
        }
    }
}
