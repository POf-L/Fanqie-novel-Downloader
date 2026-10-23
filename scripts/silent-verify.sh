#!/usr/bin/env bash
# 公开 runner 上的静默 verify：在私有源码目录里跑 fmt / clippy / test / node 等检查，
# 每一项的全部输出都只写到 runner 本地的临时文件，不进公开日志、不作为 artifact
# 上传，脚本结束时删掉。日志里只有每项的名称、通过/失败、退出码和用时。
#
# 检查清单必须和私有仓库的 scripts/verify-local.sh 完全一致（名称、命令、顺序），
# 失败时在本地运行 `scripts/verify-local.sh <名称>` 就能看到完整输出。
#
# 用法：silent-verify.sh <私有源码目录>
set -uo pipefail

source_dir="${1:?usage: silent-verify.sh <private-source-dir>}"
cd "${source_dir}" || { echo "::error::找不到私有源码目录"; exit 2; }

log_dir="$(mktemp -d "${RUNNER_TEMP:-/tmp}/silent-verify.XXXXXX")"
trap 'rm -rf "${log_dir}"' EXIT

# 不要颜色、不要进度条；输出反正只写文件。
export CARGO_TERM_COLOR=never
export CARGO_TERM_PROGRESS_WHEN=never
export NO_COLOR=1

checks=(
  "fmt|cargo fmt --manifest-path src-tauri/Cargo.toml -- --check"
  "clippy-desktop|cargo clippy --manifest-path src-tauri/Cargo.toml --all-targets --all-features -- -D warnings"
  "clippy-cli|cargo clippy --manifest-path src-tauri/Cargo.toml --bin fanqie --no-default-features --features cli -- -D warnings"
  "test-desktop|cargo test --manifest-path src-tauri/Cargo.toml --all-features"
  "test-cli|cargo test --manifest-path src-tauri/Cargo.toml --bin fanqie --no-default-features --features cli"
  "node-test|node --test tests/*.js"
  "node-check|node --check web/static/app.js"
  "diff-check|git diff --check"
)

failed=()
total_start=${SECONDS}
for entry in "${checks[@]}"; do
  name="${entry%%|*}"
  command="${entry#*|}"
  start=${SECONDS}
  # 命令来自上面写死的清单；stdin 关掉，stdout/stderr 只进本地文件。
  bash -c "${command}" </dev/null >"${log_dir}/${name}.log" 2>&1
  code=$?
  elapsed=$((SECONDS - start))
  if [[ ${code} -eq 0 ]]; then
    printf '通过  %-15s 退出码 %-3s 用时 %ss\n' "${name}" "${code}" "${elapsed}"
  else
    printf '失败  %-15s 退出码 %-3s 用时 %ss\n' "${name}" "${code}" "${elapsed}"
    failed+=("${name}")
  fi
done

echo "合计用时 $((SECONDS - total_start))s；输出未打印，也不上传。"
if [[ ${#failed[@]} -gt 0 ]]; then
  for name in "${failed[@]}"; do
    echo "::error::verify 未通过：${name}。公开日志不包含输出，请在私有仓库本地运行 scripts/verify-local.sh ${name} 复现。"
  done
  exit 1
fi
echo "verify 全部通过（${#checks[@]} 项）。"
