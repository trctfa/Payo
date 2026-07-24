# 阿美語族語教室 — 廣播教學產生器

純前端工具：用 Gemini 產生阿美語廣播教學逐字稿，並串接：

- [阿美語萌典](https://new-amis.moedict.tw/)
- [族語 E 樂園 API](https://web.klokah.tw/api/)（`multiSearchResult.php`）

## 使用方式

1. 用瀏覽器開啟 `index.html`
2. 填入 Gemini API 金鑰
3. 選擇阿美語方言與資料來源（萌典／E 樂園）
4. 全自動或自訂主題後產生逐字稿

## 串接說明

E 樂園查詢端點：

```
https://web.klokah.tw/api/multiSearchResult.php?d={方言}&txt={關鍵字}&type={類型}&l=yes
```

阿美語方言編號：`1` 南勢、`2` 秀姑巒、`3` 海岸（預設）、`4` 馬蘭、`5` 恆春。
