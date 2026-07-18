# Update all draft releases to Chinese notes with hyperlinks pointing to latest published release.
$ErrorActionPreference = 'Stop'
$repo = 'POf-L/Fanqie-novel-Downloader'
$api = "https://api.github.com/repos/$repo"

function Get-GitHubToken {
  $inputText = "protocol=https`nhost=github.com`n`n"
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = 'git'; $psi.Arguments = 'credential fill'
  $psi.RedirectStandardInput = $true; $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true; $psi.UseShellExecute = $false
  $p = [Diagnostics.Process]::Start($psi)
  $p.StandardInput.Write($inputText); $p.StandardInput.Close()
  $out = $p.StandardOutput.ReadToEnd(); $p.WaitForExit(10000) | Out-Null
  foreach ($line in ($out -split "`n")) {
    if ($line -match '^password=(.+)$') { return $Matches[1].Trim() }
  }
  throw 'token missing'
}

function GH($Method, $Url, $Token, $Body = $null) {
  $h = @{
    Authorization = "Bearer $Token"
    Accept = 'application/vnd.github+json'
    'User-Agent' = 'fanqie-draft'
    'X-GitHub-Api-Version' = '2022-11-28'
  }
  if ($null -eq $Body) {
    return Invoke-RestMethod -Method $Method -Uri $Url -Headers $h
  }
  $json = $Body | ConvertTo-Json -Depth 6
  return Invoke-RestMethod -Method $Method -Uri $Url -Headers $h -Body ([System.Text.Encoding]::UTF8.GetBytes($json)) -ContentType 'application/json; charset=utf-8'
}

function Link($Base, $Name, $Label) { "[$Label]($Base/$Name)" }

$token = Get-GitHubToken
$rels = @()
$page = 1
while ($true) {
  $batch = GH GET "$api/releases?per_page=100&page=$page" $token
  if (-not $batch -or $batch.Count -eq 0) { break }
  $rels += $batch
  if ($batch.Count -lt 100) { break }
  $page++
}

$latest = $rels | Where-Object { -not $_.draft -and $_.assets -and $_.assets.Count -gt 0 } | Select-Object -First 1
if (-not $latest) { throw 'No published release with assets found' }

$ltag = $latest.tag_name
$lname = if ($latest.name) { $latest.name } else { $ltag }
$base = "https://github.com/$repo/releases/download/$ltag"
$assets = @($latest.assets | ForEach-Object { $_.name } | Where-Object {
  $_ -and $_ -notlike '*.sig' -and $_ -notin @('latest.json','SHA256SUMS-release.txt','SHA256SUMS-android.txt','SHA256SUMS-ios.txt','SIGNING.txt')
})

function Pick([string[]]$Needles) {
  $assets | Where-Object {
    $low = $_.ToLowerInvariant()
    ($Needles | ForEach-Object { $low -like "*$($_.ToLowerInvariant())*" }) -notcontains $false
  }
}

$winX64 = @(Pick @('windows-x64','.exe'))
$winArm = @(Pick @('windows-arm64','.exe'))
$macArm = @(Pick @('darwin-aarch64') | Where-Object { $_ -like '*.dmg' })
$macX64 = @(Pick @('darwin-x64') | Where-Object { $_ -like '*.dmg' })
$debX64 = @(Pick @('linux-amd64','.deb'))
$debArm = @(Pick @('linux-arm64','.deb'))
$appX64 = @($assets | Where-Object { $_.ToLowerInvariant() -like '*linux-amd64*' -and $_.ToLowerInvariant() -like '*.appimage' })
$appArm = @($assets | Where-Object { ($_.ToLowerInvariant() -like '*linux-arm64*' -or $_.ToLowerInvariant() -like '*linux-aarch64*') -and $_.ToLowerInvariant() -like '*.appimage' })
$apkArm = @($assets | Where-Object { $_.ToLowerInvariant() -like '*arm64-v8a*' -and $_ -like '*.apk' })
$apkUni = @($assets | Where-Object { $_.ToLowerInvariant() -like '*universal*' -and $_ -like '*.apk' })
if (-not $apkUni) { $apkUni = @($assets | Where-Object { $_ -like '*.apk' }) }
$aab = @($assets | Where-Object { $_ -like '*.aab' })

$drafts = $rels | Where-Object { $_.draft }
Write-Host "Latest published: $ltag ($($assets.Count) assets)"
Write-Host "Drafts: $($drafts.Count)"

