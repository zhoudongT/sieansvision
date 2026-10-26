param([switch]$InstallDependencies, [ValidatePattern('^[A-Za-z][A-Za-z0-9_-]{0,60}$')][string]$BuildName = 'native-desktop')
$ErrorActionPreference = 'Stop'
$nativeRoot = Split-Path -Parent $PSScriptRoot
$nativePython = Join-Path $nativeRoot '.venv/Scripts/python.exe'
if (!(Test-Path -LiteralPath $nativePython)) { throw '请先按 README 创建项目 .venv Python 环境' }
Push-Location -LiteralPath $nativeRoot
try {
    if ($InstallDependencies) {
        & $nativePython -m pip install -r desktop/requirements.txt
        if ($LASTEXITCODE -ne 0) { throw '桌面依赖安装失败' }
    }
    & node scripts/export-native-catalog.cjs
    if ($LASTEXITCODE -ne 0) { throw '原生算子目录同步失败' }
    $nativeDist = [IO.Path]::GetFullPath((Join-Path $nativeRoot "artifacts/$BuildName"))
    $nativeArtifacts = [IO.Path]::GetFullPath((Join-Path $nativeRoot 'artifacts')) + [IO.Path]::DirectorySeparatorChar
    if (!$nativeDist.StartsWith($nativeArtifacts, [StringComparison]::OrdinalIgnoreCase)) { throw '打包输出必须位于项目 artifacts 目录内' }
    & $nativePython -m PyInstaller --noconfirm --distpath $nativeDist --workpath artifacts/native-build/work desktop/SIEANSVision.spec
    if ($LASTEXITCODE -ne 0) { throw '桌面程序打包失败' }
    $nativeOutput = Join-Path $nativeDist 'SIEANSVision'
    [IO.File]::WriteAllText((Join-Path $nativeOutput 'runtime-root.txt'), $nativeRoot, [Text.UTF8Encoding]::new($false))
    Write-Output "桌面开发版：$nativeOutput/SIEANSVision.exe"
    Write-Output '当前构建复用本机项目内的算法运行环境；尚非可拷贝到其他电脑的完整安装包。'
} finally { Pop-Location }
