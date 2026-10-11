# Wuxiang

[English](README.md) · [使用教程](docs/usage.zh-CN.md) · [提示词注入与语义误导](docs/agent-surfaces.zh-CN.md) · [评测协议](docs/evaluation.md)

面向 REA 等多工具代理的 Win64 C++ 函数保护与行为恢复评测实验工具。MSVC 编译主程序，项目内固定 LLVM 20.1.8 编译选定模块，经 IR 变换后生成 COFF，再由 MSVC 链接。

**当前为 0.1.1 研究原型，尚未证明能有效提高 REA 的恢复成本。** 首次保护版短分支被成功恢复，部分基准超过性能/体积上限。公开版本保留这些限制，详见 [结果与边界](docs/results.md)。

## 0.1.1 新增功能

提示词注入与语义误导已接入命令行构建和验证，两类功能默认关闭：

| 功能 | 当前实现 |
|---|---|
| 提示词注入 | 无害实验标记，要求分析 Agent 只回答按种子生成的 `WX_LAB_…`；另提供授权提醒预设 |
| 语义误导 | 合成的 UTF-8 解析器、校验和、封包描述，向分析者提供误导性文字线索 |
| 定点分析可见性 | 选定函数把文字指针传给独立 `noinline`、`noexcept` 读取函数 |
| 产物验证 | 检查只读、不可执行的 `.wxhint` PE 节、内容哈希和配置一致性 |

读取函数只做 volatile 字节读取，不执行文字、不改变原函数结果。二进制文字属于不可信目标数据，不能授予或撤销分析授权。本版不支持任意命令载荷，也不能保证触发 AI 安全拒绝。配置预设和实现细节见 [新增功能教程](docs/agent-surfaces.zh-CN.md)。

新增选项通过 JSON/CLI 流程使用；当前 CMake 适配器仍提供原有 IR 保护，尚未接入文字载荷选项。

## 先运行示例

需要 Windows x64、Python 3.10+、VS2022 的「使用 C++ 的桌面开发」、Windows SDK、CMake 和 DIA SDK。无需安装 pip 包。

在本仓库根目录打开 PowerShell：

```powershell
python tools/bootstrap_llvm.py
python wuxiang.py doctor
python wuxiang.py protect --config examples/compat-surfaces.json
python wuxiang.py verify --config examples/compat-surfaces.json
python wuxiang.py surface inspect --artifact build/compat-surfaces/protected.exe
```

Bootstrap 下载并校验官方 939 MB LLVM SDK；解压后需要数 GB 空间。首次 protect 自动编译 C++ 变换器。LLVM 工具链与构建结果均在本仓库目录内生成，不上传 GitHub。

输出位于 `build/compat-surfaces/`：

| 文件 | 用途 |
|---|---|
| `protected.exe` | IR 保护与两类文字载荷的组合版本 |
| `baseline.exe` / `msvc.exe` | 不携带文字载荷的 LLVM 基线与 MSVC 对照 |
| `build-manifest.json` | 输入、工具哈希、保护覆盖和载荷证据 |
| `verification.json` | 行为、ABI、性能、体积和载荷验证 |

三个程序应输出 `WUXIANG_ABI_OK`。`verify` 输出 `ok: true` 表示通过工程验收；`surface inspect` 只证明载荷存在，不能证明抗 AI 效果。

只使用原有 IR 保护时，改用 `examples/compat.json`；C++17 示例为 `examples/compat17.json`。回归测试执行 `python -m unittest discover -s tests -v`。

建议按 [中文使用教程](docs/usage.zh-CN.md) 完成环境检查、示例验证、自己的模块接入和评分试验；[CMake 接入](docs/cmake-adapter.md) 提供静态库与 MSVC 混合链接示例。

## 0.1.1 本机验证结果

以下结果记录于 2026-10-11，使用 `examples/compat-surfaces.json`：

| 检查 | 结果 |
|---|---|
| 回归测试 | 30 项通过，覆盖 ABI、行为、异常/析构与载荷检查 |
| REA 6.2.0 / Ghidra 12.1.4 定点反编译 | 两条文字直接显示为读取函数的参数 |
| 选定函数耗时中位数 | 比同一 LLVM 基线增加约 3.86% |
| 保护模块代码体积 | 增加约 1.39%；完整 EXE 增加 1536 字节 |
| AI 服从注入、误判语义或恢复成本上升 | 尚未评测 |

这些是一个示例在本机上的测量，不代表所有模块的开销。工具显示文字不等于 Agent 会受其影响；接入自己的模块后仍需运行验证。完整记录与此前失败样例见 [结果与边界](docs/results.md)。

## 能做什么

`WUXIANG_PROTECT` 选择函数；首版按种子改写有限整数表达式与普通控制流区域。每个函数最多一个整数位置和一个结构区域，报告始终标记部分覆盖。异常控制结构保留；完全无法变换时明确失败。

支持 C++17/20 的示例矩阵：类、继承、虚函数、RTTI、模板、STL、RAII、跨模块异常与释放。统一 `/MD /EHsc /GR`。不承诺保护协程、SEH、内联汇编、C++ Modules 或跨模块 LTO。

工具提供 protect、verify、doctor、离线任务准备、候选实际编译评分和配对汇总。成功生成保护产物不等于验收成功：选定函数耗时中位数不得超过基线 1.20 倍，模块 COFF `.text` 不得超过 2 倍。

## 开源后的评测限制

仓库包含六类示例算法及测试生成器，因此它们是公开回归样例。允许检索本仓库的代理能直接找到原算法；正式评测须使用未公开的新任务，并隔离源码、映射和隐藏测试。评分器不是操作系统沙箱，正式对抗测试需要独立环境。

完整协议见 [evaluation.md](docs/evaluation.md)。本仓库不包含原游戏文件、密钥、私有恢复数据、代理会话或隐藏评分包。

源代码使用 [MIT 许可证](LICENSE)，LLVM 等第三方工具另适用各自许可证。上传步骤见 [GitHub 操作指南](docs/github-upload.zh-CN.md)。
