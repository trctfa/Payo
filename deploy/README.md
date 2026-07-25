# 整合到 https://my.kapah.tw/tools/

Kapah 站是 **Django + 會員登入**（未登入會導向 `/login/?next=...`）。
本資料夾提供可直接貼進 Django 的頁面範本。

## 族語對話課（工直）

目標網址建議：

```text
https://my.kapah.tw/tools/amis-lesson/
```

| 檔案 | 用途 |
| --- | --- |
| `kapah_amis_lesson.html` | 完整 Django 頁面範本（含標題＋工具） |
| `amis_lesson_widget.html` | 只有工具本體（嵌進既有 layout） |

對應的獨立預覽檔：`../tools/amis-lesson/index.html`

### 接法 A（推薦）：獨立 tools 頁

1. 把 `kapah_amis_lesson.html` 複製到 Django templates，例如：
   `templates/tools/amis_lesson.html`
2. 在 `urls.py` 加：

```python
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def amis_lesson_tool(request):
    return render(request, "tools/amis_lesson.html")

# urls.py
path("tools/amis-lesson/", amis_lesson_tool, name="amis_lesson"),
```

3. 部署後開啟 https://my.kapah.tw/tools/amis-lesson/（需登入）

### 接法 B：嵌進既有 base layout

若 tools 頁已有 `{% extends "base.html" %}`：

1. 在 content 區塊貼上 `amis_lesson_widget.html` 整段
2. 不要再包一層完整 `<html>`

### 網頁功能

1. 選方言／主題（或自動選題／自訂單字）
2. 從族語 E 樂園抓已驗證詞彙
3. 用 Gemini 生成對話課 JSON 並直接在頁面播放
4. 可下載／複製／開啟既有 lesson JSON（不一定要填 API 金鑰）

### 注意

- 前端會跨網域呼叫：
  - `web.klokah.tw`（CORS `*`，可直打）
  - `generativelanguage.googleapis.com`（使用者自備 Gemini 金鑰）
  - 萌典連結為外開查詢
- Gemini 金鑰只存在使用者瀏覽器 `localStorage`，不會進你的 Django 伺服器
- 若 Kapah 的 CSP 擋外連，需放行上述網域

## 族語隨身譯（既有）

見 PR／分支中的 `kapah_zyfy.html`、`zyfy_widget.html`（路徑：`/tools/zyfy/`）。

## 需要直接改 Kapah 專案？

把 Kapah 的 GitHub repo 加進這個 agent（或提供網址＋權限），就可以直接開 PR 接到 `/tools/amis-lesson/`，不必手動複製範本。
