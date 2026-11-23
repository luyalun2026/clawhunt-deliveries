# CI 工作流副本

本仓库的令牌没有 GitHub `workflow` scope，因此无法直接写入 `.github/workflows/`。
下列文件原样放在 `ci/workflows/`，如需启用 CI，请复制回标准路径：

- `ci/workflows/ci.yml` -> `.github/workflows/ci.yml`
