---
name: amis-lesson-dialogue
description: >
  Build a web-ready Amis (阿美語) dialogue lesson: fetch verified vocabulary from
  族語E樂園 / link 阿美語萌典, generate structured bilingual teaching dialogue,
  validate JSON for my.kapah.tw tools. Use when the user asks to create, regenerate,
  or revise a 族語教學對話課 / lesson transcript / 工直課程 JSON.
disable-model-invocation: true
---

# Amis lesson dialogue

Generate one grounded, schema-valid Amis dialogue lesson for web tools (工直).

## When to use

- User asks for a 族語對話課 / 今日主題單字課 / lesson JSON
- User wants theme pick (manual or auto) then AI dialogue transcript
- Output must be consumable by `my.kapah.tw/tools` without extra parsing

## Inputs to clarify (ask only if missing)

1. Dialect (default: 海岸阿美語 `d=3`)
2. Theme mode: named theme / auto / explicit word list
3. Level: 初級 (default) / 中級 / ...
4. Output path (default: `lessons/amis/<id>.json`)

## Workflow

### 1) Build a verified vocabulary pack

Prefer the helper script (network required):

```bash
# list themes
python3 .cursor/skills/amis-lesson-dialogue/scripts/fetch-vocab.py --list-themes

# manual theme
python3 .cursor/skills/amis-lesson-dialogue/scripts/fetch-vocab.py \
  --dialect 3 --theme 親屬稱謂 --limit 8 --with-conversation --format json \
  > /tmp/vocab-pack.json

# computer-picked theme
python3 .cursor/skills/amis-lesson-dialogue/scripts/fetch-vocab.py \
  --dialect 3 --auto --limit 8 --with-conversation --format json \
  > /tmp/vocab-pack.json

# explicit lemmas
python3 .cursor/skills/amis-lesson-dialogue/scripts/fetch-vocab.py \
  --dialect 3 --words mama,ina,kaka --format json > /tmp/vocab-pack.json
```

Read `references/api-sources.md` for API details.

**Hard rule:** every target lemma must appear in the vocab pack (or be explicitly marked `provider: "manual"` by a human teacher override).

### 2) Generate the lesson JSON

Follow `references/dialogue-rules.md`.

Shape output exactly like `assets/lesson.example.json` and `assets/lesson.schema.json`.

Minimum content:

- `meta` with dialect, theme, level, `targetWords`, `source: "amis-lesson-dialogue"`
- `warmup` for target words
- `dialogue` ≥ 4 bilingual turns with `highlight` + `needsReview` when AI-composed
- `pattern` 1–3 frames
- `practice` ≥ 2 items
- `sources` provenance rows (klokah URLs + optional moedict links)

Use conversation hints from the vocab pack when present; still mark AI-adapted lines `needsReview: true`.

### 3) Validate

```bash
python3 .cursor/skills/amis-lesson-dialogue/scripts/validate-lesson.py \
  path/to/lesson.json --vocab-pack /tmp/vocab-pack.json
```

Do not present the lesson as final if validation fails.

### 4) Save + summarize

1. Write JSON to the agreed path (create directories as needed)
2. Summarize for the user:
   - theme / dialect / target words
   - output path
   - how many turns / practice items
   - which lines need human review (`needsReview: true`)

## Do not

- Invent Amis lemmas not returned by API / vocab pack
- Mix multiple Amis dialects in one lesson
- Dump raw dictionary articles into the lesson (license + UX)
- Skip validation
- Put secrets in the skill files

## Optional next steps (only if user asks)

- Scaffold a `my.kapah.tw/tools` page that renders this JSON
- Expand theme seeds beyond the built-in catalog
- Add TTS / audio URLs later via separate tooling
