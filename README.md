# 番茄小说下载器

[![GitHub release](https://img.shields.io/github/release/POf-L/Fanqie-novel-Downloader.svg)](https://github.com/POf-L/Fanqie-novel-Downloader/releases)
[![GitHub stars](https://img.shields.io/github/stars/POf-L/Fanqie-novel-Downloader.svg)](https://github.com/POf-L/Fanqie-novel-Downloader)
[![Build Status](https://github.com/POf-L/Fanqie-novel-Downloader/workflows/Build%20and%20Release/badge.svg)](https://github.com/POf-L/Fanqie-novel-Downloader/actions)

一个现代化、高效的番茄小说下载器。

当前版本统一通过 Tomato Gateway 提供图书搜索、详情获取与正文下载能力，并提供简洁、响应式的本地 Web 界面，桌面端优先通过 PyWebview 打开，支持打包为 Windows、Linux、macOS 客户端直接使用。

## ✨ 功能特性

- 🔎 **图书搜索**：支持按书名、作者等关键字快速检索小说
- 📚 **书籍详情**：查看作品信息、章节数据与下载目标
- 📥 **小说下载**：稳定获取正文内容并保存到本地
- 📦 **批量下载**：支持一次下载多本图书并显示任务进度
- 📄 **多格式导出**：支持导出为 **TXT** 和 **EPUB**
- 🖼️ **封面嵌入**：自动获取封面并写入 EPUB 文件
- 📑 **章节控制**：支持整本下载、章节范围下载与手动选章
- 🌐 **图形界面**：提供本地 Web UI，桌面端优先使用 PyWebview 内嵌窗口
- 🖥️ **跨平台运行**：支持 Windows、Linux、macOS 多平台发布

## 🚀 如何使用

普通用户请直接前往 Releases 下载客户端：

- 下载地址：<https://github.com/POf-L/Fanqie-novel-Downloader/releases>
- 选择适合你系统的构建产物
- 下载后直接运行程序即可启动界面

典型使用流程：

1. 启动客户端
2. 输入书名或作者进行搜索
3. 选择目标书籍
4. 选择导出格式（TXT / EPUB）
5. 按需选择整本、章节范围或手动选章
6. 开始下载并等待完成

## 🧩 当前实现形态

当前版本的核心体验包括：

- 本地启动 Web 服务并优先通过 PyWebview 打开图形界面
- Windows 独立版内置 WebView2 Runtime，无需系统额外安装
- 搜索、详情、下载能力统一由 Tomato Gateway 提供
- 发布流程由 GitHub Actions 自动打包并上传产物

## 📦 适合哪些场景

- 想快速搜索并下载番茄小说
- 需要批量整理 TXT / EPUB 小说文件
- 希望在本地以图形界面方式操作
- 需要直接下载现成客户端，而不是自行搭建源码环境

## 📌 仓库说明

这个公开仓库展示的是 **番茄小说下载器** 项目本身。

目前公开仓库主要承担以下职责：

- 对外展示项目功能
- 提供 Releases 下载入口
- 承载 GitHub Actions 打包与发布流程

实际业务源码在私有仓库维护；公开仓库中的说明文档会按私有源码当前能力同步更新。
