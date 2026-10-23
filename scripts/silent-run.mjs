#!/usr/bin/env node
// 公开 runner 上静默运行会编译私有源码的命令。
//
// rustc 的编译错误会带私有源码片段，链接失败会把整条链接命令（完整依赖清单、
// 私有 crate 名）打出来，Gradle / Xcode / 打包工具也会转述这些输出。这里把子进程
// 的 stdout/stderr 只写进 runner 本地临时目录里的文件，不打印、不上传，结束时删掉；
// 公开日志只有一行“通过/失败、退出码、用时”，失败时再加一行本地复现提示。
//
// 用法：
//   node silent-run.mjs --name <名称> [--repro "<复现命令>"] -- <命令> [参数...]
//   node silent-run.mjs --tauri <tauri 参数...>
//     供 tauri-action 的 tauriScript 使用：tauri-action 会在后面追加
//     “build --target ... --bundles ... --config ...”。和 tauri-action 默认行为一样，
//     没有 tauri 命令时先静默执行 npm install -g @tauri-apps/cli@v2。
//
// Windows / macOS / Linux 通用（用 Node 而不是 bash，tauri-action 在 Windows 上
// 直接 spawn tauriScript，不经过 shell）。

import { spawn } from "node:child_process";
import { closeSync, mkdtempSync, openSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const isWindows = process.platform === "win32";
const HEARTBEAT_MS = Number(process.env.SILENT_RUN_HEARTBEAT_MS || 5 * 60 * 1000);
// Windows 上 npm / tauri 是 .cmd，必须经过 cmd.exe；只接受不含 shell 元字符的参数。
const SAFE_ARG = /^[A-Za-z0-9_@%+=:,.\/\\-]+$/;

let logDir = "";
let child = null;

function cleanup() {
  if (logDir) {
    rmSync(logDir, { recursive: true, force: true });
    logDir = "";
  }
}

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => {
    if (child) child.kill(signal);
    cleanup();
    process.exit(signal === "SIGINT" ? 130 : 143);
  });
}

function usage(message) {
  console.log(`::error::silent-run: ${message}`);
  cleanup();
  process.exit(2);
}

function pad(text, width) {
  return text + " ".repeat(Math.max(1, width - text.length));
}

// 运行一条命令，输出只进本地文件。返回退出码，并打印一行汇总。
function runQuiet(name, command, args, { report = true } = {}) {
  return new Promise((resolve) => {
    if (isWindows && ![command, ...args].every((part) => SAFE_ARG.test(part))) {
      console.log(`::error::silent-run: ${name} 的参数含有不安全字符，拒绝经过 cmd.exe 运行`);
      resolve(2);
      return;
    }
    const logPath = join(logDir, `${name.replace(/[^A-Za-z0-9_.-]/g, "_")}.log`);
    const fd = openSync(logPath, "w");
    const start = Date.now();
    const seconds = () => Math.round((Date.now() - start) / 1000);
    const env = { ...process.env, CARGO_TERM_COLOR: "never", CARGO_TERM_PROGRESS_WHEN: "never", NO_COLOR: "1" };
    const options = { stdio: ["ignore", fd, fd], env };
    try {
      child = isWindows
        ? spawn([command, ...args].join(" "), { ...options, shell: true })
        : spawn(command, args, options);
    } catch {
      child = null;
    }
    const heartbeat = setInterval(() => {
      console.log(`… ${name} 仍在运行，已用 ${seconds()}s`);
    }, HEARTBEAT_MS);
    const finish = (code) => {
      clearInterval(heartbeat);
      closeSync(fd);
      child = null;
      if (report) {
        const status = code === 0 ? "通过" : "失败";
        console.log(`${status}  ${pad(name, 22)}退出码 ${pad(String(code), 4)}用时 ${seconds()}s`);
      }
      resolve(code);
    };
    if (!child) {
      finish(127);
      return;
    }
    let done = false;
    child.on("error", () => {
      if (!done) {
        done = true;
        finish(127);
      }
    });
    child.on("close", (code) => {
      if (!done) {
        done = true;
        finish(code === null ? 1 : code);
      }
    });
  });
}

function fail(name, code, repro) {
  console.log(
    `::error::${name} 未通过（退出码 ${code}）。公开日志不包含构建输出，` +
      `请在私有仓库本地运行 ${repro} 复现。`,
  );
  cleanup();
  process.exit(code);
}

async function main() {
  const argv = process.argv.slice(2);
  logDir = mkdtempSync(join(process.env.RUNNER_TEMP || tmpdir(), "silent-run-"));

  if (argv[0] === "--tauri") {
    const tauriArgs = argv.slice(1);
    if (tauriArgs.length === 0) usage("--tauri 后面缺少 tauri 子命令");
    const sub = tauriArgs.filter((arg) => !arg.startsWith("-")).slice(0, 2);
    const targetIndex = tauriArgs.indexOf("--target");
    const target = targetIndex >= 0 ? tauriArgs[targetIndex + 1] : "";
    const name = ["tauri", sub[0] || "run", target].filter(Boolean).join("-");
    const repro = `"cargo tauri ${tauriArgs.join(" ")}"`;

    // 只是探测有没有 tauri 命令，不打印汇总行（没装时的“失败”会误导人）。
    if ((await runQuiet("tauri-cli-check", "tauri", ["--version"], { report: false })) !== 0) {
      const installed = await runQuiet("tauri-cli-install", "npm", ["install", "-g", "@tauri-apps/cli@v2"]);
      if (installed !== 0) fail("tauri-cli-install", installed, '"npm install -g @tauri-apps/cli@v2"');
    }
    const code = await runQuiet(name, "tauri", tauriArgs);
    if (code !== 0) fail(name, code, repro);
    cleanup();
    return;
  }

  let name = "";
  let repro = "";
  let index = 0;
  for (; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--") {
      index += 1;
      break;
    }
    if (arg === "--name") name = argv[++index] || "";
    else if (arg === "--repro") repro = argv[++index] || "";
    else usage(`未知参数 ${arg}`);
  }
  const command = argv.slice(index);
  if (!name) usage("缺少 --name");
  if (command.length === 0) usage("缺少要运行的命令（放在 -- 之后）");
  const code = await runQuiet(name, command[0], command.slice(1));
  if (code !== 0) fail(name, code, `"${repro || command.join(" ")}"`);
  cleanup();
}

main().catch(() => {
  // 不打印异常内容（可能带路径或输出片段）。
  console.log("::error::silent-run 内部错误");
  cleanup();
  process.exit(1);
});
