# 将 Wuxiang 发布到 GitHub

发布仓库名称建议为 `HELLOW1ORLD/Wuxiang`。源码根目录应直接包含 README、LICENSE、src、python、tests，不要把外层工作目录或 ZIP 文件提交成整个仓库。

源代码暂按 MIT 整理，版权署名 HELLOW1ORLD；上传前阅读 LICENSE。如希望改成 Apache-2.0，应先统一许可证及文档，再提交。LLVM 仍使用自己的许可证，不因 Wuxiang 使用 MIT 而改变。

## 1. 选定正确目录

打开整理后的源码目录，在该目录打开 PowerShell。例如解压源码 ZIP 后，进入最内层的 `Wuxiang` 文件夹。

```powershell
Get-ChildItem
python tools/audit_source.py
```

应看到 README.md、LICENSE、CMakeLists.txt、src、python、tests。audit 输出 `ok: true` 才继续。不要上传 toolchain、build、reports、scorer、私有会话或原游戏文件；发布版已排除这些内容。

## 2. 确认 Git 与 GitHub CLI

```powershell
git --version
gh --version
gh auth status
```

如果尚未登录，运行 `gh auth login --web`，选择 GitHub.com 和 HTTPS，按提示在浏览器中授权。已登录 HELLOW1ORLD 则无需重复登录。不要将令牌写进脚本或仓库。

## 3. 初始化本地仓库并确认提交署名

```powershell
git init -b main
git config user.name
git config user.email
```

如果本地仓库已经初始化，跳过 init。未设置或署名不合适时，只为当前仓库设置：

```powershell
git config user.name "HELLOW1ORLD"
git config user.email "替换为你在 GitHub Settings → Emails 中的提交邮箱"
```

上面的邮箱必须替换；可选 GitHub 提供的真实 noreply 地址。不要提交这段占位邮箱，且不要把 `--global` 当作必要参数。

## 4. 检查并提交源码

```powershell
git add .
python tools/audit_source.py
git diff --cached --stat
git diff --cached --check
git status --short
```

确认都是源码与文档，没有大型工具链/二进制。然后执行：

```powershell
git commit -m "Initial Wuxiang 0.1.0 source release"
```

源码清单 SOURCE-MANIFEST.json 是打包时的哈希快照，修改源代码后会自然过期；源审计检查发布边界，不能代替代码审查或全面泄密证明。

## 5. 创建公开仓库并上传

先在浏览器确认目标名称未被自己的另一个项目使用。新建目标时，执行：

```powershell
gh repo create HELLOW1ORLD/Wuxiang --public --source=. --remote=origin --push --description "Experimental Win64 C++ protection and behavior-recovery evaluation toolkit"
gh repo view --web
```

这条命令会真实创建公开仓库并上传当前提交，是正式公开的步骤。上传的是当前目录，不是整个开发工作目录。

若你已经在 GitHub 创建了同名空仓库：不要重复 create；改用下列命令。新建空仓库时不要另外勾选生成 README、LICENSE 或 .gitignore，因为源码已经包含它们。

```powershell
git remote add origin https://github.com/HELLOW1ORLD/Wuxiang.git
git remote -v
git push -u origin main
```

如果 origin 已存在，先用 `git remote -v` 确认指向正确仓库，再 push。若远端已有其他提交，先 fetch 并检查；不要用强制推送覆盖它们。

以上流程对应 [GitHub 官方导入说明](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github?platform=windows) 与 [gh repo create 手册](https://cli.github.com/manual/gh_repo_create)。

## 6. 检查网页与 CI

在仓库页面确认英文 README、中文入口、MIT 许可证和文档链接正常。打开 Actions：`Source and scoring checks` 在 push/PR 时运行；`Native LLVM validation` 需手动 Run workflow，下载完整 LLVM SDK 并编译测试。

CI 的原生自检不宣称性能达标。性能/体积必须在稳定同机环境中单独测量，正式 REA 实验还要私有新任务与隔离环境。工作流已准备，但其云端执行结果只有上传后才可确认。

建议在 About 设置 `llvm`、`cpp`、`windows`、`obfuscation`、`reverse-engineering`、`research` 等 topics，描述中保留 experimental，不声称已经有效反制 AI。

## 7. 发布版本与后续更新

首轮 CI 和文档检查通过后，可发布源码版本：

```powershell
git tag -a v0.1.0 -m "Wuxiang 0.1.0 experimental source release"
git push origin v0.1.0
gh release create v0.1.0 --title "Wuxiang 0.1.0 — experimental source release" --notes-file CHANGELOG.md
```

GitHub 自动提供 Source code ZIP/TAR，不必上传 939 MB SDK。若以后发布预编译 LLVM 链接工具，应另外包含适用的 LLVM 许可证/组件通知。

日常修改后：

```powershell
python tools/audit_source.py
git add .
git diff --cached --stat
git diff --cached --check
git commit -m "Describe the actual change"
git push
```

最初整理的源码目录是独立副本。开始在此维护后，以 GitHub 仓库为主；不要再用本地导出工具覆盖已有修改或提交历史。
