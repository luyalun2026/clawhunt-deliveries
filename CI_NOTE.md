# CI 配置说明

本仓库的 GitHub Actions 工作流文件原始路径是仓库内的 `.github/workflows/`。
当前推送所用令牌没有 `workflow` 权限，无法写入 `.github/workflows/`，
因此工作流内容以**同等内容**放在 `ci/workflows/` 下（文件名不变）。

复用到真实 CI 的方法（任选其一）：

```bash
mkdir -p .github/workflows && cp -r ci/workflows/. .github/workflows/   # 方式一：复制回标准路径
```

```bash
python -m pytest tests -q            # 方式二（更常用）：直接在本地跑等价命令，效果与 CI 一致
```

`outputs/` 下已附 CI 等价命令的真实运行输出，可离线核对。
