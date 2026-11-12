param([switch]$PrepareOnly)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$runtimeRoot = Join-Path $projectRoot '.runtimes'
$dataRoot = Join-Path $projectRoot 'data'
$transcribing = $false

function Get-Digest([string]$Path) {
    $algorithm = [Security.Cryptography.SHA256]::Create()
    $stream = [IO.File]::OpenRead($Path)
    try {
        return [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-', '').ToLowerInvariant()
    }
    finally {
        $stream.Dispose()
        $algorithm.Dispose()
    }
}

function Expand-VerifiedArchive([string]$Archive, [string]$Destination) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $destinationPrefix = [IO.Path]::GetFullPath($Destination) + [IO.Path]::DirectorySeparatorChar
    $package = [IO.Compression.ZipFile]::OpenRead($Archive)
    try {
        $expandedBytes = 0L
        foreach ($entry in $package.Entries) {
            $target = [IO.Path]::GetFullPath((Join-Path $Destination $entry.FullName))
            if (-not $target.StartsWith($destinationPrefix, [StringComparison]::OrdinalIgnoreCase)) {
                throw 'Invalid uv archive path'
            }
            $expandedBytes += $entry.Length
            if ($expandedBytes -gt 268435456) { throw 'uv archive exceeds its size limit' }
            if ([string]::IsNullOrEmpty($entry.Name)) {
                [IO.Directory]::CreateDirectory($target) | Out-Null
            }
            else {
                [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($target)) | Out-Null
                [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $target, $true)
            }
        }
    }
    finally { $package.Dispose() }
}

function Get-LocalUv {
    $metadata = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'uv.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $uvRoot = Join-Path $runtimeRoot ('uv-' + $metadata.version)
    $executable = Join-Path $uvRoot 'uv.exe'
    $marker = Join-Path $uvRoot 'uv.sha256'
    if ((Test-Path -LiteralPath $executable) -and (Test-Path -LiteralPath $marker)) {
        if ((Get-Digest $executable) -eq (Get-Content -LiteralPath $marker -Raw).Trim()) {
            return $executable
        }
    }
    New-Item -ItemType Directory -Path $uvRoot -Force | Out-Null
    $archive = Join-Path $uvRoot 'download.zip'
    Write-Host '正在下载并校验 uv…'
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $metadata.url -OutFile $archive -UseBasicParsing
    if ((Get-Item -LiteralPath $archive).Length -ne $metadata.size -or (Get-Digest $archive) -ne $metadata.sha256) {
        throw 'uv download verification failed'
    }
    Expand-VerifiedArchive $archive $uvRoot
    if (-not (Test-Path -LiteralPath $executable)) { throw 'uv executable is missing' }
    Set-Content -LiteralPath $marker -Value (Get-Digest $executable) -Encoding ASCII
    return $executable
}

function Invoke-Uv([string[]]$Arguments) {
    & $script:uvExecutable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "uv exited with code $LASTEXITCODE" }
}

Push-Location -LiteralPath $projectRoot
try {
    if (-not [Environment]::Is64BitOperatingSystem) { throw 'Windows x64 is required' }
    if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'pyproject.toml'))) {
        throw 'Run this script from the complete repository'
    }
    New-Item -ItemType Directory -Path $dataRoot -Force | Out-Null
    Start-Transcript -LiteralPath (Join-Path $dataRoot 'startup.log') -Append | Out-Null
    $transcribing = $true
    $uvExecutable = Get-LocalUv
    $env:UV_PYTHON_INSTALL_DIR = Join-Path $runtimeRoot 'python'
    $env:UV_CACHE_DIR = Join-Path $runtimeRoot 'uv-cache'
    $env:UV_PYTHON_PREFERENCE = 'only-managed'
    $env:UV_PYTHON_DOWNLOADS = 'automatic'
    $env:UV_NO_PROGRESS = '1'
    $env:PYTHONUTF8 = '1'
    Write-Host '正在准备 Python 3.12 和项目依赖…'
    Invoke-Uv @('sync', '--locked', '--no-dev', '--extra', 'wechat', '--python', '3.12')
    Write-Host '正在检查 Chromium，缺少时自动下载…'
    Invoke-Uv @('run', '--locked', '--no-dev', '--extra', 'wechat', 'python', '-m', 'src.runtime', '--ensure')
    Invoke-Uv @('run', '--locked', '--no-dev', '--extra', 'wechat', 'python', '-c', 'import src.app, zxingcpp, wechatauto.db')
    Write-Host '运行环境准备完成。'
    if (-not $PrepareOnly) {
        $pythonWindow = Join-Path $projectRoot '.venv/Scripts/pythonw.exe'
        Start-Process -FilePath $pythonWindow -ArgumentList '-m', 'src' -WorkingDirectory $projectRoot -WindowStyle Normal
    }
}
catch {
    Write-Host ('启动失败：' + $_.Exception.Message) -ForegroundColor Red
    Write-Host '请检查网络后重试，详细信息位于 data/startup.log。'
    exit 1
}
finally {
    if ($transcribing) { Stop-Transcript | Out-Null }
    Pop-Location
}
