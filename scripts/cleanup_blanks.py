import re
import sys
from pathlib import Path


def cleanup_python(src: str) -> str:
    src = "\n".join(line.rstrip() for line in src.split("\n"))
    src = re.sub(r"(?:[ \t]*\n){3,}", "\n\n", src)
    src = src.lstrip("\n")
    return src.rstrip() + "\n"


def cleanup_ts(src: str) -> str:
    src = "\n".join(line.rstrip() for line in src.split("\n"))
    src = re.sub(r"^\s*\{\s*\}\s*\n", "", src, flags=re.MULTILINE)
    src = re.sub(r"(?:[ \t]*\n){3,}", "\n\n", src)
    src = src.lstrip("\n")
    return src.rstrip() + "\n"


def cleanup_sql_or_css(src: str) -> str:
    src = "\n".join(line.rstrip() for line in src.split("\n"))
    src = re.sub(r"(?:[ \t]*\n){3,}", "\n\n", src)
    src = src.lstrip("\n")
    return src.rstrip() + "\n"


HANDLERS = {
    ".py": cleanup_python,
    ".ts": cleanup_ts,
    ".tsx": cleanup_ts,
    ".js": cleanup_ts,
    ".jsx": cleanup_ts,
    ".sql": cleanup_sql_or_css,
    ".css": cleanup_sql_or_css,
}


def main() -> None:
    for arg in sys.argv[1:]:
        path = Path(arg)
        if not path.exists():
            continue
        handler = HANDLERS.get(path.suffix)
        if not handler:
            continue
        src = path.read_text(encoding="utf-8")
        new = handler(src)
        if new != src:
            path.write_text(new, encoding="utf-8")
            print(f"cleaned: {path}")


if __name__ == "__main__":
    main()
