#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
原住民族語言 AI 翻譯合成小幫手（GUI 編輯版）

工作流程：
  步驟一：貼上多行中文（一行一句）→ 按「翻譯全部句子」
  步驟二：編輯區列出「一行中文、一行翻譯」，所有文字都可直接修改；
          改完中文可按該行的「重新」單獨重翻那一句
  步驟三：按「匯出全部」把語音＋對照文字檔存到輸出資料夾；
          或勾選部分句子按「匯出勾選」單獨匯出

需求：Python 3.10+（tkinter 為標準庫，Windows/macOS 官方安裝版都有內建）
用法：python3 ilrdf_tts_gui.py
"""
import json
import queue
import re
import ssl
import threading
import tkinter as tk
import urllib.request
import uuid
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

TRANSLATE_APP = "https://ai-labs.ilrdf.org.tw/kari-seejiq-tnpusu-ai-hmjil"
TTS_APP = "https://ai-labs.ilrdf.org.tw/hnang-kari-ai-asi-sluhay"

ETHNICITIES = ['阿美', '泰雅', '排灣', '布農', '卑南', '魯凱', '鄒', '賽夏',
               '雅美', '邵', '噶瑪蘭', '太魯閣', '撒奇萊雅', '賽德克',
               '拉阿魯哇', '卡那卡那富']

CTX = ssl.create_default_context()
# 該網站憑證鏈在部分環境驗證不過；如你的環境正常，可拿掉下面兩行
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

# ---------------- Gradio API ----------------
_config_cache = {}

def _get_fn_index(app_base, api_name):
    if app_base not in _config_cache:
        with urllib.request.urlopen(app_base + "/config", context=CTX, timeout=30) as r:
            _config_cache[app_base] = json.load(r)
    for dep in _config_cache[app_base]["dependencies"]:
        if dep.get("api_name") == api_name:
            return dep["id"]
    raise RuntimeError(f"找不到 API: {api_name}")

def gradio_call(app_base, api_name, data, session):
    fn_index = _get_fn_index(app_base, api_name)
    body = json.dumps({"data": data, "fn_index": fn_index,
                       "session_hash": session}).encode()
    req = urllib.request.Request(app_base + "/gradio_api/queue/join", data=body,
                                 headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, context=CTX, timeout=30)

    req = urllib.request.Request(app_base + "/gradio_api/queue/data?session_hash=" + session)
    with urllib.request.urlopen(req, context=CTX, timeout=300) as r:
        for line in r:
            line = line.decode().strip()
            if not line.startswith("data:"):
                continue
            msg = json.loads(line[5:])
            if msg.get("msg") == "process_completed":
                if msg.get("success") is False:
                    raise RuntimeError(f"{api_name} 後端處理失敗")
                return msg["output"]["data"]
    raise RuntimeError(f"{api_name} 未收到結果")

def fetch_options(ethnicity):
    """回傳 (語別choices [[顯示名, 代碼],...], 配音員名單 [str,...])"""
    langs = gradio_call(TRANSLATE_APP, "lambda_1", [ethnicity], uuid.uuid4().hex)[0]["choices"]
    spks = [c[1] for c in gradio_call(TTS_APP, "lambda", [ethnicity], uuid.uuid4().hex)[0]["choices"]]
    return langs, spks

def translate_one(ethnicity, lang_code, text, session=None):
    """翻譯一句。session 為 None 時自建新 session 並解鎖族別。"""
    if session is None:
        session = uuid.uuid4().hex
        gradio_call(TRANSLATE_APP, "lambda_1", [ethnicity], session)
    out = gradio_call(TRANSLATE_APP, "translate_1", [text, "zho_Hant", lang_code], session)
    return (out[0] or "").strip()

def sanitize(name):
    name = re.sub(r'[\\/:*?"<>|\r\n]+', " ", name or "")
    name = re.sub(r"\s+", " ", name).strip()[:60].strip()
    return name or "tts_audio"

# ---------------- GUI ----------------
class App:
    def __init__(self, root):
        self.root = root
        root.title("族語翻譯合成小幫手（編輯版）")
        root.geometry("820x900")
        root.minsize(700, 720)

        self.msg_q = queue.Queue()
        self.running = False
        self.lang_choices = []   # [[顯示名, 代碼], ...]
        self.rows = []           # 編輯區每行：{'var','zh','tr','btn','frame'}

        pad = {"padx": 8, "pady": 4}
        frm = ttk.Frame(root)
        frm.pack(fill="both", expand=True, padx=10, pady=10)

        # --- 選項列 ---
        row1 = ttk.Frame(frm); row1.pack(fill="x", **pad)
        ttk.Label(row1, text="族別").pack(side="left")
        self.eth_cb = ttk.Combobox(row1, values=ETHNICITIES, state="readonly", width=10)
        self.eth_cb.set(ETHNICITIES[0])
        self.eth_cb.pack(side="left", padx=(4, 16))
        self.eth_cb.bind("<<ComboboxSelected>>", lambda e: self.load_options())

        ttk.Label(row1, text="語別").pack(side="left")
        self.lang_cb = ttk.Combobox(row1, state="readonly", width=16)
        self.lang_cb.pack(side="left", padx=(4, 16))

        ttk.Label(row1, text="配音員").pack(side="left")
        self.spk_cb = ttk.Combobox(row1, state="readonly", width=18)
        self.spk_cb.pack(side="left", padx=4)

        # --- 步驟一：輸入 ---
        ttk.Label(frm, text="步驟一：貼上中文文章（一行一句）→ 按「翻譯全部句子」").pack(anchor="w", **pad)
        self.input_txt = scrolledtext.ScrolledText(frm, height=5, font=("", 12))
        self.input_txt.pack(fill="x", **pad)
        self.translate_btn = ttk.Button(frm, text="翻譯全部句子 → 進入編輯區", command=self.translate_all)
        self.translate_btn.pack(fill="x", **pad)

        # --- 步驟二：編輯區 ---
        editor_box = ttk.LabelFrame(
            frm, text="步驟二：編輯區（上排中文、下排翻譯都可以直接修改；改完中文按「重新」單獨重翻那一句）")
        editor_box.pack(fill="both", expand=True, **pad)

        self.canvas = tk.Canvas(editor_box, highlightthickness=0)
        sb = ttk.Scrollbar(editor_box, orient="vertical", command=self.canvas.yview)
        self.rows_frame = ttk.Frame(self.canvas)
        self._canvas_win = self.canvas.create_window((0, 0), window=self.rows_frame, anchor="nw")
        self.rows_frame.bind("<Configure>",
                             lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>",
                         lambda e: self.canvas.itemconfigure(self._canvas_win, width=e.width))
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        # 滑鼠滾輪（Windows / Linux）
        self.canvas.bind_all("<MouseWheel>",
                             lambda e: self.canvas.yview_scroll(-1 * (e.delta // 120), "units"))
        self.canvas.bind_all("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind_all("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))

        # --- 步驟三：匯出 ---
        row2 = ttk.Frame(frm); row2.pack(fill="x", **pad)
        ttk.Label(row2, text="輸出資料夾").pack(side="left")
        self.outdir_var = tk.StringVar(value=str(Path.cwd() / "output"))
        ttk.Entry(row2, textvariable=self.outdir_var).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(row2, text="瀏覽…", command=self.pick_outdir).pack(side="left")

        self.text_only_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm, text="匯出時只存對照文字檔，不合成語音",
                        variable=self.text_only_var).pack(anchor="w", **pad)

        row3 = ttk.Frame(frm); row3.pack(fill="x", **pad)
        self.export_all_btn = ttk.Button(row3, text="匯出全部（語音＋文字檔）",
                                         command=lambda: self.export(selected_only=False))
        self.export_all_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.export_sel_btn = ttk.Button(row3, text="匯出勾選項目",
                                         command=lambda: self.export(selected_only=True))
        self.export_sel_btn.pack(side="left", fill="x", expand=True, padx=(4, 0))

        self.progress = ttk.Progressbar(frm, mode="determinate")
        self.progress.pack(fill="x", **pad)

        self.log_txt = scrolledtext.ScrolledText(frm, height=6, state="disabled", font=("", 10))
        self.log_txt.pack(fill="x", **pad)

        self.root.after(100, self.poll_queue)
        self.load_options()

    # ---------- UI 工具 ----------
    def log(self, text):
        self.msg_q.put(("log", text))

    def set_busy(self, busy):
        self.running = busy
        state = "disabled" if busy else "normal"
        self.translate_btn.configure(state=state)
        self.export_all_btn.configure(state=state)
        self.export_sel_btn.configure(state=state)
        for r in self.rows:
            r["btn"].configure(state=state)

    def poll_queue(self):
        try:
            while True:
                kind, payload = self.msg_q.get_nowait()
                if kind == "log":
                    self.log_txt.configure(state="normal")
                    self.log_txt.insert("end", payload + "\n")
                    self.log_txt.see("end")
                    self.log_txt.configure(state="disabled")
                elif kind == "options":
                    langs, spks = payload
                    self.lang_choices = langs
                    self.lang_cb["values"] = [l[0] for l in langs]
                    if langs: self.lang_cb.current(0)
                    self.spk_cb["values"] = spks
                    if spks: self.spk_cb.current(0)
                elif kind == "progress":
                    done, total = payload
                    self.progress["maximum"] = total
                    self.progress["value"] = done
                elif kind == "rows":
                    self.build_rows(payload)
                elif kind == "set_tr":
                    idx, text = payload
                    if 0 <= idx < len(self.rows):
                        e = self.rows[idx]["tr"]
                        e.delete(0, "end")
                        e.insert(0, text)
                elif kind == "btn_reset":
                    idx = payload
                    if 0 <= idx < len(self.rows):
                        self.rows[idx]["btn"].configure(state="normal", text="重新")
                elif kind == "done":
                    self.set_busy(False)
        except queue.Empty:
            pass
        self.root.after(100, self.poll_queue)

    def pick_outdir(self):
        d = filedialog.askdirectory(initialdir=self.outdir_var.get() or ".")
        if d:
            self.outdir_var.set(d)

    def current_selection(self):
        eth = self.eth_cb.get()
        lang_code = self.lang_choices[self.lang_cb.current()][1]
        speaker = self.spk_cb.get()
        return eth, lang_code, speaker

    # ---------- 載入語別/配音員 ----------
    def load_options(self):
        eth = self.eth_cb.get()
        self.lang_cb.set("載入中…"); self.spk_cb.set("載入中…")

        def worker():
            try:
                langs, spks = fetch_options(eth)
                self.msg_q.put(("options", (langs, spks)))
                self.log(f"已載入「{eth}」：{len(langs)} 個語別、{len(spks)} 位配音員")
            except Exception as e:
                self.msg_q.put(("options", ([], [])))
                self.log(f"載入選項失敗：{e}")
        threading.Thread(target=worker, daemon=True).start()

    # ---------- 編輯區 ----------
    def build_rows(self, pairs):
        for w in self.rows_frame.winfo_children():
            w.destroy()
        self.rows = []
        for idx, (zh, tr) in enumerate(pairs):
            f = ttk.Frame(self.rows_frame, padding=(4, 4))
            f.pack(fill="x", expand=True)

            left = ttk.Frame(f)
            left.grid(row=0, column=0, rowspan=2, sticky="n", padx=(0, 4))
            var = tk.BooleanVar(value=False)
            ttk.Checkbutton(left, variable=var).pack()
            btn = ttk.Button(left, text="重新", width=5,
                             command=lambda i=idx: self.retranslate(i))
            btn.pack(pady=(2, 0))

            zh_e = tk.Entry(f, font=("", 12))
            zh_e.insert(0, zh)
            zh_e.grid(row=0, column=1, sticky="ew")
            tr_e = tk.Entry(f, font=("", 13), fg="#0a7d4f")
            tr_e.insert(0, tr)
            tr_e.grid(row=1, column=1, sticky="ew", pady=(3, 0))
            f.columnconfigure(1, weight=1)

            ttk.Separator(self.rows_frame).pack(fill="x", pady=2)
            self.rows.append({"var": var, "zh": zh_e, "tr": tr_e, "btn": btn, "frame": f})
        self.canvas.yview_moveto(0)

    # ---------- 步驟一：翻譯全部 ----------
    def translate_all(self):
        if self.running:
            return
        lines = [ln.strip() for ln in self.input_txt.get("1.0", "end").splitlines() if ln.strip()]
        if not lines:
            messagebox.showwarning("提示", "請先在步驟一貼上中文（一行一句）")
            return
        if self.lang_cb.current() < 0 or self.lang_cb.get() == "載入中…":
            messagebox.showwarning("提示", "語別尚未載入完成")
            return
        eth, lang_code, _ = self.current_selection()

        self.set_busy(True)
        self.msg_q.put(("progress", (0, len(lines))))

        def worker():
            pairs = []
            try:
                sess = uuid.uuid4().hex
                gradio_call(TRANSLATE_APP, "lambda_1", [eth], sess)  # 解鎖族別，一次即可
                for i, zh in enumerate(lines, 1):
                    try:
                        native = translate_one(eth, lang_code, zh, session=sess)
                        self.log(f"[{i}/{len(lines)}] {zh} → {native}")
                    except Exception as e:
                        native = ""
                        self.log(f"[{i}/{len(lines)}] {zh} → ✗ 翻譯失敗：{e}")
                    pairs.append((zh, native))
                    self.msg_q.put(("progress", (i, len(lines))))
                self.msg_q.put(("rows", pairs))
                self.log(f"—— 翻譯完成，共 {len(pairs)} 句，請在編輯區修改後匯出 ——")
            except Exception as e:
                self.log(f"✗ 翻譯中斷：{e}")
            finally:
                self.msg_q.put(("done", None))
        threading.Thread(target=worker, daemon=True).start()

    # ---------- 單行重翻 ----------
    def retranslate(self, idx):
        if self.running:
            return
        zh = self.rows[idx]["zh"].get().strip()
        if not zh:
            messagebox.showwarning("提示", "這一行的中文是空的")
            return
        if self.lang_cb.current() < 0:
            return
        eth, lang_code, _ = self.current_selection()

        btn = self.rows[idx]["btn"]
        btn.configure(state="disabled", text="翻譯中")

        def worker():
            try:
                native = translate_one(eth, lang_code, zh)
                self.msg_q.put(("set_tr", (idx, native)))
                self.log(f"重新翻譯第 {idx + 1} 行：{zh} → {native}")
            except Exception as e:
                self.log(f"✗ 第 {idx + 1} 行重翻失敗：{e}")
            finally:
                # 一律透過訊息佇列回到主執行緒更新 UI
                self.msg_q.put(("btn_reset", idx))
        threading.Thread(target=worker, daemon=True).start()

    # ---------- 步驟三：匯出 ----------
    def export(self, selected_only):
        if self.running:
            return
        if not self.rows:
            messagebox.showwarning("提示", "編輯區還沒有內容，請先執行步驟一")
            return

        items = []  # (列號, 中文, 翻譯)
        for i, r in enumerate(self.rows):
            if selected_only and not r["var"].get():
                continue
            zh = r["zh"].get().strip()
            tr = r["tr"].get().strip()
            if zh and tr:
                items.append((i + 1, zh, tr))
        if not items:
            messagebox.showwarning(
                "提示", "沒有可匯出的句子" + ("（請先勾選要匯出的行）" if selected_only else ""))
            return

        text_only = self.text_only_var.get()
        if not text_only and (not self.spk_cb.get() or self.spk_cb.get() == "載入中…"):
            messagebox.showwarning("提示", "配音員尚未載入完成")
            return

        eth, _, speaker = self.current_selection()
        outdir = Path(self.outdir_var.get())
        outdir.mkdir(parents=True, exist_ok=True)

        self.set_busy(True)
        self.msg_q.put(("progress", (0, len(items))))

        def worker():
            ok = fail = 0
            try:
                sess = None
                if not text_only:
                    sess = uuid.uuid4().hex
                    gradio_call(TTS_APP, "lambda", [eth], sess)  # 解鎖配音員，一次即可

                for n, (row_no, zh, tr) in enumerate(items, 1):
                    try:
                        if not text_only:
                            if len(tr) > 300:
                                raise RuntimeError("翻譯超過 300 字元上限")
                            self.log(f"[{n}/{len(items)}] 第 {row_no} 行合成中：{tr}")
                            out = gradio_call(TTS_APP, "default_speaker_tts", [speaker, tr], sess)
                            url = out[0]["url"]
                            dest = outdir / (sanitize(tr) + ".wav")
                            with urllib.request.urlopen(url, context=CTX, timeout=120) as r:
                                dest.write_bytes(r.read())
                            self.log(f"    ✓ 音檔：{dest.name}")
                        ok += 1
                    except Exception as e:
                        self.log(f"    ✗ 第 {row_no} 行失敗：{e}")
                        fail += 1
                    self.msg_q.put(("progress", (n, len(items))))

                # 一行中文、一行翻譯，依編輯區順序（utf-8-sig 讓 Windows 記事本正確開啟）
                txt_name = "翻譯對照_勾選.txt" if selected_only else "翻譯對照.txt"
                txt_path = outdir / txt_name
                txt_path.write_text(
                    "\n".join(line for _, zh, tr in items for line in (zh, tr)) + "\n",
                    encoding="utf-8-sig")
                self.log(f"✓ 對照文字檔：{txt_path.name}（共 {len(items)} 句）")
                self.log(f"—— 匯出完成：成功 {ok} 句、失敗 {fail} 句，檔案在 {outdir} ——")
            except Exception as e:
                self.log(f"✗ 匯出中斷：{e}")
            finally:
                self.msg_q.put(("done", None))
        threading.Thread(target=worker, daemon=True).start()

def main():
    root = tk.Tk()
    App(root)
    root.mainloop()

if __name__ == "__main__":
    main()
