# API sources

## 族語 E 樂園（Klokah）

Base:

```text
https://web.klokah.tw/api/multiSearchResult.php
```

| Param | Required | Notes |
| --- | --- | --- |
| `d` | yes | Dialect id |
| `txt` | yes | Search string (Amis or Chinese word) |
| `type` | no | Default `all`. Prefer `vo` (千詞表) or `co` (生活會話) |
| `f` | no | `yes` fuzzy / `no` exact-ish |
| `l` | no | `yes` single-token mode |

### Amis dialect ids

| Id | Dialect |
| --- | --- |
| 1 | 南勢阿美語 |
| 2 | 秀姑巒阿美語 |
| 3 | 海岸阿美語（default） |
| 4 | 馬蘭阿美語 |
| 5 | 恆春阿美語 |

Full dialect table (16 族 / 42 語別): https://web.klokah.tw/api/

### Useful `type` values

| Code | Resource |
| --- | --- |
| `vo` | 千詞表 vocabulary |
| `co` | 生活會話 conversation |
| `sp` | 句型篇 |
| `all` | 全部 |

### Response shape (XML)

Vocabulary (`type=vo`) items typically include:

- `text` — Amis form
- `chinese` — gloss
- `class` — category like `04親屬稱謂`
- `order` — catalog order
- `url` — detail page

Conversation (`type=co`) items may include:

- `text`, `chinese`, `lessonId`, `type` (`word` / `sentence`), `order`, `url`

### Script helper

```bash
python3 .cursor/skills/amis-lesson-dialogue/scripts/fetch-vocab.py \
  --dialect 3 \
  --theme 親屬稱謂 \
  --limit 8 \
  --format json
```

Auto theme:

```bash
python3 .cursor/skills/amis-lesson-dialogue/scripts/fetch-vocab.py \
  --dialect 3 \
  --auto \
  --limit 8 \
  --format json
```

## 阿美語萌典

Public lookup pages (human + link-out):

```text
https://new-amis.moedict.tw/terms/{word}
https://amis.moedict.tw/
```

Notes:

- Prefer Klokah 千詞表 as the **canonical lesson word list**.
- Use Moedict for richer gloss / stem / cross-dictionary checks and learner links.
- License is mostly CC BY-NC / CC BY-NC-SA — keep attribution in `sources[]` and avoid commercial redistribution of dictionary text dumps.

## Reliability rules

1. Never invent target vocabulary. Every `targetWords` entry must come from a successful API hit or an explicit manual teacher override in `sources` with `provider: "manual"`.
2. Keep one dialect per lesson (`meta.dialectId` fixed).
3. Prefer exact orthography from API (`’` curly apostrophe may appear; normalize carefully but display API form in lesson).
4. Cache network results for the current generation run; do not hammer the API in loops without sleep.
