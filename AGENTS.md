# Payo

## Cursor Cloud specific instructions

### What this repo is
Payo is a collection of self-contained, single-file static web apps. Each app lives on its
own branch as a single `index.html` (HTML + CSS + vanilla JS, no build step, no dependencies):

- `cursor/mobile-kline-web-*` — 「K 線與股價分析助手」 stock/K-line analysis tool.
- `cursor/audio-merger-web-*` — 「音檔合併工具」 in-browser audio merger.

The `master` branch currently contains only `README.md`; the application code is on the
feature branches above.

### Running / developing
There is nothing to install — no `package.json`, lockfile, or build system. Just serve the
`index.html` with any static file server and open it in a browser:

```bash
python3 -m http.server 8080   # run from the directory containing index.html
```

Then open `http://localhost:8080/`. Editing `index.html` and refreshing the browser is the
full dev loop (no hot reload).

### Notes / gotchas
- The K-line app's 「自動抓取 K 線」/「一鍵抓取並分析」 buttons call an external Taiwan stock
  data API and require outbound network access; they may fail offline or if the API is
  unreachable. Use 「載入範例資料」 (Load sample data) + 「開始分析」 (Start analysis) for a
  fully offline smoke test of the analysis engine and chart rendering.
- The audio merger app relies on the browser's Web Audio API and needs real audio files as
  input.
- There are no lint or automated test suites in this repo.
