$ErrorActionPreference = "Stop"

function Stop-WithError([string]$Message) {
    Write-Error "HATA: $Message"
    exit 1
}

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Stop-WithError "Docker bulunamadı. Docker Desktop kurulmalı."
}

docker info *> $null
if ($LASTEXITCODE -ne 0) { Stop-WithError "Docker servisi çalışmıyor." }
docker compose version *> $null
if ($LASTEXITCODE -ne 0) { Stop-WithError "Docker Compose v2 bulunamadı." }
$dockerMajor = [int]((docker version --format '{{.Server.Version}}').Split('.')[0])
$composeMajor = [int]((docker compose version --short).TrimStart('v').Split('.')[0])
if ($dockerMajor -lt 24) { Stop-WithError "Docker 24 veya daha yeni olmalı." }
if ($composeMajor -lt 2) { Stop-WithError "Docker Compose v2 gerekli." }

$dockerMemory = [int64](docker info --format '{{.MemTotal}}')
if ($LASTEXITCODE -ne 0) { Stop-WithError "Docker bellek miktarı okunamadı." }
if ($dockerMemory -lt 4GB) { Stop-WithError "Docker için en az 4 GB bellek ayrılmalı." }

$architecture = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString().ToLowerInvariant()
if ($architecture -notin @("x64", "arm64")) {
    Stop-WithError "Desteklenmeyen CPU mimarisi: $architecture"
}
$platform = if ($architecture -eq "x64") { "amd64" } else { "arm64" }

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host ".env oluşturuldu. OpenSky bilgilerini bu dosyaya yazabilirsiniz."
}

$portLine = Get-Content ".env" | Where-Object { $_ -match '^APP_PORT=' } | Select-Object -Last 1
$appPort = if ($portLine) { [int]($portLine -replace '^APP_PORT=', '') } else { 5173 }
if ($appPort -lt 1 -or $appPort -gt 65535) { Stop-WithError "APP_PORT 1-65535 arasında olmalı." }

$listener = Get-NetTCPConnection -LocalPort $appPort -State Listen -ErrorAction SilentlyContinue
if ($listener) { Stop-WithError "127.0.0.1:$appPort kullanımda." }

$areaLine = Get-Content ".env" | Where-Object { $_ -match '^OPENSKY_AREA_MODE=' } | Select-Object -Last 1
$areaMode = if ($areaLine) { $areaLine -replace '^OPENSKY_AREA_MODE=', '' } else { "turkey" }
if ($areaMode -notin @("turkey", "global")) { Stop-WithError "OPENSKY_AREA_MODE turkey veya global olmalı." }
$requiredDisk = if ($areaMode -eq "global") { 30GB } else { 10GB }
$requiredDiskLabel = if ($areaMode -eq "global") { 30 } else { 10 }
$drive = (Get-Item $projectRoot).PSDrive
if (-not $drive) { Stop-WithError "Proje diski belirlenemedi." }
if ($drive.Free -lt $requiredDisk) { Stop-WithError "En az $requiredDiskLabel GB boş disk alanı gerekli." }

$archive = "offline-images-$platform.tar.gz"
if (Test-Path $archive) {
    if (Test-Path "SHA256SUMS.txt") {
        foreach ($line in Get-Content "SHA256SUMS.txt") {
            if ($line -notmatch '^([0-9a-fA-F]{64})\s+\*?(.+)$') {
                Stop-WithError "Geçersiz SHA256SUMS.txt satırı."
            }
            $expectedHash = $Matches[1].ToLowerInvariant()
            $fileName = $Matches[2]
            if (-not (Test-Path -LiteralPath $fileName)) { Stop-WithError "Checksum dosyası eksik: $fileName" }
            $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $fileName).Hash.ToLowerInvariant()
            if ($actualHash -ne $expectedHash) { Stop-WithError "SHA-256 doğrulaması başarısız: $fileName" }
        }
    }
    Write-Host "Offline image arşivi Docker içine yükleniyor..."
    docker load --input $archive | Out-Null
    if ($LASTEXITCODE -ne 0) { Stop-WithError "Offline image arşivi yüklenemedi." }

    $requiredImages = docker compose config --images
    if ($LASTEXITCODE -ne 0) { Stop-WithError "Compose image listesi okunamadı." }
    foreach ($image in $requiredImages) {
        docker image inspect $image *> $null
        if ($LASTEXITCODE -ne 0) { Stop-WithError "Offline pakette image eksik: $image" }
    }
}

docker compose config --quiet
if ($LASTEXITCODE -ne 0) { Stop-WithError "Compose yapılandırması geçersiz." }

Write-Host "Kontroller başarılı: mimari=$platform, port=$appPort, gereken_disk=${requiredDiskLabel}GB"
Write-Host "Başlatmak için: docker compose up -d"
