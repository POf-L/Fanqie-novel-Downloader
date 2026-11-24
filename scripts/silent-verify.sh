#!/usr/bin/env bash
# 公开 runner 上的静默 verify：在私有源码目录里跑 fmt / clippy / test / node 等检查，
# 每一项的全部输出都只写到 runner 本地的临时文件，不进公开日志、不作为 artifact
# 上传，脚本结束时删掉。日志里只有每项的名称、通过/失败、退出码和用时。
#
# 检查清单必须和私有仓库的 scripts/verify-local.sh 完全一致（名称、命令、顺序），
# 失败时在本地运行 `scripts/verify-local.sh <名称>` 就能看到完整输出。脚本先做一次
# checklist-sync：逐行比对两份清单，不一致直接失败，避免两边悄悄漂移。
#
# cargo clippy / test 都带 --locked：Cargo.lock 与 Cargo.toml 不一致时报错，而不是
# 在 CI 里悄悄重新解析依赖（cargo fmt 不解析依赖，不需要也不接受 --locked）。
#
# clippy-default 只开默认特性（desktop-app）：--all-features 会把 cli 一起打开，
# 只被 CLI 用到的代码会掩盖桌面版里的死代码，这一遍专门把它们找出来。
#
# 设置了 GITHUB_OUTPUT 时写出 passed / total / summary，供发布说明引用。
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
  "clippy-desktop|cargo clippy --locked --manifest-path src-tauri/Cargo.toml --all-targets --all-features -- -D warnings"
  "clippy-default|cargo clippy --locked --manifest-path src-tauri/Cargo.toml --all-targets -- -D warnings"
  "clippy-cli|cargo clippy --locked --manifest-path src-tauri/Cargo.toml --bin fanqie --no-default-features --features cli -- -D warnings"
  "test-desktop|cargo test --locked --manifest-path src-tauri/Cargo.toml --all-features"
  "test-cli|cargo test --locked --manifest-path src-tauri/Cargo.toml --bin fanqie --no-default-features --features cli"
  "node-test|node --test tests/*.js"
  "node-check|node --check web/static/app.js"
  "diff-check|git diff --check"
)

failed=()
total_start=${SECONDS}

# checklist-sync：私有仓库 verify-local.sh 里 checks=( ... ) 的每一行必须与上面完全相同。
# 比对结果只给通过/失败，不打印私有脚本内容。
local_script="scripts/verify-local.sh"
if [[ -f "${local_script}" ]] &&
   diff -q <(printf '%s\n' "${checks[@]}") \
     <(sed -n '/^checks=(/,/^)/p' "${local_script}" | sed -n 's/^  "\(.*\)"$/\1/p') \
     >/dev/null 2>&1; then
  printf '通过  %-15s 退出码 %-3s 用时 %ss\n' "checklist-sync" 0 0
else
  printf '失败  %-15s 退出码 %-3s 用时 %ss\n' "checklist-sync" 1 0
  echo "::error::silent-verify.sh 与私有仓库 ${local_script} 的检查清单不一致（名称、命令、顺序须完全相同），请两边同步修改。"
  failed+=("checklist-sync")
fi

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
total=${#checks[@]}
passed=0
for entry in "${checks[@]}"; do
  name="${entry%%|*}"
  [[ " ${failed[*]} " == *" ${name} "* ]] || passed=$((passed + 1))
done
if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  {
    echo "passed=${passed}"
    echo "total=${total}"
    echo "summary=verify ${passed}/${total} 通过"
  } >>"${GITHUB_OUTPUT}"
fi
if [[ ${#failed[@]} -gt 0 ]]; then
  for name in "${failed[@]}"; do
    if [[ "${name}" == "checklist-sync" ]]; then
      continue
    fi
    echo "::error::verify 未通过：${name}。公开日志不包含输出，请在私有仓库本地运行 scripts/verify-local.sh ${name} 复现。"
  done
  exit 1
fi
echo "verify 全部通过（${#checks[@]} 项）。"
