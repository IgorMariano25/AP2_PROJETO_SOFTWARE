<#
.SYNOPSIS
  Instala/migra as ferramentas externas pesadas do estudo para a pasta
  developer-tools/ dentro do projeto.

.DESCRIPTION
  Regra do projeto (prompt §5-A): binários pesados NÃO ficam versionados no Git
  nem no venv — vão para a pasta developer-tools/ do projeto (gitignored), um por
  subpasta. Dependências Python continuam no venv/requirements.txt; runtimes do
  SO (Java, Git, Docker) permanecem instalados pelo sistema.

  Este script é idempotente: pula o que já existe. Ferramentas instaladas:
    - ck            CK (Maurício Aniche) — migra tools/ck.jar ou baixa do Maven
    - gitleaks      detecção de segredos (release do GitHub)
    - sonar-scanner SonarScanner CLI (binaries.sonarsource.com)
    - codeql        CodeQL CLI + query packs (bundle do github/codeql-action)

  Os coletores Python resolvem cada ferramenta via common.find_external_tool
  (env → PATH → <projeto>\developer-tools\<sub>), então nenhuma alteração de PATH
  global é necessária. Use -DevTools para outro destino (ou $env:DEVELOPER_TOOLS).

.EXAMPLE
  pwsh -File scripts/setup_dev_tools.ps1
  pwsh -File scripts/setup_dev_tools.ps1 -DevTools D:\tools -SkipCodeQL
