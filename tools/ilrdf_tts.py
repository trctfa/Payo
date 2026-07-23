#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
原住民族語言研究發展基金會 AI 實驗室：中文 -> 族語翻譯 -> 語音合成 -> 存檔
用法：
    python3 ilrdf_tts.py --ethnicity 太魯閣 "你好嗎？" "謝謝你"
    python3 ilrdf_tts.py --ethnicity 阿美 --file sentences.txt
輸出：./output/<翻譯結果>.wav
"""
import argparse
import json
import re
import ssl
import sys
import urllib.request
import uuid
from pathlib import Path

TRANSLATE_APP = "https://ai-labs.ilrdf.org.tw/kari-seejiq-tnpusu-ai-hmjil"
TTS_APP = "https://ai-labs.ilrdf.org.tw/hnang-kari-ai-asi-sluhay"

CTX = ssl.create_default_context()
# 該網站憑證鏈在部分環境驗證不過；如你的環境正常，可拿掉下面兩行
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

_config_cache = {}

def get_fn_index(app_base: str, api_name: str) -> int:
    if app_base not in _config_cache:
        with urllib.request.urlopen(app_base + "/config", context=CTX) as r:
            _config_cache[app_base] = json.load(r)
    for dep in _config_cache[app_base]["dependencies"]:
        if dep.get("api_name") == api_name:
            return dep["id"]
    raise RuntimeError(f"找不到 API: {api_name}")

def gradio_call(app_base: str, api_name: str, data: list, session: str) -> list:
    fn_index = get_fn_index(app_base, api_name)
    body = json.dumps({"data": data, "fn_index": fn_index, "session_hash": session}).encode()
    req = urllib.request.Request(
        app_base + "/gradio_api/queue/join",
        data=body, headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, context=CTX)

    req = urllib.request.Request(app_base + "/gradio_api/queue/data?session_hash=" + session)
    with urllib.request.urlopen(req, context=CTX) as r:
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

def translate(ethnicity: str, text: str, lang_code: str | None = None) -> str:
    sess = uuid.uuid4().hex
    # 必須先在同一 session 用 lambda_1 解鎖該族別的語別，否則伺服器驗證會拒絕
    upd = gradio_call(TRANSLATE_APP, "lambda_1", [ethnicity], sess)
    choices = upd[0]["choices"]  # [[顯示名, 代碼], ...]
    if lang_code is None:
        lang_code = choices[0][1]
    out = gradio_call(TRANSLATE_APP, "translate_1", [text, "zho_Hant", lang_code], sess)
    return (out[0] or "").strip()

def synthesize(ethnicity: str, text: str, speaker: str | None = None) -> str:
    sess = uuid.uuid4().hex
    upd = gradio_call(TTS_APP, "lambda", [ethnicity], sess)
    speakers = [c[1] for c in upd[0]["choices"]]
    if not speakers:
        raise RuntimeError(f"{ethnicity} 沒有可用的預設配音員")
    if speaker is None:
        speaker = speakers[0]
    elif speaker not in speakers:
        raise RuntimeError(f"配音員 {speaker} 不存在，可用：{speakers}")
    out = gradio_call(TTS_APP, "default_speaker_tts", [speaker, text], sess)
    return out[0]["url"]

def sanitize(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|\r\n]+', " ", name or "")
    name = re.sub(r"\s+", " ", name).strip()[:60].strip()
    return name or "tts_audio"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ethnicity", required=True, help="族別，例如：太魯閣、阿美、泰雅…")
    ap.add_argument("--lang", default=None, help="語別代碼（不填則用該族第一個）")
    ap.add_argument("--speaker", default=None, help="配音員（不填則用該族第一位）")
    ap.add_argument("--file", default=None, help="每行一句中文的文字檔")
    ap.add_argument("--outdir", default="output", help="輸出資料夾")
    ap.add_argument("sentences", nargs="*", help="要翻譯合成的中文句子")
    args = ap.parse_args()

    sentences = list(args.sentences)
    if args.file:
        sentences += [ln.strip() for ln in Path(args.file).read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not sentences:
        ap.error("請提供句子（參數或 --file）")

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    for i, zh in enumerate(sentences, 1):
        print(f"[{i}/{len(sentences)}] 翻譯：{zh}")
        native = translate(args.ethnicity, zh, args.lang)
        if not native:
            print("  ! 翻譯結果為空，跳過"); continue
        print(f"  -> {native}")
        if len(native) > 300:
            print("  ! 超過 300 字元上限，跳過"); continue
        print("  合成中…")
        url = synthesize(args.ethnicity, native, args.speaker)
        dest = outdir / (sanitize(native) + ".wav")
        with urllib.request.urlopen(url, context=CTX) as r:
            dest.write_bytes(r.read())
        print(f"  ✓ 已存檔：{dest}")

if __name__ == "__main__":
    main()
