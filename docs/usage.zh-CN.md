# 从示例到自己的 C++ 模块

0.1.1 的提示词注入与语义误导载荷另见 [功能教程](agent-surfaces.zh-CN.md)，可直接用 `examples/compat-surfaces.json` 构建并验证。

## 1. 准备环境

打开 Visual Studio Installer，在 VS2022 中安装「使用 C++ 的桌面开发」，并确认 MSVC x64、Windows SDK、CMake 和 DIA SDK 可用。安装 Python 3.10+，在 PowerShell 运行 `python --version`。本项目无需 pip 安装。

在仓库根目录运行：

```powershell
python tools/bootstrap_llvm.py
python wuxiang.py doctor
```

第一次 bootstrap 要下载官方 939 MB 归档，之后核对 SHA-256 并解压。不要把 toolchain 提交到 Git；重跑 bootstrap 会核验缓存并补齐未完成的解压。

doctor 输出 `native_build: true` 表示构建依赖检查通过。首次构建前 `transformer: false` 正常。REA 未安装只影响攻击分析，不影响保护工具使用。实际变换器构建和示例运行才证明构建链可用。

## 2. 保护并验证现有示例

```powershell
python wuxiang.py protect --config examples/compat.json
python wuxiang.py verify --config examples/compat.json
```

配置选择 `examples/compat/module.cpp` 作为 Clang 模块，`main.cpp` 作为 MSVC 主程序；输出位于 `build/compat`。CLI 最后输出版本 1 JSON，PowerShell 中 `$LASTEXITCODE` 为 0 表示这条命令通过。

| 文件 | 如何使用 |
|---|---|
| `build/compat/protected.exe` | 实际保护版，运行应输出 `WUXIANG_ABI_OK` |
| `baseline.exe` | 同一 LLVM 流程的未保护对照 |
| `msvc.exe` | MSVC 原始模块的额外对照 |
| `build-manifest.json` | 输入/工具哈希、构建参数、覆盖及机器码检查 |
| `module0.coverage.json` | IR 变换覆盖与部分覆盖原因 |
| `verification.json` | 行为比较、全部计时样本和性能/体积验收 |

protect 的 `ok` 只表示构建/机器码检查通过。verify 的 `ok` 才包括行为及固定上限。`partial` 表示有限位置被改写，不是整个函数受到保护；性能失败也不能解释为抗逆向成功。

继续验证 C++17 和测试矩阵：

```powershell
python wuxiang.py protect --config examples/compat17.json
python wuxiang.py verify --config examples/compat17.json
python -m unittest discover -s tests -v
```

## 3. 接入自己的模块

在函数定义上添加注解，并保证 include 路径包含仓库 `include`：

```cpp
#include "wuxiang/protect.h"
WUXIANG_PROTECT unsigned long long calculate(unsigned long long x) {
    // 保留你原来的、定义良好的业务实现。
    return (x ^ 31ULL) + 7ULL;
}
```

此代码仅演示注解，不保证短函数能通过性能或机器码存活验收。源码保护工具输入 C++ 源码，不负责从已有 EXE 还原源码。

复制 `examples/compat.json` 为自己的配置，然后替换：

```json
{
  "schema_version": 1,
  "mode": "balanced",
  "standard": "c++20",
  "seed": 11,
  "module": {"sources": ["../my-code/module.cpp"]},
  "main": {"sources": ["../my-code/test-main.cpp"]},
  "include_dirs": ["../my-code/include"],
  "output_dir": "../build/my-module",
  "verification": {"expected_stdout": "SELF_TEST_OK"}
}
```

路径相对于 JSON 文件；上例假定配置位于 `examples`，源文件位于仓库内 `my-code`。输出必须在本仓库内。主程序应比较正确的返回值、内存修改和异常行为，在成功时输出 `SELF_TEST_OK`；不要只打印成功字符串而不检查行为。

main 还需实现 `--timing`：进程内重复调用被选定的函数，输出 `{"ns_per_call": 123.4}` 或 `{"median_ns_per_call": 123.4}`。已有 `examples/compat/main.cpp` 展示了计时方式。多个函数须设置 `verification.timings`，每项使用精确 LLVM 函数符号和对应计时参数，逐函数验证，不能用聚合耗时掩盖超限。

```powershell
python wuxiang.py protect --config examples/my-module.json
python wuxiang.py verify --config examples/my-module.json
```

无注解、选定函数已被优化掉或没有可安全改写位置会报错；不能通过取消保护伪装通过。对接现有应用时，先用单独的验证主程序检查模块，再按 [CMake 示例](cmake-adapter.md) 与实际 MSVC 工程链接；所有消费者统一 CRT 和 STL 布局。

## 4. 跑离线评分链

```powershell
python tools/build_benchmark.py
python wuxiang.py bench prepare --config bench-config.json
```

生成六类 × 三种子 × 三编译变体，共 54 个二进制。任一组超出 20%/2 倍门槛，正式 prepare 返回失败。研究失败原因时才使用：

```powershell
python wuxiang.py bench prepare --config bench-research-config.json
```

研究包有 54 个盲测目录及 54 个已知设计目录，评分包单独保存。默认目录 `research-packs-final` 必须为空；重复导出请在配置中换一个新目录。编译和开销失败均保留，研究导出不使失败保护变成达标。

每个候选提交放在自己的目录，例如 `submissions/session1`。按攻击包 `task.h` 实现 candidate.cpp，保存 transcript.json；submission.json 使用：

```json
{
  "schema_version": 1,
  "scoring_manifest": "../../research-packs-final/scorer/manifest.json",
  "pack_id": "从任务包 task.json 复制编号",
  "artifact_sha256": "从 task.json 复制目标哈希",
  "candidate_source": "candidate.cpp",
  "transcript_path": "transcript.json",
  "session_id": "独立且唯一的会话编号",
  "pair_id": "配对编号",
  "elapsed_seconds": 120,
  "mode": "blind",
  "environment": {
    "model": "实际模型版本",
    "rea_version": "实际 REA 版本",
    "tools": ["实际工具与版本"],
    "dynamic_available": false
  }
}
```

占位内容必须替换为实际记录。transcript 为 `{"schema_version":1,"events":[...]}`，每次工具操作含 `kind: tool_call`，附真实参数、时间、观察和证据。未使用调试器不能填写已测试动态分析。

```powershell
python wuxiang.py bench score --submission submissions/session1/submission.json
python wuxiang.py bench summarize --scores research-packs-final/scorer/scores
```

公开算法只用来验证评分器。正式恢复成本实验换用私有新任务，见 [评测协议](evaluation.md)。本地运行限可信候选；原生评分程序能访问当前用户的文件，目录分开不等于沙箱。

## 5. 常见问题

- 缺编译器/SDK：回到 VS Installer 补组件，重跑 doctor。
- DIA SDK 路径错误：按 CMake 错误提示指定本机 x64 `diaguids.lib`。
- Stale build：源码、实际头文件、配置或工具改变后，重跑 protect 再 verify。
- verify 返回失败：查看行为输出、`runtime_ratio` 与 `code_size_ratio`，不要把构建成功当成验收。
- REA 后端缺失：显式使用 `tools/rea_probe.py` 的 `--rea-cli`、`--ghidra`、`--java-home`；这些工具按各自方式安装，仓库不包含它们。
