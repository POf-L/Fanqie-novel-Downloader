#!/usr/bin/env bash
# 在 x64 Ubuntu runner 上准备 macOS（x86_64 / aarch64-apple-darwin）的交叉编译环境。
#
# GitHub 的 macOS runner 经常排队拿不到（排 15 分钟后被 GitHub 取消），
# desktop-fallback 这时改在 Linux 上编译 macOS 版：
#   - zig + cargo-zigbuild 负责 C 代码和链接，macOS SDK 提供系统框架；
#   - rcodesign 做 ad-hoc 签名（和原生构建一样是 ADHOC | RUNTIME）；
#   - hfsprogs + mozilla/libdmg-hfsplus 生成 DMG（Firefox 也是这样在 Linux 上做 DMG 的）。
# 所有下载都固定版本并校验 SHA256。只输出环境变量到 GITHUB_ENV（没有时打印到 stdout）。
#
# zig 固定 0.13.0：0.14 会把 -L 路径也拼上 SDKROOT 前缀，链接时找不到 libobjc/libiconv。
set -euo pipefail

ZIG_VERSION="0.13.0"
ZIG_SHA256="d45312e61ebcc48032b77bc4cf7fd6915c11fa16e4aad116b66c9468211230ea"
CARGO_ZIGBUILD_VERSION="0.24.1"
CARGO_ZIGBUILD_SHA256="32581c8e13f27a807bb244aaaac870522f5b51263c766cf77b1a99771ce9fa5c"
RCODESIGN_VERSION="0.29.0"
RCODESIGN_SHA256="dbe85cedd8ee4217b64e9a0e4c2aef92ab8bcaaa41f20bde99781ff02e600002"
MACOS_SDK_VERSION="15.5"
MACOS_SDK_SHA256="c15cf0f3f17d714d1aa5a642da8e118db53d79429eb015771ba816aa7c6c1cbd"
LIBDMG_COMMIT="e18579b391950589b9ed16ee630c54ce4319bb29"

root="${RUNNER_TEMP:-/tmp}/macos-cross"
bin="${root}/bin"
mkdir -p "${root}" "${bin}"

fetch() {
  local url="$1" sha="$2" out="$3"
  curl -fsSL --retry 5 --retry-delay 5 -o "${out}" "${url}"
  echo "${sha}  ${out}" | sha256sum --check --quiet
}

sudo apt-get update -qq >/dev/null
sudo apt-get install -y -qq hfsprogs cmake zlib1g-dev libbz2-dev liblzma-dev libssl-dev >/dev/null

fetch "https://ziglang.org/download/${ZIG_VERSION}/zig-linux-x86_64-${ZIG_VERSION}.tar.xz" \
  "${ZIG_SHA256}" "${root}/zig.tar.xz"
mkdir -p "${root}/zig"
tar xJf "${root}/zig.tar.xz" -C "${root}/zig" --strip-components=1
ln -sf "${root}/zig/zig" "${bin}/zig"

fetch "https://github.com/rust-cross/cargo-zigbuild/releases/download/v${CARGO_ZIGBUILD_VERSION}/cargo-zigbuild-x86_64-unknown-linux-gnu.tar.xz" \
  "${CARGO_ZIGBUILD_SHA256}" "${root}/cargo-zigbuild.tar.xz"
mkdir -p "${root}/cargo-zigbuild"
tar xJf "${root}/cargo-zigbuild.tar.xz" -C "${root}/cargo-zigbuild"
find "${root}/cargo-zigbuild" -type f -name cargo-zigbuild -exec install -m 0755 {} "${bin}/cargo-zigbuild" \;

fetch "https://github.com/indygreg/apple-platform-rs/releases/download/apple-codesign%2F${RCODESIGN_VERSION}/apple-codesign-${RCODESIGN_VERSION}-x86_64-unknown-linux-musl.tar.gz" \
  "${RCODESIGN_SHA256}" "${root}/rcodesign.tar.gz"
mkdir -p "${root}/rcodesign"
tar xzf "${root}/rcodesign.tar.gz" -C "${root}/rcodesign"
find "${root}/rcodesign" -type f -name rcodesign -exec install -m 0755 {} "${bin}/rcodesign" \;

fetch "https://github.com/joseluisq/macosx-sdks/releases/download/${MACOS_SDK_VERSION}/MacOSX${MACOS_SDK_VERSION}.sdk.tar.xz" \
  "${MACOS_SDK_SHA256}" "${root}/sdk.tar.xz"
tar xJf "${root}/sdk.tar.xz" -C "${root}"
sdk="${root}/MacOSX${MACOS_SDK_VERSION}.sdk"
if [[ ! -d "${sdk}/System/Library/Frameworks/WebKit.framework" ]]; then
  echo "::error::macOS SDK 解压后找不到 WebKit.framework"
  exit 1
fi

git init -q "${root}/libdmg-hfsplus"
git -C "${root}/libdmg-hfsplus" fetch -q --depth 1 https://github.com/mozilla/libdmg-hfsplus "${LIBDMG_COMMIT}"
git -C "${root}/libdmg-hfsplus" checkout -q FETCH_HEAD
if ! {
  cmake -S "${root}/libdmg-hfsplus" -B "${root}/libdmg-hfsplus/build" -DCMAKE_BUILD_TYPE=Release &&
  cmake --build "${root}/libdmg-hfsplus/build" --target dmg-bin hfsplus -j "$(nproc)"
} >"${root}/libdmg-build.log" 2>&1; then
  tail -n 40 "${root}/libdmg-build.log"
  echo "::error::libdmg-hfsplus 编译失败"
  exit 1
fi
install -m 0755 "${root}/libdmg-hfsplus/build/dmg/dmg" "${bin}/dmg"
install -m 0755 "${root}/libdmg-hfsplus/build/hfs/hfsplus" "${bin}/hfsplus"

for tool in zig cargo-zigbuild rcodesign dmg hfsplus mkfs.hfsplus; do
  if ! PATH="${bin}:${PATH}" command -v "${tool}" >/dev/null; then
    echo "::error::macOS 交叉编译工具 ${tool} 没装上"
    exit 1
  fi
done

env_out="${GITHUB_ENV:-/dev/stdout}"
{
  echo "SDKROOT=${sdk}"
  echo "MACOS_CROSS_BIN=${bin}"
} >> "${env_out}"
if [[ -n "${GITHUB_PATH:-}" ]]; then
  echo "${bin}" >> "${GITHUB_PATH}"
fi
echo "macOS cross toolchain ready: zig ${ZIG_VERSION}, cargo-zigbuild ${CARGO_ZIGBUILD_VERSION}, rcodesign ${RCODESIGN_VERSION}, SDK ${MACOS_SDK_VERSION}"
