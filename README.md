# Payo

阿美語／族語教學相關工具。

## 網頁版（給 my.kapah.tw 用工直）

路徑：`tools/amis-lesson/index.html`

功能：

1. 主題選詞或自動抽題  
2. 呼叫族語 E 樂園 API 驗證單字  
3. 用 Gemini 生成對話課  
4. 直接在網頁播放／練習，並下載 JSON  

本機預覽：

```bash
python3 -m http.server 8080
# 開啟 http://127.0.0.1:8080/tools/amis-lesson/
```

接到 Kapah：

1. 複製 `deploy/kapah_amis_lesson.html` → Django `templates/tools/amis_lesson.html`
2. 加路由 `tools/amis-lesson/`（需登入）
3. 詳見 `deploy/README.md`

## Cursor Skill（開發輔助，非必要）

路徑：`.cursor/skills/amis-lesson-dialogue/`

在 Cursor Agent 可執行 `/amis-lesson-dialogue` 產同一套 lesson JSON。  
正式給老師／學員使用，請走上面的網頁版。

```bash
python3 .cursor/skills/amis-lesson-dialogue/scripts/fetch-vocab.py --list-themes
python3 .cursor/skills/amis-lesson-dialogue/scripts/validate-lesson.py \
  .cursor/skills/amis-lesson-dialogue/assets/lesson.example.json
```
