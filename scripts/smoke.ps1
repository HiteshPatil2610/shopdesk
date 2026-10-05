param([Parameter(Mandatory=$true)][uri]$BaseUrl)
$ErrorActionPreference = 'Stop'
if ($BaseUrl.Scheme -notin @('http', 'https') -or $BaseUrl.UserInfo -or $BaseUrl.Query -or $BaseUrl.Fragment -or $BaseUrl.AbsolutePath -ne '/') {
    throw 'BaseUrl must be an exact HTTP(S) origin without credentials or a path.'
}
$origin = $BaseUrl.GetLeftPart([System.UriPartial]::Authority)
foreach ($path in @('/', '/admin/products', '/pos', '/api/health')) {
    $result = Invoke-WebRequest -Uri "$origin$path" -MaximumRedirection 5
    if ($result.StatusCode -ne 200) { throw "Unexpected status for $path" }
    if ($path -eq '/api/health') {
        $health = $result.Content | ConvertFrom-Json
        if ($health.app -ne 'shopdesk' -or $health.status -ne 'ok' -or $health.db -ne 'ok') { throw 'Unexpected health response' }
        if ($result.Headers['Access-Control-Allow-Origin']) { throw 'API unexpectedly permits cross-origin reads' }
    } elseif ($result.Headers['Content-Type'] -notmatch 'text/html') { throw "$path did not serve the SPA" }
    Write-Host "OK $path"
}
try {
    Invoke-WebRequest -Uri "$origin/api/auth/me" | Out-Null
    throw 'Unauthenticated request unexpectedly succeeded'
} catch {
    if ([int]$_.Exception.Response.StatusCode -ne 401) { throw }
    Write-Host 'OK /api/auth/me rejects unauthenticated requests'
}
