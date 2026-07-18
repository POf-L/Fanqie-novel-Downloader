# Rewrite all GitHub release notes to Clash-style Chinese download guides.
# Token is read from git credential manager (never printed).

$ErrorActionPreference = 'Stop'
$repo = 'POf-L/Fanqie-novel-Downloader'
$api = "https://api.github.com/repos/$repo"

function Get-GitHubToken {
  $inputText = "protocol=https`nhost=github.com`n`n"
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = 'git'
  $psi.Arguments = 'credential fill'
  $psi.RedirectStandardInput = $true
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $psi.UseShellExecute = $false
  $p = [System.Diagnostics.Process]::Start($psi)
  $p.StandardInput.Write($inputText)
  $p.StandardInput.Close()
  $out = $p.StandardOutput.ReadToEnd()
  $p.WaitForExit(10000) | Out-Null
  foreach ($line in ($out -split "`n")) {
    if ($line -match '^password=(.+)$') {
      return $Matches[1].Trim()
    }
  }
  throw 'GitHub token not found in git credential manager'
}

function Invoke-GH {
  param(
    [string]$Method = 'GET',
    [string]$Url,
    [string]$Token,
    [object]$Body = $null
  )
  $headers = @{
    Authorization = "Bearer $Token"
    Accept = 'application/vnd.github+json'
    'User-Agent' = 'fanqie-release-notes-rewriter'
    'X-GitHub-Api-Version' = '2022-11-28'
  }
  if ($null -eq $Body) {
    return Invoke-RestMethod -Method $Method -Uri $Url -Headers $headers
  }
  $json = $Body | ConvertTo-Json -Depth 8
  return Invoke-RestMethod -Method $Method -Uri $Url -Headers $headers -Body $json -ContentType 'application/json; charset=utf-8'
}

function Pick-Assets {
  param([string[]]$Assets, [string[]]$Needles)
  $out = @()
  foreach ($name in $Assets) {
    $low = $name.ToLowerInvariant()
    $ok = $true
    foreach ($n in $Needles) {
      if ($low -notlike "*$($n.ToLowerInvariant())*") { $ok = $false; break }
    }
    if ($ok) { $out += $name }
  }
  return $out
}

function Make-Link {
  param([string]$Base, [string]$Name, [string]$Label)
  return "[$Label]($Base/$Name)"
}

function Join-Links {
  param([string]$Base, [string[]]$Names, [hashtable]$LabelMap)
  if (-not $Names -or $Names.Count -eq 0) { return '_本版本未提供_' }
  $parts = @()
  foreach ($name in $Names) {
    $label = $name
    $low = $name.ToLowerInvariant()
    foreach ($key in $LabelMap.Keys) {
      if ($low -like "*$key*") { $label = $LabelMap[$key]; break }
    }
    $parts += (Make-Link -Base $Base -Name $name -Label $label)
  }
  return ($parts -join ' | ')
}

