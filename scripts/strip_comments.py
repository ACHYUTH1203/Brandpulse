import io
import re
import sys
import tokenize
from pathlib import Path


def strip_python(src: str) -> str:
    out: list[str] = []
    last_lineno = 1
    last_col = 0
    prev_toktype = tokenize.ENCODING
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except (tokenize.TokenizeError, IndentationError):
        return src
    for toknum, tokval, (slineno, scol), (elineno, ecol), _ in tokens:
        if slineno > last_lineno:
            out.append("\n" * (slineno - last_lineno))
            last_col = 0
        if scol > last_col:
            out.append(" " * (scol - last_col))
        if toknum == tokenize.COMMENT:
            pass
        elif toknum == tokenize.STRING and prev_toktype in (
            tokenize.INDENT,
            tokenize.NEWLINE,
            tokenize.NL,
            tokenize.ENCODING,
        ):
            pass
        else:
            out.append(tokval)
        if toknum not in (tokenize.NL,):
            prev_toktype = toknum
        last_col = ecol
        last_lineno = elineno
    result = "".join(out)
    result = re.sub(r"\n{3,}", "\n\n", result)
    result = "\n".join(line.rstrip() for line in result.split("\n"))
    return result.rstrip() + "\n"


def strip_ts(src: str) -> str:
    out: list[str] = []
    i = 0
    n = len(src)
    in_string: str | None = None
    while i < n:
        c = src[i]
        if in_string is not None:
            if c == "\\" and i + 1 < n:
                out.append(c)
                out.append(src[i + 1])
                i += 2
                continue
            if c == in_string:
                in_string = None
            out.append(c)
            i += 1
            continue
        if c in "\"'`":
            in_string = c
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            while i < n and src[i] != "\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            i += 2
            while i + 1 < n and not (src[i] == "*" and src[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(c)
        i += 1
    result = "".join(out)
    result = "\n".join(line.rstrip() for line in result.split("\n"))
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.rstrip() + "\n"


def strip_sql(src: str) -> str:
    out_lines: list[str] = []
    for line in src.split("\n"):
        stripped = line.lstrip()
        if stripped.startswith("--"):
            continue
        idx = line.find("--")
        if idx > 0:
            line = line[:idx].rstrip()
        out_lines.append(line)
    result = "\n".join(out_lines)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.rstrip() + "\n"


def strip_css(src: str) -> str:
    result = re.sub(r"/\*[\s\S]*?\*/", "", src)
    result = "\n".join(line.rstrip() for line in result.split("\n"))
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.rstrip() + "\n"


HANDLERS = {
    ".py": strip_python,
    ".ts": strip_ts,
    ".tsx": strip_ts,
    ".js": strip_ts,
    ".jsx": strip_ts,
    ".sql": strip_sql,
    ".css": strip_css,
}


def main() -> None:
    for arg in sys.argv[1:]:
        path = Path(arg)
        if not path.exists():
            print(f"skip (missing): {path}")
            continue
        handler = HANDLERS.get(path.suffix)
        if not handler:
            print(f"skip (unknown ext): {path}")
            continue
        src = path.read_text(encoding="utf-8")
        new = handler(src)
        path.write_text(new, encoding="utf-8")
        print(f"cleaned: {path}")


if __name__ == "__main__":
    main()
