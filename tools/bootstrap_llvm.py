"""Fetch the pinned official LLVM SDK into this project only."""
from pathlib import Path
import hashlib
import json
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
NAME = "clang+llvm-20.1.8-x86_64-pc-windows-msvc"
URL = "https://github.com/llvm/llvm-project/releases/download/llvmorg-20.1.8/clang%2Bllvm-20.1.8-x86_64-pc-windows-msvc.tar.xz"
DIGEST = "f229769f11d6a6edc8ada599c0cda964b7dee6ab1a08c6cf9dd7f513e85b107f"

def main():
    folder = ROOT / "toolchain"
    folder.mkdir(exist_ok=True)
    archive = folder / (NAME + ".tar.xz")
    if not archive.exists():
        print("Downloading official LLVM 20.1.8 SDK (939 MB)", flush=True)
        with urllib.request.urlopen(URL, timeout=120) as source, archive.with_suffix(".part").open("wb") as out:
            while block := source.read(1024 * 1024):
                out.write(block)
        archive.with_suffix(".part").rename(archive)
    digest = hashlib.sha256()
    with archive.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    if digest.hexdigest() != DIGEST:
        raise ValueError("Official SDK SHA256 mismatch; archive retained for inspection")
    target = folder / NAME
    required=['bin/clang-cl.exe','bin/llc.exe','include/llvm/IR/Module.h','lib/LLVMCore.lib','lib/cmake/llvm/LLVMConfig.cmake']
    marker=target/'wuxiang-sdk-complete.json'
    if not marker.is_file() or not all((target/p).is_file() for p in required):
        print("Extracting verified SDK", flush=True)
        with tarfile.open(archive) as tar:
            for entry in tar:
                destination = (folder / entry.name).resolve()
                if not destination.is_relative_to(folder.resolve()) or entry.issym() or entry.islnk():
                    raise ValueError("Unsafe archive member: " + entry.name)
                tar.extract(entry, folder)
        if not all((target/p).is_file() for p in required):raise ValueError('SDK extraction missing required files')
        marker.write_text(json.dumps({'sha256':DIGEST,'version':'20.1.8'})+'\n',encoding='utf-8')
    lock = {"schema_version": 1, "version": "20.1.8", "url": URL, "sha256": DIGEST, "directory": NAME}
    (folder / "llvm.lock.json").write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    print(target, flush=True)

if __name__ == "__main__":
    main()
