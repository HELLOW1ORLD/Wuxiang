# CMake 接入

主工程继续使用 MSVC。先构建 `wuxiang-ir`，再指定项目内 LLVM 20.1.8 的工具路径。

```cmake
set(WUXIANG_CLANG_CL "${WUXIANG_ROOT}/toolchain/clang+llvm-20.1.8-x86_64-pc-windows-msvc/bin/clang-cl.exe")
set(WUXIANG_LLC "${WUXIANG_ROOT}/toolchain/clang+llvm-20.1.8-x86_64-pc-windows-msvc/bin/llc.exe")
set(WUXIANG_IR "${WUXIANG_ROOT}/build/transform/bin/Release/wuxiang-ir.exe")
include("${WUXIANG_ROOT}/cmake/Wuxiang.cmake")

wuxiang_add_protected_library(core_protected
    SOURCES core.cpp
    INCLUDE_DIRECTORIES "${CMAKE_CURRENT_SOURCE_DIR}/include"
    CXX_STANDARD 20
    SEED 11)

add_executable(app main.cpp)
target_compile_features(app PRIVATE cxx_std_20)
wuxiang_link_protected_library(app core_protected)
```

在源文件中用 `WUXIANG_PROTECT` 标记函数。`FUNCTIONS` 可额外传入逗号分隔的、优化后仍存在的 LLVM 精确符号名。每个保护源文件都必须包含至少一个选定函数；普通辅助源文件可放入主工程的常规目标。库的每个源文件分别生成优化后的 bitcode、保护 bitcode、COFF 对象和覆盖报告，头文件依赖通过 depfile 跟踪。

保护模块固定使用 `/O2 /MD /EHsc /GR`，支持 C++17 和 C++20。`wuxiang_link_protected_library` 必须用于每个直接消费者：它将未指定的运行库设置为 `MultiThreadedDLL`，并统一 `_ITERATOR_DEBUG_LEVEL=0`。即使主工程使用 Debug 配置，也保持 `/MD` 和相同 STL 布局；调试信息和主工程优化级别仍由主工程控制。显式指定 `/MT`、`/MDd` 或其他不兼容运行库时配置失败。消费者再被其他目标使用时，这些目标也必须统一运行库与 STL 布局。

禁止接入 LTO、C++ Modules 或改变 CRT/异常/RTTI 契约的编译参数。保护库的运行库属性不能替代消费者的运行库设置，因此不要只调用 `target_link_libraries` 省略链接辅助函数。跨模块类、STL、内存释放和异常仍需执行本项目的兼容测试，并对实际业务接口增加行为测试。

报告中的 `partial` 表示有限位置被变换，不表示整个函数已经被保护。构建完成后还应运行 `wuxiang verify` 的机器码、行为、性能和体积检查。保护成功生成不代表通过 20% 耗时增幅及 2 倍体积验收。
