# 参与贡献

这个公开仓库负责 Issues、发布说明和 GitHub Actions 打包调度。应用行为由私有
Tauri 源码仓库负责，发布工作流只在临时 Runner 中检出源码；不要把应用源码复制到这里。

提交 Issue 时，请选择对应的结构化表单，并填写发布版本、平台与架构、复现步骤及脱敏后的
日志或截图。提交 Issue 前需要先公开 Star 当前项目；首次核验未通过时，Actions 会礼貌
提醒并保留 Issue 开放 10 分钟。宽限期内通过复查会删除提醒并继续开放，超时仍未通过才
以 `not planned` 关闭。对于官方 API 的 JSON 错误，请保留
endpoint 路径、HTTP 状态码、Content-Type 和简短响应预览；删除 query、签名、token、
Cookie 和设备标识。

修改工作流时，请同步增加或调整自动化测试，并运行：

```powershell
python -m unittest discover -s tests -p 'test_*.py'
actionlint -no-color
git diff --check
```

不要提交发布凭据、updater 私钥、私有源码快照或下载产物。报告敏感问题前请先阅读
`SECURITY.md`，并使用私密漏洞报告入口。
