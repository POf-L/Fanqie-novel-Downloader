#!/usr/bin/env bash
# 在 x64 Ubuntu runner 上准备 aarch64-unknown-linux-gnu 的 Tauri 交叉编译环境。
#
# 以前 fallback 只装了 x64 的 WebKitGTK 开发包并设 PKG_CONFIG_ALLOW_CROSS=1，
# pkg-config 返回的是 x64 的 glib/gtk/webkit 库，链接 arm64 目标时找不到库。
# 这里改为 Debian/Ubuntu multiarch：加 arm64 架构、从 ports.ubuntu.com 装 arm64
# 版开发包，并只对 aarch64 目标把 pkg-config 指到 arm64 的 .pc 目录（宿主机上
# 运行的 build script 不受影响）。
#
# 只输出环境变量到 GITHUB_ENV（没有时打印到 stdout），不编译任何源码。
set -euo pipefail

target_triple="aarch64-unknown-linux-gnu"
multiarch="aarch64-linux-gnu"
# shellcheck disable=SC1091
codename="$(. /etc/os-release && echo "${VERSION_CODENAME}")"
if [[ -z "${codename}" ]]; then
  echo "::error::无法识别 Ubuntu 版本代号"
  exit 1
fi
ports="http://ports.ubuntu.com/ubuntu-ports"

sudo dpkg --add-architecture arm64

# 现有的源（archive/azure 镜像、mirror+file:、security、第三方仓库）大多没有 arm64，
# 全部限定为 amd64，否则 apt-get update 会因为 404 失败；arm64 只从下面的 ports 源装。
# 兼容旧式 sources.list / *.list 和 deb822 *.sources。
restrict_list() {
  # 没有 [...] 选项的行插入 [arch=amd64]；有选项但没写 arch= 的行补上 arch=amd64。
  sudo sed -i -E \
    -e '/^deb(-src)?[[:space:]]+\[/{/arch=/!s/^(deb(-src)?[[:space:]]+)\[/\1[arch=amd64 /}' \
    -e 's/^(deb(-src)?)[[:space:]]+([^[[:space:]])/\1 [arch=amd64] \3/' \
    "$1"
}
shopt -s nullglob
for list in /etc/apt/sources.list /etc/apt/sources.list.d/*.list; do
  [[ -f "${list}" ]] && restrict_list "${list}"
done
for sources in /etc/apt/sources.list.d/*.sources; do
  if ! grep -q '^Architectures:' "${sources}"; then
    sudo sed -i -E 's/^(URIs:.*)$/\1\nArchitectures: amd64/' "${sources}"
  fi
done
shopt -u nullglob

{
  for suite in "${codename}" "${codename}-updates" "${codename}-security"; do
    echo "deb [arch=arm64] ${ports} ${suite} main restricted universe multiverse"
  done
} | sudo tee /etc/apt/sources.list.d/arm64-ports.list >/dev/null

sudo apt-get update -o Acquire::Retries=3
sudo apt-get install -y --no-install-recommends -o Acquire::Retries=3 \
  gcc-aarch64-linux-gnu \
  g++-aarch64-linux-gnu \
  libc6-dev-arm64-cross \
  pkg-config \
  patchelf \
  xdg-utils \
  libwebkit2gtk-4.1-dev:arm64 \
  libgtk-3-dev:arm64 \
  libsoup-3.0-dev:arm64 \
  libjavascriptcoregtk-4.1-dev:arm64 \
  libdbus-1-dev:arm64 \
  libssl-dev:arm64

pc_dirs="/usr/lib/${multiarch}/pkgconfig:/usr/share/pkgconfig"
for pc in glib-2.0 gtk+-3.0 webkit2gtk-4.1 libsoup-3.0 javascriptcoregtk-4.1 dbus-1; do
  if ! PKG_CONFIG_LIBDIR="${pc_dirs}" pkg-config --exists "${pc}"; then
    echo "::error::arm64 交叉编译环境缺少 ${pc}.pc"
    exit 1
  fi
done

env_out="${GITHUB_ENV:-/dev/stdout}"
underscored="${target_triple//-/_}"
upper="$(echo "${underscored}" | tr '[:lower:]' '[:upper:]')"
{
  echo "CARGO_TARGET_${upper}_LINKER=${multiarch}-gcc"
  echo "CC_${underscored}=${multiarch}-gcc"
  echo "CXX_${underscored}=${multiarch}-g++"
  echo "AR_${underscored}=${multiarch}-ar"
  # pkg-config-rs / system-deps 支持按目标设置的变量：只影响 aarch64 目标。
  echo "PKG_CONFIG_ALLOW_CROSS=1"
  echo "PKG_CONFIG_LIBDIR_${underscored}=${pc_dirs}"
  echo "PKG_CONFIG_SYSROOT_DIR_${underscored}=/"
} >> "${env_out}"
echo "arm64 交叉编译环境已就绪（${codename}）。"