#>
[CmdletBinding()]
param(
    [string]$DevTools = $(if ($env:DEVELOPER_TOOLS) { $env:DEVELOPER_TOOLS } else { Join-Path (Split-Path -Parent $PSScriptRoot) 'developer-tools' }),
    [switch]$SkipCodeQL,
    [switch]$PullSonarQubeImage
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'   # acelera Invoke-WebRequest

# Versões fixadas (reprodutibilidade — registrar em TOOLS_VERSIONS.md).
$CK_URL = 'https://repo1.maven.org/maven2/com/github/mauricioaniche/ck/0.7.0/ck-0.7.0-jar-with-dependencies.jar'
$SONAR_SCANNER_VERSION = '6.2.1.4610'
$SONAR_SCANNER_URL = "https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/sonar-scanner-cli-$SONAR_SCANNER_VERSION-windows-x64.zip"

$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$Summary = [System.Collections.Generic.List[string]]::new()

function Write-Step($m) { Write-Host "`n=== $m ===" -ForegroundColor Cyan }
function Add-Summary($name, $status, $path) { $Summary.Add(("{0,-14} {1,-10} {2}" -f $name, $status, $path)) }

function Get-WithRetry($Url, $OutFile, $Tries = 3) {
    for ($i = 1; $i -le $Tries; $i++) {
        try { Invoke-WebRequest -Uri $Url -OutFile $OutFile -UseBasicParsing -TimeoutSec 600; return }
        catch { if ($i -eq $Tries) { throw }; Write-Host "  retry $i/$Tries ..."; Start-Sleep 3 }
    }
}

New-Item -ItemType Directory -Force -Path $DevTools | Out-Null
Write-Host "Destino das ferramentas: $DevTools" -ForegroundColor Green

# --------------------------------------------------------------------------- #
# 1. CK — migra do projeto (tools/ck.jar) ou baixa do Maven Central
# --------------------------------------------------------------------------- #
Write-Step 'CK (Mauricio Aniche)'
$ckDir = Join-Path $DevTools 'ck'
$ckJar = Join-Path $ckDir 'ck.jar'
$legacyJar = Join-Path $ProjectRoot 'tools\ck.jar'
New-Item -ItemType Directory -Force -Path $ckDir | Out-Null
if (Test-Path $ckJar) {
    Add-Summary 'ck' 'ja existe' $ckJar
} elseif (Test-Path $legacyJar) {
    Move-Item $legacyJar $ckJar -Force
    Write-Host "Migrado de $legacyJar"
    Add-Summary 'ck' 'migrado' $ckJar
} else {
    Get-WithRetry $CK_URL $ckJar
    Add-Summary 'ck' 'baixado' $ckJar
}

# --------------------------------------------------------------------------- #
# 2. Gitleaks — release mais recente do GitHub (windows x64)
# --------------------------------------------------------------------------- #
Write-Step 'Gitleaks'
$glDir = Join-Path $DevTools 'gitleaks'
$glExe = Join-Path $glDir 'gitleaks.exe'
if (Test-Path $glExe) {
    Add-Summary 'gitleaks' 'ja existe' $glExe
} else {
    New-Item -ItemType Directory -Force -Path $glDir | Out-Null
    try {
        $rel = Invoke-RestMethod 'https://api.github.com/repos/gitleaks/gitleaks/releases/latest' -UseBasicParsing
        $ver = $rel.tag_name.TrimStart('v')
        $asset = $rel.assets | Where-Object { $_.name -eq "gitleaks_${ver}_windows_x64.zip" } | Select-Object -First 1
        if (-not $asset) { throw "asset windows_x64 nao encontrado em $($rel.tag_name)" }
        $zip = Join-Path $env:TEMP "gitleaks_$ver.zip"
        Get-WithRetry $asset.browser_download_url $zip
        Expand-Archive $zip $glDir -Force
        Remove-Item $zip -Force
        Add-Summary 'gitleaks' "v$ver" $glExe
    } catch { Add-Summary 'gitleaks' 'FALHOU' $_.Exception.Message }
}

# --------------------------------------------------------------------------- #
# 3. SonarScanner CLI — layout final: <DevTools>\sonar-scanner\bin\sonar-scanner.bat
# --------------------------------------------------------------------------- #
Write-Step "SonarScanner CLI ($SONAR_SCANNER_VERSION)"
$ssDir = Join-Path $DevTools 'sonar-scanner'
$ssBat = Join-Path $ssDir 'bin\sonar-scanner.bat'
if (Test-Path $ssBat) {
    Add-Summary 'sonar-scanner' 'ja existe' $ssBat
} else {
    try {
        $zip = Join-Path $env:TEMP 'sonar-scanner.zip'
        Get-WithRetry $SONAR_SCANNER_URL $zip
        $tmp = Join-Path $env:TEMP 'sonar-scanner-extract'
        if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
        Expand-Archive $zip $tmp -Force
        $inner = Get-ChildItem $tmp -Directory | Select-Object -First 1
        if (Test-Path $ssDir) { Remove-Item $ssDir -Recurse -Force }
        Move-Item $inner.FullName $ssDir -Force
        Remove-Item $zip, $tmp -Recurse -Force -ErrorAction SilentlyContinue
        Add-Summary 'sonar-scanner' "v$SONAR_SCANNER_VERSION" $ssBat
    } catch { Add-Summary 'sonar-scanner' 'FALHOU' $_.Exception.Message }
}

# --------------------------------------------------------------------------- #
# 4. CodeQL CLI + packs — bundle do github/codeql-action (inclui as queries)
# --------------------------------------------------------------------------- #
Write-Step 'CodeQL (bundle: CLI + query packs)'
$cqDir = Join-Path $DevTools 'codeql'
$cqExe = Join-Path $cqDir 'codeql.exe'
if ($SkipCodeQL) {
    Add-Summary 'codeql' 'pulado' '(-SkipCodeQL)'
} elseif (Test-Path $cqExe) {
    Add-Summary 'codeql' 'ja existe' $cqExe
} else {
    try {
        $rel = Invoke-RestMethod 'https://api.github.com/repos/github/codeql-action/releases/latest' -UseBasicParsing
        $asset = $rel.assets | Where-Object { $_.name -eq 'codeql-bundle-win64.tar.gz' } | Select-Object -First 1
        if (-not $asset) { throw 'codeql-bundle-win64.tar.gz nao encontrado' }
        $tgz = Join-Path $env:TEMP 'codeql-bundle.tar.gz'
        Write-Host "Baixando bundle (~1 GB) ..."
        Get-WithRetry $asset.browser_download_url $tgz
        # O bundle extrai uma pasta "codeql" — extrai direto em $DevTools.
        if (Test-Path $cqDir) { Remove-Item $cqDir -Recurse -Force }
        tar -xzf $tgz -C $DevTools
        Remove-Item $tgz -Force
        Add-Summary 'codeql' "$($rel.tag_name)" $cqExe
    } catch { Add-Summary 'codeql' 'FALHOU' $_.Exception.Message }
}

# --------------------------------------------------------------------------- #
# 5. (Opcional) imagem Docker do servidor SonarQube
# --------------------------------------------------------------------------- #
if ($PullSonarQubeImage) {
    Write-Step 'SonarQube server (imagem Docker)'
    try { docker pull sonarqube:community; Add-Summary 'sonarqube-img' 'pull ok' 'sonarqube:community' }
    catch { Add-Summary 'sonarqube-img' 'FALHOU' $_.Exception.Message }
} else {
    Add-Summary 'sonarqube-img' 'pulado' 'use -PullSonarQubeImage; ou docker run -d -p 9000:9000 sonarqube:community'
}

# --------------------------------------------------------------------------- #
# Resumo + checagem de versões
# --------------------------------------------------------------------------- #
Write-Step 'Resumo'
$Summary | ForEach-Object { Write-Host $_ }

Write-Step 'Versoes detectadas'
$checks = @{
    'gitleaks'      = (Join-Path $glDir 'gitleaks.exe'),     'version'
    'sonar-scanner' = (Join-Path $ssDir 'bin\sonar-scanner.bat'), '--version'
    'codeql'        = (Join-Path $cqDir 'codeql.exe'),        'version'
}
foreach ($name in $checks.Keys) {
    $exe, $arg = $checks[$name]
    if (Test-Path $exe) {
        try { $out = & $exe $arg 2>&1 | Select-Object -First 1; Write-Host ("{0,-14}: {1}" -f $name, $out) }
        catch { Write-Host ("{0,-14}: erro ao executar" -f $name) }
    } else { Write-Host ("{0,-14}: ausente" -f $name) }
}

Write-Host "`nConcluido. Os coletores acham as ferramentas automaticamente em $DevTools." -ForegroundColor Green
Write-Host "Preencha as versoes reais em TOOLS_VERSIONS.md." -ForegroundColor Yellow
