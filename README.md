# Payo

阿美語／族語教學相關工具與 Cursor Agent Skills。

## Cursor Skill：`amis-lesson-dialogue`

路徑：`.cursor/skills/amis-lesson-dialogue/`

用途：依主題（或自動選題）從[族語 E 樂園](https://web.klokah.tw/api/)抓取已驗證詞彙，再產出可給 `my.kapah.tw/tools`（工直）使用的對話課 JSON。

在 Cursor Agent 中執行：

```text
/amis-lesson-dialogue
```

快速測試腳本：

```bash
python3 .cursor/skills/amis-lesson-dialogue/scripts/fetch-vocab.py --list-themes
python3 .cursor/skills/amis-lesson-dialogue/scripts/validate-lesson.py \
  .cursor/skills/amis-lesson-dialogue/assets/lesson.example.json
```
