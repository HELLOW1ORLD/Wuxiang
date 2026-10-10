# Wuxiang

面向 REA 等多工具代理的 Win64 C++ 函数保护与行为恢复评测实验工具。MSVC 编译主程序，项目内固定 LLVM 20.1.8 编译选定模块，经 IR 变换后生成 COFF，再由 MSVC 链接。

**当前为 0.1.0 研究原型，尚未证明能有效提高 REA 的恢复成本。** 首次保护版短分支被成功恢复，部分基准超过性能/体积上限。公开版本保留这些限制，详见 [结果与边界](docs/results.md)。

## 先运行示例

需要 Windows x64、Python 3.10+、VS2022 的「使用 C++ 的桌面开发」、Windows SDK、CMake 和 DIA SDK。无需安装 pip 包。

在本仓库根目录打开 PowerShell：

```powershell
python tools/bootstrap_llvm.py
python wuxiang.py doctor
python wuxiang.py protect --config examples/compat.json
python wuxiang.py verify --config examples/compat.json
python -m unittest discover -s tests -v
```

Bootstrap 下载并校验官方 939 MB LLVM SDK；解压后需要数 GB 空间。首次 protect 自动编译 C++ 变换器。LLVM 工具链与构建结果均在本仓库目录内生成，不上传 GitHub。

建议按 [中文使用教程](docs/usage.zh-CN.md) 完成环境检查、示例验证、自己的模块接入和评分试验；[CMake 接入](docs/cmake-adapter.md) 提供静态库与 MSVC 混合链接示例。

## 能做什么

`WUXIANG_PROTECT` 选择函数；首版按种子改写有限整数表达式与普通控制流区域。每个函数最多一个整数位置和一个结构区域，报告始终标记部分覆盖。异常控制结构保留；完全无法变换时明确失败。

支持 C++17/20 的示例矩阵：类、继承、虚函数、RTTI、模板、STL、RAII、跨模块异常与释放。统一 `/MD /EHsc /GR`。不承诺保护协程、SEH、内联汇编、C++ Modules 或跨模块 LTO。

工具提供 protect、verify、doctor、离线任务准备、候选实际编译评分和配对汇总。成功生成保护产物不等于验收成功：选定函数耗时中位数不得超过基线 1.20 倍，模块 COFF `.text` 不得超过 2 倍。

## 开源后的评测限制

仓库包含六类示例算法及测试生成器，因此它们是公开回归样例。允许检索本仓库的代理能直接找到原算法；正式评测须使用未公开的新任务，并隔离源码、映射和隐藏测试。评分器不是操作系统沙箱，正式对抗测试需要独立环境。

完整协议见 [evaluation.md](docs/evaluation.md)。本仓库不包含原游戏文件、密钥、私有恢复数据、代理会话或隐藏评分包。

源代码使用 [MIT 许可证](LICENSE)，LLVM 等第三方工具另适用各自许可证。上传步骤见 [GitHub 操作指南](docs/github-upload.zh-CN.md)。
