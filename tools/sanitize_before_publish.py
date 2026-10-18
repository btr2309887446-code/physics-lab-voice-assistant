# -*- coding: utf-8 -*-
"""上传公开仓库前的脱敏处理。

用法：
    python tools/sanitize_before_publish.py <要脱敏的目录> [--secrets <密钥清单文件>]

密钥清单文件格式（一行一条，`原文 => 替换为`）：
    某个密码 => <已移除，请向负责人索取>
    某个 API Key => <已移除>

如果不传 --secrets，会依次尝试环境变量 SANITIZE_SECRETS_FILE 和当前目录的
`.sanitize_secrets` 文件。

**密钥清单本身不要提交进仓库**（.gitignore 已包含 `.sanitize_secrets`）。
"""
import os
import sys

DEFAULT_WARNING = """> ⚠️ **公开仓库脱敏说明**
>
> 本文档原本含有明文凭据，已在上传前替换为占位符。
> 如果你手里有更早的副本，请视为凭据已泄露，**立即更换**。

"""

EXTS = {".md", ".txt", ".yaml", ".yml", ".json", ".py", ".java",
        ".dart", ".cc", ".h", ".env"}

SKIP_DIRS = {".git", "node_modules", "build", "dist", "__pycache__"}


def load_secrets(path):
    """读取 `原文 => 替换` 清单，返回 {原文: 替换}

    用 utf-8-sig 读，否则 Windows 记事本/PowerShell 写出的 BOM 会粘在第一条
    凭据前面，导致永远匹配不上。
    """
    secrets = {}
    with open(path, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if "=>" not in line:
                continue
            plain, repl = line.split("=>", 1)
            plain = plain.strip()
            if plain:
                secrets[plain] = repl.strip() or "<已移除>"
    return secrets


def walk_text_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if os.path.splitext(name)[1].lower() in EXTS or name.endswith(".env"):
                yield os.path.join(dirpath, name)


def main():
    argv = sys.argv[1:]
    if not argv:
        print(__doc__)
        return 2
    if "--secrets" in argv:
        i = argv.index("--secrets")
        secrets_path = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    else:
        secrets_path = os.environ.get("SANITIZE_SECRETS_FILE") or ".sanitize_secrets"

    root = os.path.abspath(argv[0])
    if not os.path.isdir(root):
        print("目录不存在: %s" % root)
        return 1
    if not os.path.isfile(secrets_path):
        print("找不到密钥清单: %s" % os.path.abspath(secrets_path))
        print("先创建一个，每行写 `原文 => 替换为`。该文件不要提交进仓库。")
        return 2

    secrets = load_secrets(secrets_path)
    if not secrets:
        print("密钥清单是空的: %s" % os.path.abspath(secrets_path))
        return 2

    hits = []
    for p in walk_text_files(root):
        if os.path.abspath(p) == os.path.abspath(secrets_path):
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                text = f.read()
        except (UnicodeDecodeError, OSError):
            continue
        original = text
        for plain, repl in secrets.items():
            if plain in text:
                hits.append((os.path.relpath(p, root), len(plain), text.count(plain)))
                text = text.replace(plain, repl)
        if text != original:
            if not text.lstrip().startswith(">"):
                text = DEFAULT_WARNING + text
            with open(p, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)

    print("脱敏命中：")
    for rel, n, count in hits:
        print("  %s  长度%d 的凭据 x%d" % (rel, n, count))
    if not hits:
        print("  （无命中，可能已处理过）")

    leftovers = []
    for p in walk_text_files(root):
        if os.path.abspath(p) == os.path.abspath(secrets_path):
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                t = f.read()
        except (UnicodeDecodeError, OSError):
            continue
        if any(plain in t for plain in secrets):
            leftovers.append(os.path.relpath(p, root))

    print("\n复扫残留：%s" % (leftovers if leftovers else "无 ✓"))
    return 1 if leftovers else 0


if __name__ == "__main__":
    sys.exit(main())
