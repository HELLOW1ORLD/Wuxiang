# Third-party notices

Wuxiang-authored source and examples use the repository's [LICENSE](LICENSE). Third-party tools retain their own terms.

## LLVM 20.1.8

The bootstrap downloads the official LLVM Windows SDK. The SDK, headers, libraries and executables are not shipped in this source archive. The project compiles against LLVM libraries when building the transformer.

LLVM is distributed under Apache-2.0 WITH LLVM-exception, with additional upstream notices for some components. See the version-pinned upstream [LICENSE.TXT](https://github.com/llvm/llvm-project/blob/llvmorg-20.1.8/llvm/LICENSE.TXT), the included [license text](licenses/LLVM-LICENSE.txt), and [LLVM policy](https://llvm.org/docs/DeveloperPolicy.html).

When redistributing a transformer linked against LLVM or redistributing any SDK components, preserve the applicable upstream license/copyright notices and review the licenses of the components actually shipped. The Wuxiang source license does not replace LLVM's license.

## Build and analysis tools

MSVC, Windows SDK, Python, CMake, REA, Ghidra, Node.js and Java are independently installed tools. They are not included in the source release; users obtain them under their respective licenses. The source release includes no commercial-game binary, assets, keys, private plugins or recovered proprietary scripts.