function Build-Notes {
  param(
    [string]$Tag,
    [string]$Version,
    [bool]$Prerelease,
    [string[]]$AssetNames
  )

  $base = "https://github.com/$repo/releases/download/$Tag"
  $assets = @($AssetNames | Where-Object {
    $_ -and
    ($_ -notlike '*.sig') -and
    ($_ -notin @('latest.json','SHA256SUMS-release.txt','SHA256SUMS-android.txt','SHA256SUMS-ios.txt','SIGNING.txt'))
  })

  $winX64 = Pick-Assets $assets @('windows-x64', '.exe')
  $winArm = Pick-Assets $assets @('windows-arm64', '.exe')
  $macArm = @(Pick-Assets $assets @('darwin-aarch64') | Where-Object { $_ -like '*.dmg' })
  if ($macArm.Count -eq 0) { $macArm = @(Pick-Assets $assets @('aarch64') | Where-Object { $_ -like '*.dmg' -and $_ -like '*darwin*' }) }
  $macX64 = @(Pick-Assets $assets @('darwin-x64') | Where-Object { $_ -like '*.dmg' })
  $debX64 = Pick-Assets $assets @('linux-amd64', '.deb')
  if ($debX64.Count -eq 0) { $debX64 = Pick-Assets $assets @('amd64', '.deb') }
  $debArm = Pick-Assets $assets @('linux-arm64', '.deb')
  if ($debArm.Count -eq 0) { $debArm = Pick-Assets $assets @('aarch64', '.deb') }
  $appX64 = Pick-Assets $assets @('linux-amd64', '.appimage')
  if ($appX64.Count -eq 0) { $appX64 = Pick-Assets $assets @('x86_64', '.appimage') }
  $appArm = Pick-Assets $assets @('linux-arm64', '.appimage')
  if ($appArm.Count -eq 0) { $appArm = Pick-Assets $assets @('aarch64', '.appimage') }
  $apkArm64 = @(Pick-Assets $assets @('arm64-v8a') | Where-Object { $_ -like '*.apk' })
  $apkV7 = @(Pick-Assets $assets @('armeabi-v7a') | Where-Object { $_ -like '*.apk' })
  $apkX86 = @(Pick-Assets $assets @('x86_64') | Where-Object { $_ -like '*.apk' })
  $apkUni = @(Pick-Assets $assets @('universal') | Where-Object { $_ -like '*.apk' })
  if ($apkUni.Count -eq 0) {
    # fallback: any apk not already classified
    $apkUni = @($assets | Where-Object {
      $_ -like '*.apk' -and
      $_ -notlike '*arm64-v8a*' -and
      $_ -notlike '*armeabi-v7a*' -and
      $_ -notlike '*x86_64*'
    })
  }
  $aab = @($assets | Where-Object { $_ -like '*.aab' })

  # 判断本版本实际产出了什么
  $shipped = @()
  if ($winX64.Count -gt 0 -or $winArm.Count -gt 0) { $shipped += 'Windows' }
  if ($macArm.Count -gt 0 -or $macX64.Count -gt 0) { $shipped += 'macOS' }
  if ($debX64.Count -gt 0 -or $debArm.Count -gt 0 -or $appX64.Count -gt 0 -or $appArm.Count -gt 0) { $shipped += 'Linux' }
  if ($apkArm64.Count -gt 0 -or $apkV7.Count -gt 0 -or $apkUni.Count -gt 0 -or $aab.Count -gt 0) { $shipped += 'Android' }
  $iosIpa = @($assets | Where-Object { $_ -like '*.ipa' })
  if ($iosIpa.Count -gt 0) { $shipped += 'iOS（无签名 IPA）' }
  $shippedStr = if ($shipped.Count -gt 0) { $shipped -join ' / ' } else { '无' }

  if ($Prerelease) {
    $header = "## $Version"
    $risk = @(
      '',
      '> ⚠️ **本版本是测试预发布（Pre-release）**，可能存在不稳定问题。',
      '> 不会进入稳定版自动更新通道；普通用户建议等正式版发布后再更新。'
    )
  } else {
    $header = "## $Version（正式版）"
    $risk = @()
  }

  $lines = New-Object System.Collections.Generic.List[string]
  $lines.Add($header) | Out-Null
  $lines.Add('') | Out-Null
  $lines.Add('基于 **Rust + Tauri v2** 的番茄小说下载器。') | Out-Null
  $lines.Add('') | Out-Null
  $lines.Add('> 📱 **项目目标平台**：Windows / Linux / macOS / Android / iOS。') | Out-Null
  $lines.Add("> 📦 **本版本实际产出**：$shippedStr。") | Out-Null
  $lines.Add('> iOS 为无签名 IPA，需自行侧载，不上架 App Store。') | Out-Null
  if (-not $Prerelease) {
    $lines.Add('>') | Out-Null
    $lines.Add('> 🔄 已安装旧版的用户，可直接在软件内使用「一键更新」。') | Out-Null
  }
  foreach ($r in $risk) { $lines.Add($r) | Out-Null }
  $lines.Add('') | Out-Null
  $lines.Add('## 下载地址') | Out-Null
  $lines.Add('') | Out-Null

  $lines.Add('### 🪟 Windows') | Out-Null
  $lines.Add('') | Out-Null
  $lines.Add('#### 安装包（推荐）') | Out-Null
  $lines.Add('') | Out-Null
  $winLinks = @()
  if ($winX64.Count -gt 0) { $winLinks += (Make-Link $base $winX64[0] '64位（常用）') }
  if ($winArm.Count -gt 0) { $winLinks += (Make-Link $base $winArm[0] 'ARM64（Surface / 骁龙本）') }
  $lines.Add('- ' + ($(if ($winLinks.Count) { $winLinks -join ' | ' } else { '_本版本未提供_' }))) | Out-Null
  $lines.Add('') | Out-Null

  $lines.Add('### 🍎 macOS') | Out-Null
  $lines.Add('') | Out-Null
  $macLinks = @()
  if ($macArm.Count -gt 0) { $macLinks += (Make-Link $base $macArm[0] 'Apple M 芯片（推荐）') }
  if ($macX64.Count -gt 0) { $macLinks += (Make-Link $base $macX64[0] 'Intel 芯片') }
  $lines.Add('- ' + ($(if ($macLinks.Count) { $macLinks -join ' | ' } else { '_本版本未提供_' }))) | Out-Null
  $lines.Add('') | Out-Null

  $lines.Add('### 🐧 Linux') | Out-Null
  $lines.Add('') | Out-Null
  $lines.Add('#### DEB 包（推荐，体积小）') | Out-Null
  $lines.Add('') | Out-Null
  $debLinks = @()
  if ($debX64.Count -gt 0) { $debLinks += (Make-Link $base $debX64[0] '64位') }
  if ($debArm.Count -gt 0) { $debLinks += (Make-Link $base $debArm[0] 'ARM64') }
  $lines.Add('- ' + ($(if ($debLinks.Count) { $debLinks -join ' | ' } else { '_本版本未提供_' }))) | Out-Null
  $lines.Add('') | Out-Null
  $lines.Add('#### AppImage（免安装，体积较大）') | Out-Null
  $lines.Add('') | Out-Null
  $appLinks = @()
  if ($appX64.Count -gt 0) { $appLinks += (Make-Link $base $appX64[0] '64位') }
  if ($appArm.Count -gt 0) { $appLinks += (Make-Link $base $appArm[0] 'ARM64') }
  $lines.Add('- ' + ($(if ($appLinks.Count) { $appLinks -join ' | ' } else { '_本版本未提供_' }))) | Out-Null
  $lines.Add('') | Out-Null

  $lines.Add('### 🤖 Android') | Out-Null
  $lines.Add('') | Out-Null
  $lines.Add('#### 手机安装包') | Out-Null
  $lines.Add('') | Out-Null
  $apkLines = @()
  if ($apkArm64.Count -gt 0) { $apkLines += '- ' + (Make-Link $base $apkArm64[0] '64位 arm64-v8a（现代手机，推荐）') }
  if ($apkV7.Count -gt 0) { $apkLines += '- ' + (Make-Link $base $apkV7[0] '32位 armeabi-v7a（老旧手机）') }
  if ($apkUni.Count -gt 0) {
    $uniLabel = '通用版 universal（兼容所有设备）'
    if ($apkArm64.Count -eq 0 -and $apkV7.Count -eq 0 -and $apkX86.Count -eq 0) {
      $uniLabel = '通用版 universal（兼容所有设备，约 66MB）'
    }
    $apkLines += '- ' + (Make-Link $base $apkUni[0] $uniLabel)
  }
  if ($apkX86.Count -gt 0) { $apkLines += '- ' + (Make-Link $base $apkX86[0] 'x86_64（模拟器 / 部分平板）') }
  if ($apkLines.Count -eq 0) { $apkLines += '- _本版本未提供_' }
  foreach ($l in $apkLines) { $lines.Add($l) | Out-Null }
  $lines.Add('') | Out-Null
  $lines.Add('#### 应用商店包') | Out-Null
  $lines.Add('') | Out-Null
  if ($aab.Count -gt 0) {
    $lines.Add('- ' + (Make-Link $base $aab[0] 'AAB（上架用）')) | Out-Null
  } else {
    $lines.Add('- _本版本未提供_') | Out-Null
  }
  $lines.Add('') | Out-Null

  $lines.Add('### 📱 iOS') | Out-Null
  $lines.Add('') | Out-Null
  if ($iosIpa.Count -gt 0) {
    $lines.Add("- $(Make-Link $base $iosIpa[0] '无签名 IPA（需自行侧载）')") | Out-Null
    $lines.Add('') | Out-Null
    $lines.Add('> ⚠️ **未上架 App Store**。此 IPA **无 Apple 签名**，需自行用 AltStore / Sideloadly / TrollStore 等工具侧载安装。') | Out-Null
    $lines.Add('> 安装后需信任开发者证书（设置 → 通用 → VPN 与设备管理）。') | Out-Null
  } else {
    $lines.Add('_本版本未提供 IPA。_') | Out-Null
  }
  $lines.Add('') | Out-Null
  $lines.Add('---') | Out-Null
  $lines.Add('') | Out-Null
  $lines.Add('### ❓ 常见问题') | Out-Null
  $lines.Add('') | Out-Null
  $lines.Add('- **Windows 提示无法验证发行商**：安装包右键 → 属性 → 勾选「解除锁定」后再运行。') | Out-Null
  $lines.Add('- **Linux DEB 打不开**：先安装 `libwebkit2gtk-4.1`（Ubuntu/Debian）。') | Out-Null
  $lines.Add('- **Android 安装被拦截**：系统设置中允许「安装未知来源应用」。') | Out-Null
  $lines.Add('- **iOS 如何安装**：下载无签名 IPA，用 AltStore / Sideloadly / TrollStore 等工具侧载；不支持 App Store。') | Out-Null
  $lines.Add('- **这是测试版还是正式版**：标题标注「测试预发布」的是测试版，标注「正式版」的是稳定版。') | Out-Null
  $lines.Add('- **软件内更新失败**：可手动下载本页对应平台安装包覆盖安装。') | Out-Null
  $lines.Add('') | Out-Null
  $lines.Add('### 💎 支持与推广') | Out-Null
  $lines.Add('') | Out-Null
  $lines.Add('如果这个项目对你有帮助，也欢迎支持一下合作服务：') | Out-Null
  $lines.Add('') | Out-Null
  $lines.Add('> 走邀请码注册即送 **1 美元**，不走邀请链接是没有的。麻烦各位体验一下了。') | Out-Null
  $lines.Add('') | Out-Null
  $lines.Add('- [注册链接（含邀请码）](https://999554.xyz/register?aff=Xf2p)') | Out-Null
  $lines.Add('') | Out-Null
  $lines.Add('也诚招赞助与推广合作，可通过 [Issues](https://github.com/POf-L/Fanqie-novel-Downloader/issues) 留言联系。') | Out-Null
  $lines.Add('') | Out-Null
  $lines.Add('### 🔗 相关链接') | Out-Null
  $lines.Add('') | Out-Null
  $lines.Add('- [问题反馈](https://github.com/POf-L/Fanqie-novel-Downloader/issues)') | Out-Null
  $lines.Add('- [项目说明](https://github.com/POf-L/Fanqie-novel-Downloader)') | Out-Null
  $lines.Add('') | Out-Null
  $lines.Add('<details>') | Out-Null
  $lines.Add('<summary>📦 构建信息</summary>') | Out-Null
  $lines.Add('') | Out-Null
  $relType = if ($Prerelease) { '测试预发布（Pre-release）' } else { '正式稳定版' }
  $lines.Add("- 版本：``$Version``") | Out-Null
  $lines.Add("- Tag：``$Tag``") | Out-Null
  $lines.Add("- 类型：$relType") | Out-Null
  $lines.Add("- 本版本实际产出：$shippedStr") | Out-Null
  $lines.Add("- 可下载安装包数量：$($assets.Count)（不含 .sig 签名和校验文件）") | Out-Null
  $lines.Add('') | Out-Null
  $lines.Add('</details>') | Out-Null
  $lines.Add('') | Out-Null

  return ($lines -join "`n")
}

