param([Parameter(Mandatory=$true)][ValidatePattern('^[a-zA-Z0-9.-]+$')][string]$Domain)
$ErrorActionPreference = 'Stop'
foreach ($endpoint in @("https://admin-api.$Domain/api/health", "https://pos-api.$Domain/api/health", "https://admin.$Domain", "https://pos.$Domain", "https://admin.$Domain/products")) {
    $result = Invoke-WebRequest -Uri $endpoint -MaximumRedirection 5
    if ($result.StatusCode -ne 200) { throw "Unexpected status for $endpoint" }
    Write-Host "OK $endpoint"
}
foreach ($server in @('admin-api','pos-api')) {
    try {
        Invoke-WebRequest -Uri "https://$server.$Domain/api/auth/me" | Out-Null
        throw "Unauthenticated request unexpectedly succeeded: $server"
    } catch {
        if ([int]$_.Exception.Response.StatusCode -ne 401) { throw }
        Write-Host "OK $server rejects unauthenticated requests"
    }
}
