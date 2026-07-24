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
import io
import json
import queue
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
import urllib.parse
import urllib.request
import uuid
import wave
import xml.etree.ElementTree as ET
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

TRANSLATE_APP = "https://ai-labs.ilrdf.org.tw/kari-seejiq-tnpusu-ai-hmjil"
TTS_APP = "https://ai-labs.ilrdf.org.tw/hnang-kari-ai-asi-sluhay"

ETHNICITIES = ['阿美', '泰雅', '排灣', '布農', '卑南', '魯凱', '鄒', '賽夏',
               '雅美', '邵', '噶瑪蘭', '太魯閣', '撒奇萊雅', '賽德克',
               '拉阿魯哇', '卡那卡那富']

# 開啟程式時的預設選擇（選項清單中找不到時退回第一個）
DEFAULT_ETHNICITY = "阿美"
DEFAULT_LANG_LABEL = "阿美_南勢"
DEFAULT_SPEAKER = "阿美_南勢_女聲"

# 語別標籤 → Klokah 方言編號（https://web.klokah.tw/api/）
KLOKAH_DIALECT = {
    "阿美_南勢": 1, "阿美_秀姑巒": 2, "阿美_海岸": 3, "阿美_馬蘭": 4, "阿美_恆春": 5,
    "泰雅_賽考利克": 6, "泰雅_澤敖利": 7, "泰雅_汶水": 8, "泰雅_萬大": 9,
    "泰雅_四季": 10, "泰雅_宜蘭澤敖利": 11,
    "賽夏": 13, "邵": 14,
    "賽德克_都達": 15, "賽德克_德固達雅": 16, "賽德克_德鹿谷": 17,
    "布農_卓群": 18, "布農_卡群": 19, "布農_丹群": 20, "布農_巒群": 21, "布農_郡群": 22,
    "排灣_東": 23, "排灣_北": 24, "排灣_中": 25, "排灣_南": 26,
    "魯凱_東": 27, "魯凱_霧台": 28, "魯凱_大武": 29, "魯凱_多納": 30,
    "魯凱_茂林": 31, "魯凱_萬山": 32,
    "太魯閣": 33, "噶瑪蘭": 34, "鄒": 35,
    "卡那卡那富": 36, "拉阿魯哇": 37,
    "卑南_南王": 38, "卑南_知本": 39, "卑南_西群": 40, "卑南_建和": 41,
    "雅美": 42, "撒奇萊雅": 43,
}
KLOKAH_SRC_NAME = {
    "alphabet": "字母篇", "conversation": "生活會話", "speech": "句型篇", "nine": "九階教材",
    "twelve": "十二年國教教材", "vocabulary": "千詞表", "custom": "自訂辭典",
    "song": "歌謠篇", "picture": "圖畫故事", "read": "閱讀書寫", "culture": "文化篇",
    "dialogue": "情境族語", "essay": "族語短文", "readingtext": "閱讀文本",
}

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

def merge_wavs(blobs, gap_seconds=0.4):
    """把多個 WAV（格式需相同）串接成一個，句子之間加一小段靜音。"""
    out_buf = io.BytesIO()
    params = None
    silence = b""
    with wave.open(out_buf, "wb") as w:
        for i, blob in enumerate(blobs):
            with wave.open(io.BytesIO(blob)) as r:
                if params is None:
                    params = r.getparams()
                    w.setparams(params)
                    silence = b"\x00" * (int(params.framerate * gap_seconds)
                                         * params.sampwidth * params.nchannels)
                if i > 0:
                    w.writeframes(silence)
                w.writeframes(r.readframes(r.getnframes()))
    return out_buf.getvalue()

