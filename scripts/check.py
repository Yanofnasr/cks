# SPDX-License-Identifier: MIT
"""Offline workbook checks; no dependency installation or cluster access."""
import html
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit


DRILL = r"(?:CS|CH|SH|MW|SC|RT|CAP)\d{2}"
LINK = re.compile(r"\[[^\]\n]*\]\(\s*(?:<([^>\n]+)>|([^\s()]+))(?:\s+(?:\"[^\"\n]*\"|'[^'\n]*'))?\s*\)")
PRIVATE = {"work", ".git", ".aws", ".kube"}


def markdown_files(root):
    paths = list(root.glob("*.md"))
    for directory in ("preparation", "labs", "solutions"):
        paths.extend((root / directory).rglob("*.md"))
    return sorted(p for p in paths if not any(part.startswith(".") for part in p.relative_to(root).parts))


def prose(text, label, errors):
    lines = []
    fence = None
    for number, line in enumerate(text.splitlines(), 1):
        if fence:
            if re.fullmatch(r" {0,3}" + re.escape(fence) + fence[0] + r"*[ \t]*", line):
                fence = None
            lines.append("")
        else:
            opening = re.match(r" {0,3}(`{3,}|~{3,})", line)
            if opening:
                fence = opening[1]
                opened_at = number
                lines.append("")
            else:
                lines.append(line)
    if fence:
        errors.append(f"{label}:{opened_at}: unclosed fence")
    return "\n".join(lines)


def anchors(text):
    used = set()
    for heading in re.findall(r"^ {0,3}#{1,6}[ \t]+(.+)$", text, re.MULTILINE):
        heading = re.sub(r"\s+#+\s*$", "", heading)
        heading = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", heading)
        heading = re.sub(r"<[^>]*>", "", html.unescape(heading))
        base = re.sub(r"[^\w\s-]", "", heading.lower()).strip()
        base = re.sub(r"\s", "-", base)
        slug, suffix = base, 0
        while slug in used:
            suffix += 1
            slug = f"{base}-{suffix}"
        used.add(slug)
    return used


def check(root):
    root = root.resolve()
    errors, texts, drills = [], {}, {}
    for path in markdown_files(root):
        label = path.relative_to(root)
        if not path.resolve().is_relative_to(root):
            errors.append(f"{label}: source points outside repository")
            continue
        try:
            texts[path] = prose(path.read_text(encoding="utf-8"), label, errors)
        except (OSError, UnicodeError) as error:
            errors.append(f"{label}: cannot read Markdown: {error}")

    # shortcut: checks inline links and ATX headings, extend if reference links or HTML anchors are adopted.
    for path, text in texts.items():
        for number, line in enumerate(text.splitlines(), 1):
            label = f"{path.relative_to(root)}:{number}"
            if path.parent == root / "labs":
                match = re.match(r"^#{1,2}\s+(" + DRILL + r")\b", line)
                if match:
                    identifier = match[1]
                    if identifier in drills:
                        errors.append(f"{label}: duplicate drill {identifier} (also {drills[identifier]})")
                    drills[identifier] = label
            line = re.sub(r"(`+).*?\1", "", line)
            for match in LINK.finditer(line):
                target = match[1] if match[1] is not None else match[2]
                try:
                    url = urlsplit(target)
                except ValueError:
                    errors.append(f"{label}: invalid link {target}")
                    continue
                if url.scheme in {"http", "https", "mailto"}:
                    continue
                if url.scheme or url.netloc:
                    errors.append(f"{label}: unsupported local link {target}")
                    continue
                link_path = Path(unquote(url.path))
                if link_path.is_absolute():
                    errors.append(f"{label}: absolute local link {target}")
                    continue
                destination = (path.parent / link_path).resolve() if url.path else path.resolve()
                if not destination.is_relative_to(root):
                    errors.append(f"{label}: link points outside repository: {target}")
                    continue
                relative = destination.relative_to(root)
                directory_parts = relative.parts if destination.is_dir() else relative.parts[:-1]
                hidden_directory = any(part.startswith(".") and part != ".github" for part in directory_parts)
                if (relative.parts and relative.parts[0] in PRIVATE) or hidden_directory:
                    errors.append(f"{label}: private local link target: {target}")
                    continue
                if not destination.exists():
                    errors.append(f"{label}: missing target: {target}")
                    continue
                if url.fragment:
                    if destination.suffix != ".md" or not destination.is_file():
                        errors.append(f"{label}: anchor target is not Markdown: {target}")
                    else:
                        try:
                            body = texts.get(destination)
                            if body is None:
                                body = prose(destination.read_text(encoding="utf-8"), relative, errors)
                            if unquote(url.fragment) not in anchors(body):
                                errors.append(f"{label}: missing anchor: {target}")
                        except (OSError, UnicodeError) as error:
                            errors.append(f"{label}: cannot read anchor target: {error}")

    study = texts.get(root / "preparation/STUDY-PATH.md")
    if study is None:
        errors.append("preparation/STUDY-PATH.md: missing study path")
    else:
        mapped = set(re.findall(r"\b" + DRILL + r"\b", study))
        for identifier in sorted(drills.keys() - mapped):
            errors.append(f"{drills[identifier]}: {identifier} missing from study path")
        for identifier in sorted(mapped - drills.keys()):
            errors.append(f"preparation/STUDY-PATH.md: unknown drill {identifier}")
    if not drills:
        errors.append("labs/: no drill IDs found")

    for path in sorted((root / "labs/fixtures").rglob("*")):
        if path.suffix not in {".json", ".jsonl"} or any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
        label = path.relative_to(root)
        if not path.resolve().is_relative_to(root):
            errors.append(f"{label}: fixture points outside repository")
            continue
        try:
            text = path.read_text(encoding="utf-8")
            records = text.splitlines() if path.suffix == ".jsonl" else [text]
            for number, record in enumerate(records, 1):
                try:
                    json.loads(record, parse_constant=reject_constant)
                except ValueError as error:
                    errors.append(f"{label}:{number}: invalid JSON: {error}")
        except (OSError, UnicodeError) as error:
            errors.append(f"{label}: cannot read fixture: {error}")
    return errors


def reject_constant(value):
    raise ValueError(f"non-JSON constant {value}")


def main(root):
    errors = check(root)
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        print(f"FAIL: {len(errors)} repository consistency error(s).")
    else:
        print("PASS: inline Markdown links/heading anchors, drill coverage and JSON fixtures.")
    print("Not checked: YAML schemas, external link availability, CEL or lab runtime behavior.")
    return int(bool(errors))


if __name__ == "__main__":
    sys.exit(main(Path(__file__).resolve().parents[1]))
