# 族語隨身譯

把中文一鍵翻譯成 16 族原住民族語，並用 AI 語音合成朗讀、下載音檔。
翻譯與語音合成服務由[原住民族語言研究發展基金會 AI 實驗室](https://ai-labs.ilrdf.org.tw/)提供，本專案僅作介面串接。

## 內容

| 檔案 | 說明 |
|---|---|
| `index.html` | Landing page（單一 HTML 檔，零依賴），可直接部署到任何靜態網站空間 |
| `embed.html` | 嵌入版小工具：貼進現有網頁的「自訂 HTML」區塊即可，樣式只作用在小工具內部，不影響原網站版面 |
| `tools/ilrdf_tts.py` | 命令列批次工具：`python3 ilrdf_tts.py --ethnicity 太魯閣 --file sentences.txt` |
| `tools/ilrdf_tts_gui.py` | 桌面 GUI 版（tkinter，Python 內建），適合批次做教材音檔 |

## 功能（網頁版與 GUI 版一致）

- 貼上多行中文（一行一句）→ 一鍵翻譯全部 → 進入編輯區
- 編輯區每句「上排中文、下排翻譯」都可直接修改
- 每句 SVG 圖示按鈕：↻ 單句重翻、▶ 單句試聽、⭳ 單句下載音檔、勾選框
- 匯出全部／匯出勾選：逐句 WAV（檔名＝翻譯）＋「一行中文、一行翻譯」對照文字檔
- 串接全部句子成一個語音檔（句間 0.4 秒停頓，純前端合併 WAV）
- 語音快取：唸過／下載過的句子不重新合成
- 預設選擇：阿美／阿美_南勢／阿美_南勢_女聲

命令列版：跑完自動產生 `翻譯對照.txt`；加 `--text-only` 可只翻譯、跳過語音合成。
文字檔以 UTF-8（含 BOM）儲存，Windows 記事本可直接開啟。

註：`index.html` 的工具區塊與 `embed.html` 是同一份小工具程式，更新其中一份時請同步另一份。

## 部署 Landing Page

兩個檔案都沒有後端與相依套件，依你的網站後台選一種方式：

- **後台可上傳檔案／建立獨立頁面**：把 `index.html` 上傳到你的網站空間（可改名，例如 `translate.html`）。
- **後台只能在現有頁面貼 HTML**（WordPress 自訂 HTML 區塊等）：改貼 `embed.html` 的完整內容。`index.html` 含完整網頁結構與全域樣式，貼進現有頁面會弄亂原版面；`embed.html` 的樣式全部限定在小工具內部。
- **GitHub Pages**：本 repo 開啟 Pages（Settings → Pages → Deploy from branch），即可獲得公開網址。
- **Netlify / Cloudflare Pages**：把檔案拖進去即可。

注意：頁面必須透過 `http(s)://` 開啟（本機直接雙擊 `file://` 開啟時，跨網域請求會被瀏覽器擋掉）。

## 技術說明

兩個來源網站都是 Gradio 5 應用，後端 API 允許跨網域（CORS）呼叫：

- 翻譯：`kari-seejiq-tnpusu-ai-hmjil` 的 `lambda_1`（依族別取得語別）與 `translate_1`
- 合成：`hnang-kari-ai-asi-sluhay` 的 `lambda`（依族別取得配音員）與 `default_speaker_tts`

兩個重要細節：

1. **呼叫順序**：需先 POST `queue/join`，再開 `queue/data` 的 SSE 連線等結果；順序顛倒伺服器會直接關閉連線。
2. **Session 解鎖**：翻譯前必須用同一個 `session_hash` 先呼叫 `lambda_1(族別)`，否則伺服器的下拉選單驗證只認預設（阿美）的語別代碼。

請以正常教學用途的流量使用，尊重基金會的服務條款。