def play_wav_file(path):
    """播放 WAV。Windows 用內建 winsound；macOS/Linux 找系統播放器。回傳是否成功啟動。"""
    try:
        if sys.platform == "win32":
            import winsound
            winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
            return True
        for cmd in (["afplay"], ["paplay"], ["aplay", "-q"], ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"]):
            if shutil.which(cmd[0]):
                subprocess.Popen(cmd + [str(path)],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
    except Exception:
        pass
    return False

def klokah_dialect_id(lang_label):
    if lang_label in KLOKAH_DIALECT:
        return KLOKAH_DIALECT[lang_label], lang_label
    for k, v in KLOKAH_DIALECT.items():
        if k in lang_label or lang_label in k:
            return v, k
    return None, lang_label

def klokah_search(dialect_id, query):
    """呼叫族語 E 樂園 API，回傳 [{native, chinese, src, url}, ...]。"""
    url = ("https://web.klokah.tw/api/multiSearchResult.php?d="
           + str(dialect_id) + "&txt=" + urllib.parse.quote(query))
    with urllib.request.urlopen(url, context=CTX, timeout=30) as r:
        xml_text = r.read().decode("utf-8", errors="replace")
    root = ET.fromstring(xml_text)
    items, seen = [], set()
    for section in list(root):
        src = KLOKAH_SRC_NAME.get(section.tag, section.tag)
        for item in section.findall("item"):
            native = (item.findtext("text") or "").strip()
            chinese = (item.findtext("chinese") or "").strip()
            link = (item.findtext("url") or "").strip()
            key = native + "|" + chinese
            if not native or key in seen:
                continue
            seen.add(key)
            items.append({"native": native, "chinese": chinese, "src": src, "url": link})
    return items

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
        self.rows = []           # 編輯區每行：{'var','zh','tr','btn','play','frame'}
        self.audio_cache = {}    # (配音員, 文字) -> wav bytes，避免重複合成
        self.tmpdir = Path(tempfile.mkdtemp(prefix="ilrdf_tts_"))
        self.pending_project = None  # 開啟專案時暫存，等選項載入完再套用

        pad = {"padx": 8, "pady": 4}
        frm = ttk.Frame(root)
        frm.pack(fill="both", expand=True, padx=10, pady=10)

        # --- 選項列 ---
        row1 = ttk.Frame(frm); row1.pack(fill="x", **pad)
        ttk.Label(row1, text="族別").pack(side="left")
        self.eth_cb = ttk.Combobox(row1, values=ETHNICITIES, state="readonly", width=10)
        self.eth_cb.set(DEFAULT_ETHNICITY)
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
            frm, text="步驟二：編輯區（可改字；「重新」重翻、「▶唸」試聽、「字典」查 Klokah 並套用）")
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

        row_sel = ttk.Frame(frm); row_sel.pack(fill="x", **pad)
        self.select_all_btn = ttk.Button(row_sel, text="全選", command=lambda: self.set_all_checked(True))
        self.select_all_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.clear_sel_btn = ttk.Button(row_sel, text="清除勾選", command=lambda: self.set_all_checked(False))
        self.clear_sel_btn.pack(side="left", fill="x", expand=True, padx=4)
        self.delete_sel_btn = ttk.Button(row_sel, text="刪除勾選句子", command=self.delete_selected)
        self.delete_sel_btn.pack(side="left", fill="x", expand=True, padx=(4, 0))

        row3 = ttk.Frame(frm); row3.pack(fill="x", **pad)
        self.export_all_btn = ttk.Button(row3, text="匯出全部（語音＋文字檔）",
                                         command=lambda: self.export(selected_only=False))
        self.export_all_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.export_sel_btn = ttk.Button(row3, text="匯出勾選項目",
                                         command=lambda: self.export(selected_only=True))
        self.export_sel_btn.pack(side="left", fill="x", expand=True, padx=(4, 0))

        self.export_merge_btn = ttk.Button(
            frm, text="串接全部句子 → 匯出成一個語音檔", command=self.export_merged)
        self.export_merge_btn.pack(fill="x", **pad)

        row4 = ttk.Frame(frm); row4.pack(fill="x", **pad)
        self.save_proj_btn = ttk.Button(row4, text="儲存專案（下次可再編輯）", command=self.save_project)
        self.save_proj_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.open_proj_btn = ttk.Button(row4, text="開啟專案", command=self.open_project)
        self.open_proj_btn.pack(side="left", fill="x", expand=True, padx=(4, 0))

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
        self.export_merge_btn.configure(state=state)
        self.save_proj_btn.configure(state=state)
        self.open_proj_btn.configure(state=state)
        self.select_all_btn.configure(state=state)
        self.clear_sel_btn.configure(state=state)
        self.delete_sel_btn.configure(state=state)
        for r in self.rows:
            r["btn"].configure(state=state)
            r["play"].configure(state=state)
            r["dict"].configure(state=state)

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
                    labels = [l[0] for l in langs]
                    self.lang_cb["values"] = labels
                    if langs:
                        self.lang_cb.current(
                            labels.index(DEFAULT_LANG_LABEL) if DEFAULT_LANG_LABEL in labels else 0)
                    self.spk_cb["values"] = spks
                    if spks:
                        self.spk_cb.current(
                            spks.index(DEFAULT_SPEAKER) if DEFAULT_SPEAKER in spks else 0)
                    # 開啟專案：選項載入完成後套用專案內容
                    if self.pending_project:
                        p, self.pending_project = self.pending_project, None
                        if p.get("lang_label") in labels:
                            self.lang_cb.current(labels.index(p["lang_label"]))
                        if p.get("speaker") in spks:
                            self.spk_cb.current(spks.index(p["speaker"]))
                        self.build_rows([(r.get("zh", ""), r.get("tr", "")) for r in p["rows"]])
                        for state_r, row in zip(p["rows"], self.rows):
                            row["var"].set(bool(state_r.get("checked")))
                        self.log(f"✓ 專案已載入，共 {len(self.rows)} 句，可以繼續編輯")
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
                elif kind == "play_reset":
                    idx = payload
                    if 0 <= idx < len(self.rows):
                        self.rows[idx]["play"].configure(state="normal", text="▶ 唸")
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
            play = ttk.Button(left, text="▶ 唸", width=5,
                              command=lambda i=idx: self.play_row(i))
            play.pack(pady=(2, 0))
            dict_btn = ttk.Button(left, text="字典", width=5,
                                  command=lambda i=idx: self.open_dict(i))
            dict_btn.pack(pady=(2, 0))

            zh_e = tk.Entry(f, font=("", 12))
            zh_e.insert(0, zh)
            zh_e.grid(row=0, column=1, sticky="ew")
            tr_e = tk.Entry(f, font=("", 13), fg="#0a7d4f")
            tr_e.insert(0, tr)
            tr_e.grid(row=1, column=1, sticky="ew", pady=(3, 0))
            f.columnconfigure(1, weight=1)

            ttk.Separator(self.rows_frame).pack(fill="x", pady=2)
            self.rows.append({"var": var, "zh": zh_e, "tr": tr_e,
                              "btn": btn, "play": play, "dict": dict_btn, "frame": f})
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

    # ---------- 語音合成（含快取） ----------
    def get_audio(self, eth, speaker, text, session=None):
        """取得該句語音的 WAV bytes；唸過／匯出過的句子直接用快取，不重新合成。"""
        key = (speaker, text)
        if key in self.audio_cache:
            return self.audio_cache[key]
        if len(text) > 300:
            raise RuntimeError("文字超過 300 字元上限")
        if session is None:
            session = uuid.uuid4().hex
            gradio_call(TTS_APP, "lambda", [eth], session)
        out = gradio_call(TTS_APP, "default_speaker_tts", [speaker, text], session)
        url = out[0]["url"]
        with urllib.request.urlopen(url, context=CTX, timeout=120) as r:
            data = r.read()
        self.audio_cache[key] = data
        return data

    # ---------- 單句試聽 ----------
    def play_row(self, idx):
        if self.running:
            return
        tr = self.rows[idx]["tr"].get().strip()
        if not tr:
            messagebox.showwarning("提示", "這一行還沒有翻譯文字")
            return
        if not self.spk_cb.get() or self.spk_cb.get() == "載入中…":
            messagebox.showwarning("提示", "配音員尚未載入完成")
            return
        eth, _, speaker = self.current_selection()

        play_btn = self.rows[idx]["play"]
        play_btn.configure(state="disabled", text="…")

        def worker():
            try:
                cached = (speaker, tr) in self.audio_cache
                if not cached:
                    self.log(f"第 {idx + 1} 行合成中（約 5~20 秒）：{tr}")
                data = self.get_audio(eth, speaker, tr)
                tmp = self.tmpdir / (sanitize(tr) + ".wav")
                tmp.write_bytes(data)
                if play_wav_file(tmp):
                    self.log(f"▶ 播放第 {idx + 1} 行：{tr}")
                else:
                    self.log(f"✗ 找不到可用的播放器，音檔在：{tmp}")
            except Exception as e:
                self.log(f"✗ 第 {idx + 1} 行試聽失敗：{e}")
            finally:
                self.msg_q.put(("play_reset", idx))
        threading.Thread(target=worker, daemon=True).start()

    # ---------- 查字典（Klokah 內嵌＋套用） ----------
    def open_dict(self, idx):
        if idx < 0 or idx >= len(self.rows):
            return
        row = self.rows[idx]
        lang_label = self.lang_cb.get()
        dialect_id, mapped = klokah_dialect_id(lang_label)
        if dialect_id is None:
            messagebox.showwarning("提示", f"語別「{lang_label}」找不到對應的 Klokah 方言編號")
            return

        # 反白文字優先，否則用整句翻譯／中文
        q = ""
        try:
            if row["tr"].selection_present():
                q = row["tr"].selection_get().strip()
            elif row["zh"].selection_present():
                q = row["zh"].selection_get().strip()
        except tk.TclError:
            q = ""
        if not q:
            q = row["tr"].get().strip() or row["zh"].get().strip()

        win = tk.Toplevel(self.root)
        win.title(f"查字典 · {mapped}")
        win.geometry("560x480")
        win.transient(self.root)

        ttk.Label(win, text=f"語別：{mapped}（Klokah #{dialect_id}）　目標：第 {idx + 1} 行").pack(
            anchor="w", padx=10, pady=(10, 4))
        bar = ttk.Frame(win); bar.pack(fill="x", padx=10, pady=4)
        q_var = tk.StringVar(value=q)
        ttk.Entry(bar, textvariable=q_var, font=("", 12)).pack(side="left", fill="x", expand=True)
        go_btn = ttk.Button(bar, text="查詢"); go_btn.pack(side="left", padx=(6, 0))

        meta = ttk.Label(win, text="輸入關鍵字後按查詢（中文或族語皆可）")
        meta.pack(anchor="w", padx=10, pady=4)

        list_frame = ttk.Frame(win); list_frame.pack(fill="both", expand=True, padx=10, pady=4)
        lb = tk.Listbox(list_frame, font=("", 11), activestyle="dotbox")
        sb = ttk.Scrollbar(list_frame, orient="vertical", command=lb.yview)
        lb.configure(yscrollcommand=sb.set)
        lb.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        results = []

        def render(items):
            results.clear()
            results.extend(items)
            lb.delete(0, "end")
            for it in items:
                line = it["native"]
                if it["chinese"]:
                    line += "　｜　" + it["chinese"]
                line += "　〔" + it["src"] + "〕"
                lb.insert("end", line)
            meta.configure(text=f"找到 {len(items)} 筆" if items else "沒有找到結果，可改打單字或中文再試")

        def do_search():
            query = q_var.get().strip()
            if not query:
                meta.configure(text="請輸入要查詢的字")
                return
            go_btn.configure(state="disabled")
            meta.configure(text=f"查詢中：「{query}」…")

            def worker():
                try:
                    items = klokah_search(dialect_id, query)[:40]
                    self.msg_q.put(("log", f"字典查詢「{query}」→ {len(items)} 筆"))
                    win.after(0, lambda: (render(items), go_btn.configure(state="normal")))
                except Exception as e:
                    win.after(0, lambda: (
                        meta.configure(text=f"查詢失敗：{e}"),
                        go_btn.configure(state="normal")))
            threading.Thread(target=worker, daemon=True).start()

        def apply_selected():
            sel = lb.curselection()
            if not sel:
                messagebox.showwarning("提示", "請先點選一筆結果", parent=win)
                return
            if idx >= len(self.rows):
                messagebox.showwarning("提示", "目標句子已不存在", parent=win)
                return
            native = results[sel[0]]["native"]
            e = self.rows[idx]["tr"]
            e.delete(0, "end")
            e.insert(0, native)
            self.log(f"✓ 字典套用第 {idx + 1} 行：{native}")
            win.destroy()

        go_btn.configure(command=do_search)
        win.bind("<Return>", lambda e: do_search())
        btn_row = ttk.Frame(win); btn_row.pack(fill="x", padx=10, pady=10)
        ttk.Button(btn_row, text="套用到該行翻譯", command=apply_selected).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ttk.Button(btn_row, text="關閉", command=win.destroy).pack(side="left", fill="x", expand=True, padx=(4, 0))
        ttk.Label(win, text="資料來源：族語 E 樂園公開 API（web.klokah.tw）",
                  foreground="#666").pack(anchor="w", padx=10, pady=(0, 8))

        if q:
            do_search()

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
                            self.log(f"[{n}/{len(items)}] 第 {row_no} 行合成中：{tr}")
                            data = self.get_audio(eth, speaker, tr, session=sess)
                            dest = outdir / (sanitize(tr) + ".wav")
                            dest.write_bytes(data)
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

    # ---------- 勾選／批次刪除 ----------
    def set_all_checked(self, value):
        if not self.rows:
            return
        for r in self.rows:
            r["var"].set(value)
        self.log("已" + ("全選" if value else "清除勾選") + f" {len(self.rows)} 句")

    def delete_selected(self):
        if self.running:
            return
        if not self.rows:
            messagebox.showwarning("提示", "編輯區還沒有句子")
            return
        kept = []
        removed = 0
        for r in self.rows:
            if r["var"].get():
                removed += 1
            else:
                kept.append((r["zh"].get(), r["tr"].get()))
        if removed == 0:
            messagebox.showwarning("提示", "請先勾選要刪除的句子")
            return
        if not messagebox.askyesno("確認刪除", f"確定刪除勾選的 {removed} 句嗎？"):
            return
        self.build_rows(kept)
        self.log(f"✓ 已刪除 {removed} 句，剩餘 {len(kept)} 句")

    # ---------- 專案儲存／開啟（與網頁版通用的 JSON 格式） ----------
    def save_project(self):
        if not self.rows:
            messagebox.showwarning("提示", "編輯區還沒有內容，沒有東西可以存")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("族語專案檔", "*.json")],
            initialfile="族語專案.json")
        if not path:
            return
        data = {
            "app": "zyfy-project", "version": 1,
            "ethnicity": self.eth_cb.get(),
            "lang_label": self.lang_cb.get(),
            "speaker": self.spk_cb.get(),
            "rows": [{"zh": r["zh"].get(), "tr": r["tr"].get(), "checked": r["var"].get()}
                     for r in self.rows],
        }
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        self.log(f"✓ 專案已儲存：{path}")

    def open_project(self):
        path = filedialog.askopenfilename(
            filetypes=[("族語專案檔", "*.json"), ("所有檔案", "*.*")])
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
            if data.get("app") != "zyfy-project" or not isinstance(data.get("rows"), list):
                raise ValueError("不是族語專案檔")
        except Exception as e:
            messagebox.showerror("錯誤", f"無法讀取專案檔：{e}")
            return
        self.pending_project = data
        eth = data.get("ethnicity")
        if eth in ETHNICITIES:
            self.eth_cb.set(eth)
        self.log(f"開啟專案：{Path(path).name}（載入選項中…）")
        self.load_options()  # 選項載入完成後（poll_queue）會自動套用專案內容

    # ---------- 串接匯出：全部句子合成一個音檔 ----------
    def export_merged(self):
        if self.running:
            return
        items = []  # (列號, 翻譯)
        for i, r in enumerate(self.rows):
            tr = r["tr"].get().strip()
            if tr:
                items.append((i + 1, tr))
        if not items:
            messagebox.showwarning("提示", "編輯區還沒有可合成的翻譯，請先執行步驟一")
            return
        if not self.spk_cb.get() or self.spk_cb.get() == "載入中…":
            messagebox.showwarning("提示", "配音員尚未載入完成")
            return

        eth, _, speaker = self.current_selection()
        outdir = Path(self.outdir_var.get())
        outdir.mkdir(parents=True, exist_ok=True)

        self.set_busy(True)
        self.msg_q.put(("progress", (0, len(items))))

        def worker():
            try:
                sess = uuid.uuid4().hex
                gradio_call(TTS_APP, "lambda", [eth], sess)  # 解鎖配音員，一次即可

                blobs = []
                for n, (row_no, tr) in enumerate(items, 1):
                    self.log(f"[{n}/{len(items)}] 第 {row_no} 行合成中：{tr}")
                    blobs.append(self.get_audio(eth, speaker, tr, session=sess))
                    self.msg_q.put(("progress", (n, len(items))))

                merged = merge_wavs(blobs, gap_seconds=0.4)
                first = sanitize(items[0][1])[:20]
                dest = outdir / f"串接語音_{first}_共{len(items)}句.wav"
                dest.write_bytes(merged)

                with wave.open(io.BytesIO(merged)) as w:
                    secs = w.getnframes() / w.getframerate()
                self.log(f"✓ 串接完成：{dest.name}（{len(items)} 句、約 {secs:.1f} 秒）")
                self.log(f"—— 檔案在 {outdir} ——")
            except Exception as e:
                self.log(f"✗ 串接匯出失敗：{e}")
            finally:
                self.msg_q.put(("done", None))
        threading.Thread(target=worker, daemon=True).start()

def main():
    root = tk.Tk()
    App(root)
    root.mainloop()

if __name__ == "__main__":
    main()
