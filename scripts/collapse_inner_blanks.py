import sys
from pathlib import Path


def collapse(src: str) -> str:
    lines = src.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        stripped = line.rstrip()
        is_inside_body = line.startswith((" ", "\t")) and not stripped.endswith((":", "(", ","))
        is_block_opener = bool(stripped) and stripped.endswith(":")
        if is_inside_body or is_block_opener:
            j = i + 1
            blanks: list[str] = []
            while j < len(lines) and lines[j].strip() == "":
                blanks.append(lines[j])
                j += 1
            next_is_indented = j < len(lines) and lines[j].startswith((" ", "\t"))
            next_starts_def = (
                j < len(lines)
                and lines[j].lstrip().startswith(("def ", "async def ", "class "))
            )
            if is_inside_body and next_starts_def:
                out.extend(blanks)
                i = j
                continue
            if next_is_indented:
                i = j
                continue
            out.extend(blanks)
            i = j
            continue
        i += 1
    return "\n".join(out)


def main() -> None:
    for arg in sys.argv[1:]:
        path = Path(arg)
        if not path.exists() or path.suffix != ".py":
            continue
        src = path.read_text(encoding="utf-8")
        new = collapse(src)
        if new != src:
            path.write_text(new, encoding="utf-8")
            print(f"collapsed: {path}")


if __name__ == "__main__":
    main()
