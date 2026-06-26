param(
    [string]$Path = "C:\Users\Administrator\xhs_accounts.txt",
    [string]$ApiBase = "http://127.0.0.1:8088"
)

$ErrorActionPreference = "Stop"

$lineNo = 0
$imported = 0
$skipped = 0

Get-Content -LiteralPath $Path -Encoding UTF8 | ForEach-Object {
    $lineNo += 1
    $parts = $_ -split "`t"
    if ($parts.Count -lt 1) {
        $skipped += 1
        return
    }

    try {
        $cookies = $parts[-1] | ConvertFrom-Json
    } catch {
        Write-Output "row=$lineNo skipped=parse_error"
        $skipped += 1
        return
    }

    $names = @($cookies | ForEach-Object { $_.name })
    if (($names -notcontains "a1") -or ($names -notcontains "web_session") -or ($names -notcontains "xsecappid")) {
        Write-Output "row=$lineNo skipped=missing_required_cookie"
        $skipped += 1
        return
    }

    $cookieString = (($cookies | Where-Object { $_.name -and $_.value } | ForEach-Object {
        "$($_.name)=$($_.value)"
    }) -join "; ")

    $label = if ($parts.Count -ge 5 -and $parts[4]) { $parts[4] } else { "account" }
    $name = "file_${lineNo}_$label"
    $body = @{ name = $name; cookie = $cookieString } | ConvertTo-Json -Compress

    try {
        $response = Invoke-RestMethod `
            -Method Post `
            -Uri "$ApiBase/api/accounts" `
            -ContentType "application/json" `
            -Body $body
        Write-Output "row=$lineNo imported account_id=$($response.account_id) name=$name"
        $imported += 1
    } catch {
        Write-Output "row=$lineNo import_failed=$($_.Exception.Message)"
        $skipped += 1
    }
}

Write-Output "summary imported=$imported skipped=$skipped"
