#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
原住民族語言 AI 翻譯合成小幫手（GUI 版）
中文 -> 族語翻譯 -> 語音合成 -> 存成 WAV（檔名 = 翻譯結果）

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

def translate(ethnicity, lang_code, text):
    sess = uuid.uuid4().hex
    # 需在同一 session 先解鎖該族別的語別選項，否則伺服器驗證會拒絕
    gradio_call(TRANSLATE_APP, "lambda_1", [ethnicity], sess)
    out = gradio_call(TRANSLATE_APP, "translate_1", [text, "zho_Hant", lang_code], sess)
    return (out[0] or "").strip()

def synthesize(ethnicity, speaker, text):
    sess = uuid.uuid4().hex
    gradio_call(TTS_APP, "lambda", [ethnicity], sess)
    out = gradio_call(TTS_APP, "default_speaker_tts", [speaker, text], sess)
    file = out[0]
    if not file or not file.get("url"):
        raise RuntimeError("合成結果沒有音檔")
    return file["url"]

def sanitize(name):
    name = re.sub(r'[\\/:*?"<>|\r\n]+', " ", name or "")
    name = re.sub(r"\s+", " ", name).strip()[:60].strip()
    return name or "tts_audio"

# ---------------- GUI ----------------
class App:
    def __init__(self, root):
        self.root = root
        root.title("族語翻譯合成小幫手")
        root.geometry("620x640")
        root.minsize(560, 560)

        self.msg_q = queue.Queue()
        self.running = False
        self.lang_choices = []   # [[顯示名, 代碼], ...]

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

        # --- 輸入區 ---
        ttk.Label(frm, text="中文句子（一行一句，會逐句翻譯＋合成）：").pack(anchor="w", **pad)
        self.input_txt = scrolledtext.ScrolledText(frm, height=8, font=("", 12))
        self.input_txt.pack(fill="both", expand=True, **pad)

        # --- 輸出資料夾 ---
        row2 = ttk.Frame(frm); row2.pack(fill="x", **pad)
        ttk.Label(row2, text="輸出資料夾").pack(side="left")
        self.outdir_var = tk.StringVar(value=str(Path.cwd() / "output"))
        ttk.Entry(row2, textvariable=self.outdir_var).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(row2, text="瀏覽…", command=self.pick_outdir).pack(side="left")

        # --- 執行 ---
        row3 = ttk.Frame(frm); row3.pack(fill="x", **pad)
        self.run_btn = ttk.Button(row3, text="開始 翻譯 ＋ 合成 ＋ 存檔", command=self.start)
        self.run_btn.pack(side="left", fill="x", expand=True)
        self.progress = ttk.Progressbar(frm, mode="determinate")
        self.progress.pack(fill="x", **pad)

        # --- 紀錄 ---
        ttk.Label(frm, text="進度紀錄：").pack(anchor="w", **pad)
        self.log_txt = scrolledtext.ScrolledText(frm, height=10, state="disabled", font=("", 11))
        self.log_txt.pack(fill="both", expand=True, **pad)

        self.root.after(100, self.poll_queue)
        self.load_options()

    # ---------- UI 工具 ----------
    def log(self, text):
        self.msg_q.put(("log", text))

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
                elif kind == "done":
                    self.running = False
                    self.run_btn.configure(state="normal", text="開始 翻譯 ＋ 合成 ＋ 存檔")
        except queue.Empty:
            pass
        self.root.after(100, self.poll_queue)

    def pick_outdir(self):
        d = filedialog.askdirectory(initialdir=self.outdir_var.get() or ".")
        if d:
            self.outdir_var.set(d)

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

    # ---------- 主流程 ----------
    def start(self):
        if self.running:
            return
        sentences = [ln.strip() for ln in self.input_txt.get("1.0", "end").splitlines() if ln.strip()]
        if not sentences:
            messagebox.showwarning("提示", "請先輸入至少一句中文")
            return
        if self.lang_cb.current() < 0 or not self.spk_cb.get() or self.spk_cb.get() == "載入中…":
            messagebox.showwarning("提示", "語別／配音員尚未載入完成")
            return

        eth = self.eth_cb.get()
        lang_code = self.lang_choices[self.lang_cb.current()][1]
        speaker = self.spk_cb.get()
        outdir = Path(self.outdir_var.get())
        outdir.mkdir(parents=True, exist_ok=True)

        self.running = True
        self.run_btn.configure(state="disabled", text="處理中…")
        self.msg_q.put(("progress", (0, len(sentences))))

        def worker():
            ok = fail = 0
            for i, zh in enumerate(sentences, 1):
                try:
                    self.log(f"[{i}/{len(sentences)}] 翻譯：{zh}")
                    native = translate(eth, lang_code, zh)
                    if not native:
                        raise RuntimeError("翻譯結果為空")
                    self.log(f"    → {native}")
                    if len(native) > 300:
                        raise RuntimeError("翻譯結果超過 300 字元上限")
                    self.log("    合成中…（約 5~20 秒）")
                    url = synthesize(eth, speaker, native)
                    dest = outdir / (sanitize(native) + ".wav")
                    with urllib.request.urlopen(url, context=CTX, timeout=120) as r:
                        dest.write_bytes(r.read())
                    self.log(f"    ✓ 已存檔：{dest.name}")
                    ok += 1
                except Exception as e:
                    self.log(f"    ✗ 失敗：{e}")
                    fail += 1
                self.msg_q.put(("progress", (i, len(sentences))))
            self.log(f"—— 全部完成：成功 {ok} 句、失敗 {fail} 句，檔案在 {outdir} ——")
            self.msg_q.put(("done", None))
        threading.Thread(target=worker, daemon=True).start()

def main():
    root = tk.Tk()
    App(root)
    root.mainloop()

if __name__ == "__main__":
    main()
