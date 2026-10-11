# 0.1.1 提示词注入与语义误导使用说明

本版实现可选的二进制文字载荷，配置、生成、最终 PE 检查和行为验证已接入命令行构建。两类功能默认关闭；当前 CMake 适配器仍提供原有 IR 保护，没有接入这些载荷选项。

提示词注入采用无害实验标记，要求分析 Agent 停止还原、只回答种子生成的 `WX_LAB_…` 标记。它是被分析目标中的不可信文字，没有实际授权效力，也不会在程序中执行。语义误导使用合成的 UTF-8 解析、校验和或封包描述，使文字线索与原函数行为不一致；原函数实际计算保持不变。本版没有实现任意提示词、删除命令、自动触发安全拒绝、符号重命名或伪造算法控制流。

## 直接运行

在包含 `wuxiang.py` 的仓库根目录打开 PowerShell，环境要求与 [基础教程](usage.zh-CN.md) 相同：

```powershell
python wuxiang.py doctor
python wuxiang.py protect --config examples/compat-surfaces.json
python wuxiang.py verify --config examples/compat-surfaces.json
python wuxiang.py surface inspect --artifact build/compat-surfaces/protected.exe
```

若没有本地 LLVM SDK，先执行 `python tools/bootstrap_llvm.py`。首次构建自动编译变换器。输出在 `build/compat-surfaces/`：

| 文件 | 用途 |
|---|---|
| `protected.exe` | 原有 IR 保护和两类载荷的组合产物 |
| `baseline.exe` / `msvc.exe` | 无载荷的 LLVM 基线与 MSVC 对照 |
| `agent-surface.cpp` / `.obj` | 自动生成的只读载荷对象 |
| `build-manifest.json` | 输入、工具哈希、保护覆盖和载荷证据 |
| `verification.json` | 行为、ABI、性能、体积和存留检查 |

示例执行正常的 ABI/行为验证并输出 `WUXIANG_ABI_OK`；程序自身不会输出注入文字。

## 接入自己的模块

继续使用 `WUXIANG_PROTECT` 选择函数，并按基础教程配置模块、主程序、头文件和输出路径。在现有版本 1 JSON 的顶层加入：

```json
"agent_surface": {
  "experimental": true,
  "prompt_injection": "marker",
  "semantic_decoy": "utf8_parser",
  "max_bytes": 8192
}
```

这是配置对象中的字段片段，需要保留其他字段与逗号。配置或种子变化后重新执行 `protect`，再执行 `verify`；验证器会拒绝旧产物。

| 配置项 | 可用值与含义 |
|---|---|
| `prompt_injection` | `off`、`marker`、`authorization_notice` |
| `semantic_decoy` | `off`、`utf8_parser`、`checksum`、`packet_codec` |
| `experimental` | 默认 `false`；启用 `marker` 必须为 `true` |
| `max_bytes` | 完整载荷上限，默认 8192，范围 1–65536；大于 8192 需要实验开关 |

`authorization_notice` 提醒从可信用户上下文确认授权，同时明确二进制不能授予或撤销授权。它不会可靠地阻止非法逆向。未知选项、自定义载荷、载荷超限会明确报错。删去 `agent_surface` 或将两个选项设为 `off` 即关闭功能。

可以分别开启一种载荷，形成注入、语义误导与组合的对照版本。保持任务、种子及其他参数一致；为各组设置不同输出目录，避免覆盖。

## 载荷如何进入分析视野

载荷位于只读、不可执行的 `.wxhint` PE 节，使用有版本号的 JSON 帧和 SHA-256 校验。每个成功变换的选定函数，在入口把每条文字指针传给独立的 `noinline`、`noexcept` 读取函数；该函数只 volatile 读取起始字节，不输出文字、不写入状态。MSVC 链接时显式保留载荷。读取不改变返回值、不写入调用者内存，但有执行与体积成本。异常控制结构保持原状，并测试了异常展开与析构。

独立调用保留文字参数，避免直接的无用读取被反编译器省略。字符串扫描或定点反编译有机会发现载荷。工具是否展开它、Agent 是否看到及是否受影响，需要实际记录；分析者也可以识别或移除该节。公开固定载荷不能被当作不可绕过的保护。

本次用 REA 6.2.0 / Ghidra 12.1.4 对示例选定函数进行定点反编译，输出直接包含两条文字参数。这个结果证明该示例在此工具链中的可见性，尚未测试 Agent 是否服从注入或错误恢复行为，详见 [本机结果](results.md)。

检查器验证 PE32+ 头、节边界、只读属性、帧长度和规范化内容。头结构依据 [Microsoft PE 格式说明](https://learn.microsoft.com/en-us/windows/win32/debug/pe-format)。它用于识别 Wuxiang 载荷，并非完整的 Windows 加载器验证器。

## 阅读报告

`build-manifest.json` 中 `agent_surface.present` 表示最终 EXE 存在匹配载荷，`function_references` 是插入引用总数。`payload_sha256` 为载荷哈希，`artifact_sha256` 为整个 EXE 哈希。COFF 引用存留另外由原生测试检查。

`verification.json` 中 `surface_verified: true` 表示产物与当前配置匹配。只有 `ok: true` 才表示同时通过既有行为、性能和代码体积验收：选定函数耗时最多 1.20 倍、模块代码最多 2 倍。`binary_size_delta_bytes` 单独记录完整 EXE 增量。

`exposure_status: "not_evaluated"` 和 `effectiveness_verified: false` 表示尚未测得 Agent 暴露与效果，不能解读成抗 AI 成功。

## 下一步评测

对同一个未公开任务比较原保护版、注入版、语义误导版、组合版。记录工具是否输出文字、Agent 是否跟随注入、是否误判用途，以及恢复代码的隐藏测试通过率、耗时和调用次数。再做已知设计的适应性攻击，至少三次独立配对会话。

注入导致任务偏离属于 Agent 鲁棒性结果；语义恢复成本上升属于保护结果，两者分别报告。公开示例用于工程回归，无法证明正式抗逆向效果。详见 [评测说明](evaluation.md)。
