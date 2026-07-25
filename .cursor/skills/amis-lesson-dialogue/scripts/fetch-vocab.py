#!/usr/bin/env python3
"""Fetch / assemble a verified Amis vocabulary pack from 族語E樂園.

Examples:
  python3 fetch-vocab.py --theme 親屬稱謂 --limit 8
  python3 fetch-vocab.py --auto --dialect 3 --limit 8
  python3 fetch-vocab.py --words mama,ina,kaka --dialect 3
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

KLOKAH_API = "https://web.klokah.tw/api/multiSearchResult.php"
MOEDICT_TERM = "https://new-amis.moedict.tw/terms/{word}"

DIALECTS = {
    1: "南勢阿美語",
    2: "秀姑巒阿美語",
    3: "海岸阿美語",
    4: "馬蘭阿美語",
    5: "恆春阿美語",
}

# Seed lemmas previously verified against Klokah 千詞表 (coastal Amis d=3).
# The script still re-validates every word at runtime.
THEME_SEEDS: dict[str, dict[str, Any]] = {
    "親屬稱謂": {
        "class_prefix": "04",
        "seeds": ["mama", "ina", "kaka", "faki", "fai", "ama"],
    },
    "人物身分": {
        "class_prefix": "05",
        "seeds": ["widang", "kapah", "tamdaw", "fafahiyan", "fa'inayan", "mato'asay"],
    },
    "數字計量": {
        "class_prefix": "01",
        "seeds": ["cecay", "tosa", "tolo", "sepat", "lima"],
    },
    "飲食": {
        "class_prefix": None,
        "seeds": ["komaen", "nanom", "hemay", "titi", "pawli", "foting", "losay", "kaysing"],
    },
    "家與建築": {
        "class_prefix": "12",
        "seeds": ["loma'", "pitilidan"],
    },
    "代名詞": {
        "class_prefix": "02",
        "seeds": ["kiso", "mako"],
    },
}


def normalize_form(text: str | None) -> str:
    if not text:
        return ""
    return text.strip().replace("’", "'").replace("‘", "'").lower()


def klokah_search(
    dialect: int,
    text: str,
    search_type: str = "vo",
    fuzzy: bool = True,
    timeout: float = 20.0,
) -> list[dict[str, Any]]:
    params = {
        "d": str(dialect),
        "txt": text,
        "type": search_type,
        "f": "yes" if fuzzy else "no",
    }
    url = f"{KLOKAH_API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "amis-lesson-dialogue/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = resp.read()
    root = ET.fromstring(payload)
    items: list[dict[str, Any]] = []
    for item in root.findall(".//item"):
        word = (item.findtext("text") or "").strip()
        if not word:
            continue
        items.append(
            {
                "word": word,
                "zh": (item.findtext("chinese") or "").strip(),
                "class": (item.findtext("class") or "").strip(),
                "order": (item.findtext("order") or "").strip(),
                "url": (item.findtext("url") or "").strip(),
                "itemType": (item.findtext("type") or "").strip() or None,
                "lessonId": (item.findtext("lessonId") or "").strip() or None,
                "provider": "klokah",
            }
        )
    return items


def pick_best_item(
    query: str,
    items: list[dict[str, Any]],
    class_prefix: str | None = None,
) -> dict[str, Any] | None:
    if not items:
        return None
    q = normalize_form(query)

    def score(item: dict[str, Any]) -> tuple[int, int]:
        form = normalize_form(item.get("word"))
        exact = 0 if form == q else 1
        class_ok = 0
        if class_prefix:
            class_ok = 0 if (item.get("class") or "").startswith(class_prefix) else 1
        return (exact, class_ok)

    ranked = sorted(items, key=score)
    best = ranked[0]
    if class_prefix and not (best.get("class") or "").startswith(class_prefix):
        # Keep best exact form even if class filter misses; caller may still use it.
        exact = next((i for i in ranked if normalize_form(i.get("word")) == q), None)
        return exact or best
    return best


def enrich(item: dict[str, Any]) -> dict[str, Any]:
    word = item["word"]
    link_word = normalize_form(word).replace(" ", "")
    out = dict(item)
    out["moedictUrl"] = MOEDICT_TERM.format(word=urllib.parse.quote(link_word))
    return out


def collect_from_seeds(
    dialect: int,
    seeds: list[str],
    class_prefix: str | None,
    limit: int,
    sleep_s: float,
) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for seed in seeds:
        try:
            items = klokah_search(dialect, seed, search_type="vo", fuzzy=True)
        except (urllib.error.URLError, TimeoutError, ET.ParseError) as exc:
            print(f"[warn] search failed for {seed!r}: {exc}", file=sys.stderr)
            time.sleep(sleep_s)
            continue
        best = pick_best_item(seed, items, class_prefix=class_prefix)
        if best:
            key = normalize_form(best["word"])
            if key not in seen:
                seen.add(key)
                found.append(enrich(best))
        if len(found) >= limit:
            break
        time.sleep(sleep_s)
    return found


def fetch_conversation_hints(
    dialect: int,
    words: list[str],
    sleep_s: float,
    per_word: int = 2,
) -> list[dict[str, Any]]:
    hints: list[dict[str, Any]] = []
    for word in words:
        try:
            items = klokah_search(dialect, word, search_type="co", fuzzy=True)
        except (urllib.error.URLError, TimeoutError, ET.ParseError) as exc:
            print(f"[warn] conversation search failed for {word!r}: {exc}", file=sys.stderr)
            time.sleep(sleep_s)
            continue
        sentences = [i for i in items if (i.get("itemType") or "") == "sentence"]
        for item in sentences[:per_word]:
            hints.append(enrich(item))
        time.sleep(sleep_s)
    return hints


def build_pack(
    dialect: int,
    theme: str,
    words: list[dict[str, Any]],
    conversation_hints: list[dict[str, Any]] | None = None,
    mode: str = "theme",
) -> dict[str, Any]:
    return {
        "dialectId": dialect,
        "dialect": DIALECTS.get(dialect, f"dialect:{dialect}"),
        "theme": theme,
        "mode": mode,
        "count": len(words),
        "words": words,
        "conversationHints": conversation_hints or [],
        "moedictHome": "https://new-amis.moedict.tw/",
        "klokahApi": KLOKAH_API,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dialect", type=int, default=3, choices=sorted(DIALECTS))
    parser.add_argument("--theme", type=str, default=None, help="Theme key from built-in catalog")
    parser.add_argument("--auto", action="store_true", help="Randomly pick a theme")
    parser.add_argument("--words", type=str, default=None, help="Comma-separated Amis lemmas")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--sleep", type=float, default=0.15, help="Delay between API calls")
    parser.add_argument("--with-conversation", action="store_true", help="Also fetch co hints")
    parser.add_argument("--list-themes", action="store_true")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    parser.add_argument("--seed", type=int, default=None, help="RNG seed for --auto")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.list_themes:
        for name, meta in THEME_SEEDS.items():
            print(f"{name}\tseeds={len(meta['seeds'])}\tclass_prefix={meta['class_prefix']}")
        return 0

    if args.seed is not None:
        random.seed(args.seed)

    mode = "theme"
    theme = args.theme
    class_prefix = None
    seeds: list[str] = []

    if args.words:
        mode = "words"
        theme = theme or "自選單字"
        seeds = [w.strip() for w in args.words.split(",") if w.strip()]
    elif args.auto or not theme:
        mode = "auto"
        theme = random.choice(list(THEME_SEEDS))
        class_prefix = THEME_SEEDS[theme]["class_prefix"]
        seeds = list(THEME_SEEDS[theme]["seeds"])
        random.shuffle(seeds)
    else:
        if theme not in THEME_SEEDS:
            print(
                f"Unknown theme {theme!r}. Use --list-themes or --words.",
                file=sys.stderr,
            )
            return 2
        class_prefix = THEME_SEEDS[theme]["class_prefix"]
        seeds = list(THEME_SEEDS[theme]["seeds"])

    words = collect_from_seeds(
        dialect=args.dialect,
        seeds=seeds,
        class_prefix=class_prefix,
        limit=args.limit,
        sleep_s=args.sleep,
    )
    if not words:
        print("No verified vocabulary found.", file=sys.stderr)
        return 1

    hints: list[dict[str, Any]] = []
    if args.with_conversation:
        hints = fetch_conversation_hints(
            dialect=args.dialect,
            words=[w["word"] for w in words],
            sleep_s=args.sleep,
        )

    pack = build_pack(
        dialect=args.dialect,
        theme=theme,
        words=words,
        conversation_hints=hints,
        mode=mode,
    )

    if args.format == "text":
        print(f"#{pack['dialect']} / {pack['theme']} ({pack['count']})")
        for item in pack["words"]:
            print(f"- {item['word']}\t{item['zh']}\t{item.get('class','')}\t{item['url']}")
        return 0

    json.dump(pack, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
