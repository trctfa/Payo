# 整合到 https://my.kapah.tw/tools/zyfy/

你的 Kapah 站是 **Django + 會員登入**（未登入會導向 `/login/?next=/tools/zyfy/`）。
本資料夾提供可直接貼進 Django 的頁面範本。

## 檔案

| 檔案 | 用途 |
|---|---|
| `kapah_zyfy.html` | 完整 Django 頁面範本（含站內標題＋小工具） |
| `zyfy_widget.html` | 只有小工具本體（若你要嵌進既有 layout） |

## 接法 A（推薦）：獨立 tools 頁

1. 把 `kapah_zyfy.html` 複製到你的 Django templates，例如：
   `templates/tools/zyfy.html`
2. 在 `urls.py` 加（或確認已有）：

```python
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def zyfy_tool(request):
    return render(request, "tools/zyfy.html")

# urls.py
path("tools/zyfy/", zyfy_tool, name="zyfy"),
```

3. 部署後開 https://my.kapah.tw/tools/zyfy/ （需登入）即可使用。

## 接法 B：嵌進既有 base layout

若你的 tools 頁已有 `{% extends "base.html" %}`：

1. 在 content 區塊貼上 `zyfy_widget.html` **整段內容**（從 `<!-- ===` 註解到最後的 `</script>`）。
2. 不要再包一層完整的 `<html>`。

## 注意

- 小工具會跨網域呼叫：
  - `ai-labs.ilrdf.org.tw`（翻譯／語音）
  - `web.klokah.tw`（字典）
  兩者都允許 CORS，前端可直接打，**不必**在 Django 再寫代理。
- 你的站有 `X-Frame-Options: DENY`，這不影響把小工具「貼進頁面」；只是別人不能用 iframe 嵌你的 Kapah 頁。
- 若之後更新功能，只要再覆蓋一次 `embed.html`／`kapah_zyfy.html` 即可。

## 需要我直接改 Kapah 專案？

把 Kapah 的 GitHub repo 網址（或把這個 agent 加進該 repo）給我，我可以直接開 PR 接到 `/tools/zyfy/`。
