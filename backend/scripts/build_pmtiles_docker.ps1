$ErrorActionPreference = "Stop"

$Image = "pax1933-tippecanoe:local"
$BackendDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$DataDir = Join-Path $BackendDir "data"
$TilesDir = Join-Path $DataDir "tiles"
$PmtilesPath = Join-Path $TilesDir "pax1933_map.pmtiles"
$DockerDir = Join-Path $BackendDir "docker\tippecanoe"
$DockerfilePath = Join-Path $DockerDir "Dockerfile"
New-Item -ItemType Directory -Force -Path $TilesDir | Out-Null

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  throw "Docker is not running. Start Docker Desktop and retry."
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
  throw "Docker is not running. Start Docker Desktop and retry."
}

if (-not (Test-Path -LiteralPath $DockerfilePath -PathType Leaf)) {
  throw "Tippecanoe Dockerfile was not found: $DockerfilePath"
}

$required = @(
  "processed/countries_1933.geojson",
  "processed/regions_1933.geojson",
  "processed/microstates_1933.geojson",
  "processed/rivers_1933.geojson",
  "processed/country_label_lines_1933.geojson",
  "processed/country_label_points_1933.geojson",
  "processed/region_label_points_1933.geojson",
  "processed/microstate_label_points_1933.geojson"
)

foreach ($relative in $required) {
  $path = Join-Path $DataDir $relative
  if (-not (Test-Path $path)) {
    throw "Missing processed layer: $relative. Run the preparation scripts first."
  }
}

Write-Host "Building local Tippecanoe Docker image: $Image"
docker build `
  -t $Image `
  -f $DockerfilePath `
  $DockerDir
if ($LASTEXITCODE -ne 0) {
  throw "Failed to build the local Tippecanoe Docker image. Check the Docker build output above and retry."
}

if (Test-Path -LiteralPath $PmtilesPath) {
  Remove-Item -LiteralPath $PmtilesPath -Force
}

Write-Host "Running Tippecanoe in Docker..."
docker run --rm `
  -v "${DataDir}:/data" `
  $Image `
  --force `
  -o /data/tiles/pax1933_map.pmtiles `
  -Z 0 `
  -z 8 `
  --drop-densest-as-needed `
  --extend-zooms-if-still-dropping `
  --detect-shared-borders `
  --no-tile-size-limit `
  -L countries:/data/processed/countries_1933.geojson `
  -L regions:/data/processed/regions_1933.geojson `
  -L microstates:/data/processed/microstates_1933.geojson `
  -L rivers:/data/processed/rivers_1933.geojson `
  -L country_label_lines:/data/processed/country_label_lines_1933.geojson `
  -L country_label_points:/data/processed/country_label_points_1933.geojson `
  -L region_label_points:/data/processed/region_label_points_1933.geojson `
  -L microstate_label_points:/data/processed/microstate_label_points_1933.geojson

if ($LASTEXITCODE -ne 0) {
  throw "Tippecanoe Docker run failed. Check the Docker output above and retry."
}

if (-not (Test-Path -LiteralPath $PmtilesPath -PathType Leaf)) {
  throw "PMTiles file was not created at expected path: $PmtilesPath"
}

$sizeBytes = (Get-Item -LiteralPath $PmtilesPath).Length
if ($sizeBytes -le 0) {
  throw "PMTiles file is empty: $PmtilesPath"
}

Write-Host "saved: $PmtilesPath"
Write-Host "sizeBytes: $sizeBytes"
