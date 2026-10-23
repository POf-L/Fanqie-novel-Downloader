#!/usr/bin/env bash
# 安装移动端构建用的 cargo-tauri（`cargo tauri` 子命令）。
#
# Android 的 Gradle rustBuild* 任务和 iOS 的 Xcode "Build Rust Code" 阶段调用的是
# `cargo tauri ...`，必须有 ~/.cargo/bin/cargo-tauri；npm 的 @tauri-apps/cli 不提供
# 它（见 1f67a75）。以前用 `cargo install` 从源码编译，Android 约 4–5 分钟、
# iOS 约 6–8 分钟。这里改用 tauri 官方 Release 里同版本的预编译
# cargo-tauri（与 cargo-binstall 用的是同一批文件），并用下面固定的 sha256
# 校验。版本没登记校验值、下载失败、校验不符或版本号不对时，退回原来的
# `cargo install`，结果和以前完全一样。
#
# 升级 TAURI_CLI_VERSION 时，在 checksum_for() 里补上新版本的校验值
# （gh api repos/tauri-apps/tauri/releases/tags/tauri-cli-v<版本> 的 assets[].digest）；
# 不补也能构建，只是会走慢的 cargo install。
set -euo pipefail

version="${TAURI_CLI_VERSION:?TAURI_CLI_VERSION is required}"
cargo_bin="${CARGO_HOME:-${HOME}/.cargo}/bin"

asset_for() {
  case "$1" in
    Linux-x86_64) echo "cargo-tauri-x86_64-unknown-linux-gnu.tgz" ;;
    Darwin-arm64) echo "cargo-tauri-aarch64-apple-darwin.zip" ;;
    Darwin-x86_64) echo "cargo-tauri-x86_64-apple-darwin.zip" ;;
    *) echo "" ;;
  esac
}

checksum_for() {
  case "$1/$2" in
    2.11.4/cargo-tauri-x86_64-unknown-linux-gnu.tgz)
      echo "6864602a34292aa6f2ad40ae019eebe5c1064d6c623fe20696a8a8974067e60b" ;;
    2.11.4/cargo-tauri-aarch64-apple-darwin.zip)
      echo "82bdcb9ae7f407882321680ae50750f11623fae22445f8b00b096e10f815d604" ;;
    2.11.4/cargo-tauri-x86_64-apple-darwin.zip)
      echo "f10dfcc103ccb79248ca27cb9aff7b8a65499d1b0df79fe0465e8aa0a8e7cbef" ;;
    *) echo "" ;;
  esac
}

install_prebuilt() {
  local asset sha256 tmp url
  asset="$(asset_for "$(uname -s)-$(uname -m)")"
  if [[ -z "${asset}" ]]; then
    echo "No prebuilt cargo-tauri for $(uname -s)-$(uname -m)"
    return 1
  fi
  sha256="$(checksum_for "${version}" "${asset}")"
  if [[ -z "${sha256}" ]]; then
    echo "No pinned checksum for tauri-cli ${version} (${asset})"
    return 1
  fi
  tmp="$(mktemp -d)"
  url="https://github.com/tauri-apps/tauri/releases/download/tauri-cli-v${version}/${asset}"
  if ! curl -fsSL --retry 3 --retry-delay 5 -o "${tmp}/${asset}" "${url}"; then
    echo "Download failed: ${url}"
    rm -rf "${tmp}"
    return 1
  fi
  if ! echo "${sha256}  ${tmp}/${asset}" | shasum -a 256 -c -; then
    echo "Checksum mismatch for ${asset}; refusing to use it"
    rm -rf "${tmp}"
    return 1
  fi
  case "${asset}" in
    *.tgz) tar -xzf "${tmp}/${asset}" -C "${tmp}" cargo-tauri ;;
    *.zip) unzip -q -o "${tmp}/${asset}" cargo-tauri -d "${tmp}" ;;
  esac
  mkdir -p "${cargo_bin}"
  install -m 0755 "${tmp}/cargo-tauri" "${cargo_bin}/cargo-tauri"
  rm -rf "${tmp}"
  if [[ "$(cargo tauri --version 2>/dev/null || true)" != "tauri-cli ${version}" ]]; then
    echo "Prebuilt cargo-tauri does not report tauri-cli ${version}"
    rm -f "${cargo_bin}/cargo-tauri"
    return 1
  fi
}

if install_prebuilt; then
  echo "Installed prebuilt cargo-tauri ${version}"
else
  echo "::warning::Prebuilt cargo-tauri unavailable; falling back to cargo install (slower)"
  rm -f "${cargo_bin}/cargo-tauri"
  cargo install tauri-cli --version "${TAURI_CLI_VERSION}" --locked
fi
cargo tauri --version