$token = Get-GitHubToken
Write-Host "Token acquired (not printed)."

# List all releases (paginated)
$all = @()
$page = 1
while ($true) {
  $batch = Invoke-GH -Url "$api/releases?per_page=100&page=$page" -Token $token
  if (-not $batch -or $batch.Count -eq 0) { break }
  $all += $batch
  if ($batch.Count -lt 100) { break }
  $page++
}

Write-Host "Found $($all.Count) releases."

$updated = 0
$skipped = 0
$failed = 0

foreach ($rel in $all) {
  $tag = [string]$rel.tag_name
  if ([string]::IsNullOrWhiteSpace($tag)) {
    # draft untagged
    $tag = [string]$rel.name
  }
  $id = $rel.id
  $name = if ($rel.name) { [string]$rel.name } else { $tag }
  $version = $name -replace '^番茄小说下载器\s*', '' -replace '^Fanqie.*?\s+', ''
  if ([string]::IsNullOrWhiteSpace($version)) { $version = $tag.TrimStart('v') }

  $assetNames = @($rel.assets | ForEach-Object { $_.name })
  if ($assetNames.Count -eq 0) {
    Write-Host "SKIP (no assets): $tag"
    $skipped++
    continue
  }

  try {
    $body = Build-Notes -Tag $tag -Version $version -Prerelease ([bool]$rel.prerelease) -AssetNames $assetNames
    $payload = @{
      name = if ($name -match '番茄') { $name } else { "番茄小说下载器 $version" }
      body = $body
    }
    Invoke-GH -Method PATCH -Url "$api/releases/$id" -Token $token -Body $payload | Out-Null
    Write-Host "OK: $tag ($($assetNames.Count) assets)"
    $updated++
    Start-Sleep -Milliseconds 250
  } catch {
    Write-Host "FAIL: $tag -> $($_.Exception.Message)"
    $failed++
  }
}

Write-Host "Done. updated=$updated skipped=$skipped failed=$failed"