foreach ($d in $drafts) {
  $version = if ($d.name) { $d.name -replace '^番茄小说下载器\s*','' } else { $d.tag_name }
  $tag = if ($d.tag_name) { $d.tag_name } else { $version }
  $lines = @(
    "## $version",
    '',
    '基于 **Rust + Tauri v2** 的番茄小说下载器。',
    '',
    '> ⏳ **本版本仍是 Draft / 构建中或无附件。**',
    '>',
    '> 📱 **当前支持**：Windows / Linux / macOS / Android。',
    '> **iOS 暂不支持**，本仓库不提供 IPA。',
    '>',
    "> 🔗 下方下载链接**默认指向最新已发布版本** [`$lname`](https://github.com/$repo/releases/tag/$ltag)。",
    '> 本版本资源就绪后，请重新发布或运行 finalize 以替换为本版本链接。',
    '',
    '## 下载地址（默认：最新已发布版本）',
    '',
    '### 🪟 Windows',
    '',
    '#### 安装包（推荐）',
    ''
  )
  $wp = @()
  if ($winX64) { $wp += (Link $base $winX64[0] '64位（常用）') }
  if ($winArm) { $wp += (Link $base $winArm[0] 'ARM64（Surface / 骁龙本）') }
  $lines += '- ' + ($(if ($wp) { $wp -join ' | ' } else { '_暂无_' }))
  $lines += '', '### 🍎 macOS', ''
  $mp = @()
  if ($macArm) { $mp += (Link $base $macArm[0] 'Apple M 芯片（推荐）') }
  if ($macX64) { $mp += (Link $base $macX64[0] 'Intel 芯片') }
  $lines += '- ' + ($(if ($mp) { $mp -join ' | ' } else { '_暂无_' }))
  $lines += '', '### 🐧 Linux', '', '#### DEB 包（推荐）', ''
  $dp = @()
  if ($debX64) { $dp += (Link $base $debX64[0] '64位') }
  if ($debArm) { $dp += (Link $base $debArm[0] 'ARM64') }
  $lines += '- ' + ($(if ($dp) { $dp -join ' | ' } else { '_暂无_' }))
  $lines += '', '#### AppImage', ''
  $ap = @()
  if ($appX64) { $ap += (Link $base $appX64[0] '64位') }
  if ($appArm) { $ap += (Link $base $appArm[0] 'ARM64') }
  $lines += '- ' + ($(if ($ap) { $ap -join ' | ' } else { '_暂无_' }))
  $lines += '', '### 🤖 Android', '', '#### 手机安装包', ''
  if ($apkArm) { $lines += '- ' + (Link $base $apkArm[0] '64位 arm64-v8a（推荐）') }
  if ($apkUni) { $lines += '- ' + (Link $base $apkUni[0] '通用版 universal') }
  if (-not $apkArm -and -not $apkUni) { $lines += '- _暂无_' }
  $lines += '', '#### 应用商店包', ''
  if ($aab) { $lines += '- ' + (Link $base $aab[0] 'AAB（上架用）') } else { $lines += '- _暂无_' }
  $lines += '', '### 📱 iOS', '', '**当前不支持。** 本项目暂时不提供 iOS / IPA 下载。', '', '---', ''
  $lines += '### 💎 支持与推广', '', '如果这个项目对你有帮助，也欢迎支持一下合作服务：', ''
  $lines += '> 走邀请码注册即送 **1 美元**，不走邀请链接是没有的。麻烦各位体验一下了。', ''
  $lines += '- [注册链接（含邀请码）](https://999554.xyz/register?aff=Xf2p)', ''
  $lines += '### 🔗 相关链接', ''
  $lines += "- [最新发布 $lname](https://github.com/$repo/releases/tag/$ltag)"
  $lines += "- [全部 Releases](https://github.com/$repo/releases)"
  $lines += "- [问题反馈](https://github.com/$repo/issues)"
  $lines += ''
  $body = $lines -join "`n"

  $payload = @{
    name = if ($d.name -and $d.name -match '番茄') { $d.name } else { "番茄小说下载器 $version" }
    body = $body
  }
  GH PATCH "$api/releases/$($d.id)" $token $payload | Out-Null
  Write-Host "Updated draft: $($d.tag_name) / $($d.name)"
}

Write-Host 'Draft update done.'
