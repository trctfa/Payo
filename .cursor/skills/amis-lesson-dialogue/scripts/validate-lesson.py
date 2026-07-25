#!/usr/bin/env python3
"""Validate a lesson JSON against assets/lesson.schema.json and grounded-vocab rules.

Examples:
  python3 validate-lesson.py path/to/lesson.json
  python3 validate-lesson.py lesson.json --vocab-pack vocab.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
DEFAULT_SCHEMA = SKILL_DIR / "assets" / "lesson.schema.json"


def normalize_form(text: str | None) -> str:
    if not text:
        return ""
    return text.strip().replace("’", "'").replace("‘", "'").lower()


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def basic_schema_check(lesson: dict[str, Any]) -> list[str]:
    """Lightweight required-field checks (no external jsonschema dependency)."""
    errors: list[str] = []
    required_top = ["meta", "warmup", "dialogue", "pattern", "practice", "sources"]
    for key in required_top:
        if key not in lesson:
            errors.append(f"missing top-level key: {key}")

    meta = lesson.get("meta")
    if not isinstance(meta, dict):
        errors.append("meta must be an object")
        return errors

    for key in [
        "id",
        "dialectId",
        "dialect",
        "theme",
        "level",
        "targetWords",
        "createdAt",
        "source",
    ]:
        if key not in meta:
            errors.append(f"meta missing: {key}")

    if meta.get("source") != "amis-lesson-dialogue":
        errors.append('meta.source must be "amis-lesson-dialogue"')

    level = meta.get("level")
    if level not in {None, "初級", "中級", "中高級", "高級"}:
        errors.append(f"invalid meta.level: {level!r}")

    target = meta.get("targetWords")
    if not isinstance(target, list) or len(target) < 3:
        errors.append("meta.targetWords must be a list with >= 3 items")

    dialogue = lesson.get("dialogue")
    if not isinstance(dialogue, list) or len(dialogue) < 4:
        errors.append("dialogue must be a list with >= 4 turns")
    else:
        for i, turn in enumerate(dialogue):
            if not isinstance(turn, dict):
                errors.append(f"dialogue[{i}] must be object")
                continue
            for key in ("speaker", "amis", "zh"):
                if not turn.get(key):
                    errors.append(f"dialogue[{i}] missing {key}")

    practice = lesson.get("practice")
    if not isinstance(practice, list) or len(practice) < 2:
        errors.append("practice must be a list with >= 2 items")
    else:
        allowed = {"fill", "match", "reorder", "speak"}
        for i, item in enumerate(practice):
            if not isinstance(item, dict):
                errors.append(f"practice[{i}] must be object")
                continue
            if item.get("type") not in allowed:
                errors.append(f"practice[{i}].type invalid: {item.get('type')!r}")
            if not item.get("prompt"):
                errors.append(f"practice[{i}] missing prompt")

    sources = lesson.get("sources")
    if not isinstance(sources, list) or not sources:
        errors.append("sources must be a non-empty list")
    else:
        for i, src in enumerate(sources):
            if not isinstance(src, dict):
                errors.append(f"sources[{i}] must be object")
                continue
            for key in ("word", "zh", "url", "provider"):
                if not src.get(key):
                    errors.append(f"sources[{i}] missing {key}")
            if src.get("provider") not in {None, "klokah", "amis-moedict", "manual"}:
                errors.append(f"sources[{i}].provider invalid: {src.get('provider')!r}")

    return errors


def grounded_vocab_check(
    lesson: dict[str, Any],
    vocab_pack: dict[str, Any] | None,
) -> list[str]:
    errors: list[str] = []
    meta = lesson.get("meta") or {}
    targets = meta.get("targetWords") or []
    sources = lesson.get("sources") or []

    source_words = {
        normalize_form(s.get("word"))
        for s in sources
        if isinstance(s, dict) and s.get("word")
    }
    for word in targets:
        if normalize_form(word) not in source_words:
            errors.append(f"target word lacks sources[] entry: {word!r}")

    if vocab_pack:
        pack_words = {
            normalize_form(w.get("word"))
            for w in vocab_pack.get("words") or []
            if isinstance(w, dict)
        }
        for word in targets:
            nw = normalize_form(word)
            src = next(
                (
                    s
                    for s in sources
                    if isinstance(s, dict) and normalize_form(s.get("word")) == nw
                ),
                None,
            )
            if src and src.get("provider") == "manual":
                continue
            if nw not in pack_words:
                errors.append(
                    f"target word not in vocab pack and not manual: {word!r}"
                )

        pack_dialect = vocab_pack.get("dialectId")
        if pack_dialect is not None and meta.get("dialectId") != pack_dialect:
            errors.append(
                f"meta.dialectId {meta.get('dialectId')!r} != vocab pack {pack_dialect!r}"
            )

    return errors


def try_jsonschema(lesson: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    try:
        import jsonschema  # type: ignore
    except ImportError:
        return []
    validator = jsonschema.Draft202012Validator(schema)
    return [
        f"schema: {e.message} at {'/'.join(str(p) for p in e.path) or '<root>'}"
        for e in sorted(validator.iter_errors(lesson), key=lambda e: list(e.path))
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lesson", type=Path, help="Path to lesson JSON")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument(
        "--vocab-pack",
        type=Path,
        default=None,
        help="Optional vocab pack from fetch-vocab.py for grounding checks",
    )
    parser.add_argument(
        "--strict-schema",
        action="store_true",
        help="Fail if jsonschema package is missing",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.lesson.exists():
        print(f"Lesson not found: {args.lesson}", file=sys.stderr)
        return 2
    if not args.schema.exists():
        print(f"Schema not found: {args.schema}", file=sys.stderr)
        return 2

    lesson = load_json(args.lesson)
    schema = load_json(args.schema)
    vocab_pack = load_json(args.vocab_pack) if args.vocab_pack else None

    if not isinstance(lesson, dict):
        print("Lesson JSON must be an object", file=sys.stderr)
        return 1

    errors = basic_schema_check(lesson)
    errors.extend(grounded_vocab_check(lesson, vocab_pack))

    schema_errors = try_jsonschema(lesson, schema)
    if schema_errors:
        errors.extend(schema_errors)
    elif args.strict_schema:
        try:
            import jsonschema  # noqa: F401
        except ImportError:
            errors.append("jsonschema package not installed (required by --strict-schema)")

    if errors:
        print(f"INVALID: {args.lesson} ({len(errors)} issue(s))")
        for err in errors:
            print(f"- {err}")
        return 1

    print(f"OK: {args.lesson}")
    meta = lesson.get("meta", {})
    print(
        f"theme={meta.get('theme')} dialect={meta.get('dialect')} "
        f"words={len(meta.get('targetWords') or [])} "
        f"turns={len(lesson.get('dialogue') or [])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
