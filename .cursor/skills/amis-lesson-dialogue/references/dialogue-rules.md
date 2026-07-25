# Dialogue generation rules

## Goal

Produce one web-ready Amis (or later: other indigenous language) dialogue lesson JSON that a tools page can render without extra parsing.

## Hard constraints

1. **Grounded vocabulary only**  
   Target words must come from the vocab pack returned by `fetch-vocab.py` (or an equivalent verified source list). Do not invent Amis lemmas.

2. **One dialect**  
   All forms should match `meta.dialectId`. Do not mix 南勢 / 海岸 / 馬蘭 etc. in one lesson.

3. **Bilingual lines**  
   Every dialogue turn needs both `amis` and `zh`.

4. **Mark uncertainty**  
   If a sentence is AI-composed and not copied from Klokah conversation (`type=co`), set `needsReview: true`.

5. **Highlight target words**  
   Put today’s target lemmas in `highlight` whenever they appear.

6. **Schema compliance**  
   Output must validate against `assets/lesson.schema.json`.

## Pedagogy defaults

| Level | Dialogue turns | Target words | Practice items |
| --- | --- | --- | --- |
| 初級 | 6–10 | 5–8 | 3–5 |
| 中級 | 8–12 | 8–12 | 4–6 |

Lesson sections:

1. `warmup` — show each target word with gloss (+ optional note)
2. `dialogue` — short scene using those words
3. `pattern` — 1–3 reusable frames with slots
4. `practice` — mix of `match` / `fill` / `reorder` (optional `speak`)
5. `sources` — provenance for each target word

## Prompt skeleton (for the generating model)

Use this after the vocab pack is ready:

```text
你是阿美語教學助教。請用下列「已驗證詞彙包」產生一課對話教學 JSON。
規則：
- 只把詞彙包內的詞當必學目標詞
- 不可發明未驗證的族語單詞
- 全程使用指定方言
- 每句提供 amis + zh
- 不確定的句子 needsReview=true
- 嚴格符合提供的 JSON schema
輸入：
- dialect / dialectId
- theme / level
- vocabPack JSON
輸出：單一 JSON 物件，不要 markdown。
```

## Quality checklist before saving

- [ ] `meta.targetWords` ⊆ vocab pack words
- [ ] every target word has a `sources[]` row
- [ ] dialogue length fits level
- [ ] at least 2 practice items
- [ ] `validate-lesson.py` exits 0
- [ ] uncertain lines flagged `needsReview`
