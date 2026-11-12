param(
  [Parameter(Mandatory = $true)]
  [string]$ZipPath
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
$zip = (Resolve-Path -LiteralPath $ZipPath).Path
if (-not (Test-Path -LiteralPath (Join-Path $repo '.git'))) {
    throw 'Execute este script na pasta de clone do repositorio acessCaptchaBridge.'
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw 'Git nao encontrado no PATH.'
}

$temp = Join-Path $env:TEMP ('acessoponte-publish-' + [guid]::NewGuid().ToString('N'))
try {
    Expand-Archive -LiteralPath $zip -DestinationPath $temp -Force
    $source = Join-Path $temp 'AcessoPonte-VLM'
    if (-not (Test-Path -LiteralPath (Join-Path $source 'extension/manifest.json'))) {
        throw 'ZIP invalido: a pasta AcessoPonte-VLM/extension/manifest.json nao foi encontrada.'
    }
    Push-Location $repo
    try {
        if ((git status --porcelain).Count -gt 0) {
            throw 'O repositorio possui alteracoes locais. Faca commit ou salve-as antes de prosseguir.'
        }

        foreach ($folder in @('backend', 'extension', 'demo', 'tests')) {
            Copy-Item -LiteralPath (Join-Path $source $folder) -Destination $repo -Recurse -Force
        }
        Copy-Item -LiteralPath (Join-Path $source 'README.md') -Destination (Join-Path $repo 'README.md') -Force

        py -m unittest discover -s tests -v
        if ($LASTEXITCODE -ne 0) { throw 'Testes Python falharam; publicacao cancelada.' }
        if (Get-Command node -ErrorAction SilentlyContinue) {
            node --check extension/background.js
            if ($LASTEXITCODE -ne 0) { throw 'Sintaxe JavaScript invalida.' }
            node --check extension/popup.js
            if ($LASTEXITCODE -ne 0) { throw 'Sintaxe JavaScript invalida.' }
        }
        git add README.md backend extension demo tests
        git commit -m 'feat: publish full AcessoPonte v0.2.0 sources'
        if ($LASTEXITCODE -ne 0) { throw 'Falha ao criar commit.' }
        git push origin main
        if ($LASTEXITCODE -ne 0) { throw 'Falha no push do codigo.' }

        Set-Content -LiteralPath (Join-Path $repo 'release-ready.txt') -Value 'v0.2.0' -Encoding utf8
        git add release-ready.txt
        git commit -m 'release: trigger GitHub Actions for v0.2.0'
        if ($LASTEXITCODE -ne 0) { throw 'Falha ao registrar gatilho.' }
        git push origin main
        if ($LASTEXITCODE -ne 0) { throw 'Falha no push do gatilho.' }

        Write-Host 'Codigo enviado. Verifique Actions e Releases no GitHub.' -ForegroundColor Green
    } finally { Pop-Location }
} finally {
    Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
}
