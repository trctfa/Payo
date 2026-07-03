import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os, sys, threading, time, subprocess, re, math
from datetime import timedelta, datetime

try:
    import cv2
except ImportError:
    print("錯誤：找不到 cv2 (OpenCV)")
    print("請在 PowerShell 執行以下指令安裝依賴：")
    print(f'  & "{sys.executable}" -m pip install opencv-python Pillow')
    sys.exit(1)

try:
    from PIL import Image, ImageTk
except ImportError:
    print("錯誤：找不到 PIL (Pillow)")
    print("請在 PowerShell 執行以下指令：")
    print(f'  & "{sys.executable}" -m pip install Pillow')
    sys.exit(1)

# 處理 GPU 監控套件
try:
    import nvidia_ml_py as pynvml
    HAS_GPU_TOOL = True
except ImportError:
    try:
        import pynvml
        HAS_GPU_TOOL = True
    except ImportError:
        HAS_GPU_TOOL = False

class VideoMasterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Python 專業影片拼接器 - FPS 偵測版")
        self.root.geometry("1600x900")

        self.video_list = []
        self.is_playing = False
        self.current_cap = None
        self.current_frame_idx = 0
        self.total_frames = 0
        self.preview_timer = None

        self.sort_status = {k: False for k in ["name", "ratio", "fps", "date", "size", "duration"]}
        self.audio_std_var = tk.BooleanVar(value=False)
        self.fast_mode_var = tk.BooleanVar(value=False)

        self.has_gpu = False
        if HAS_GPU_TOOL:
            try:
                pynvml.nvmlInit()
                self.has_gpu = True
            except:
                self.has_gpu = False

        self.setup_ui()
        self.bind_shortcuts()
        self.update_gpu_info()

    def get_ratio(self, width, height):
        if width == 0 or height == 0:
            return "Unknown"
        gcd = math.gcd(int(width), int(height))
        return f"{int(width/gcd)}:{int(height/gcd)}"

    def get_video_shooting_date(self, filepath):
        cmd = ['ffprobe', '-v', 'quiet', '-select_streams', 'v:0', '-show_entries', 'format_tags=creation_time', '-of', 'default=noprint_wrappers=1:nokey=1', filepath]
        try:
            output = subprocess.check_output(cmd, shell=True).decode().strip()
            if output:
                dt = datetime.strptime(output[:19], '%Y-%m-%dT%H:%M:%S')
                local_dt = dt + timedelta(hours=8)
                return local_dt.strftime('%Y-%m-%d %H:%M'), local_dt.timestamp()
        except:
            pass
        return datetime.fromtimestamp(os.path.getctime(filepath)).strftime('%Y-%m-%d %H:%M'), os.path.getctime(filepath)

    def open_external_player(self, event=None):
        sel = self.tree.selection()
        if sel:
            idx = int(sel[-1])
            video_path = self.video_list[idx]["path"]
            try:
                os.startfile(video_path)
            except:
                subprocess.run(['open', video_path])

    def setup_ui(self):
        top_frame = tk.Frame(self.root, pady=10)
        top_frame.pack(fill=tk.X)
        tk.Button(top_frame, text="📁 匯入 (Ctrl+O)", command=self.import_folder).pack(side=tk.LEFT, padx=10)
        tk.Button(top_frame, text="✚ 勾選 (Space)", command=lambda: self.batch_modify_check(True), bg="#e1f5fe").pack(side=tk.LEFT, padx=5)
        tk.Button(top_frame, text="— 取消 (Ctrl+D)", command=lambda: self.batch_modify_check(False), bg="#ffebee").pack(side=tk.LEFT, padx=5)
        tk.Button(top_frame, text="🌓 反轉 (Ctrl+I)", command=self.inverse_batch_selection).pack(side=tk.LEFT, padx=5)
        tk.Button(top_frame, text="🗑 刪除 (Del)", command=self.delete_selected, fg="#cc0000").pack(side=tk.LEFT, padx=5)
        tk.Button(top_frame, text="🛑 強制結束", command=lambda: os._exit(0), bg="#ff4d4d", fg="white").pack(side=tk.RIGHT, padx=10)

        self.paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True, padx=10)

        list_frame = tk.Frame(self.paned)
        self.paned.add(list_frame, weight=1)
        self.columns = ("check", "name", "ratio", "fps", "date", "size", "duration")
        self.tree = ttk.Treeview(list_frame, columns=self.columns, show='headings', selectmode="extended")
        display_names = {"check": "V", "name": "檔名", "ratio": "比例", "fps": "影格率 (FPS)", "date": "拍攝日期", "size": "大小", "duration": "長度"}
        for col in self.columns:
            self.tree.heading(col, text=display_names[col], command=lambda c=col: self.sort_column(c))
        self.tree.column("check", width=30, anchor="center")
        self.tree.column("fps", width=80, anchor="center")
        self.tree.column("name", width=150, anchor="w")
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        self.player_container = tk.LabelFrame(self.paned, text=" 影片預覽 ", bg="#000000", fg="#ffffff")
        self.paned.add(self.player_container, weight=4)
        self.canvas = tk.Label(self.player_container, bg="black")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        ctrl_bar = tk.Frame(self.player_container, bg="#222", pady=5)
        ctrl_bar.pack(fill=tk.X)
        tk.Button(ctrl_bar, text="⏹", command=self.stop_video, width=3).pack(side=tk.LEFT, padx=2)
        self.btn_play = tk.Button(ctrl_bar, text="▶", command=self.toggle_play, width=5, font=("Arial", 10, "bold"))
        self.btn_play.pack(side=tk.LEFT, padx=5)
        tk.Button(ctrl_bar, text="🖥 外部開啟", command=self.open_external_player, bg="#424242", fg="white", width=10).pack(side=tk.LEFT, padx=10)
        self.seek_slider = ttk.Scale(ctrl_bar, from_=0, to=100, orient=tk.HORIZONTAL, command=self.on_seek)
        self.seek_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)

        bottom_frame = tk.LabelFrame(self.root, text=" 任務狀態 ", padx=15, pady=5)
        bottom_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Checkbutton(bottom_frame, text="🔧 音訊標準化", variable=self.audio_std_var, fg="#d32f2f").pack(side=tk.LEFT)
        tk.Checkbutton(bottom_frame, text="⚡ 快速拼接 (不轉碼, 需規格一致)", variable=self.fast_mode_var, fg="#f57c00").pack(side=tk.LEFT, padx=20)
        self.status_label = tk.Label(bottom_frame, text="準備就緒", fg="#0066cc", font=("Arial", 10, "bold"))
        self.status_label.pack(side=tk.LEFT, padx=20)
        self.gpu_label = tk.Label(bottom_frame, text="GPU: 0%", fg="#28a745")
        self.gpu_label.pack(side=tk.RIGHT)

        self.prog_bar = ttk.Progressbar(self.root, orient=tk.HORIZONTAL, mode='determinate')
        self.prog_bar.pack(fill=tk.X, padx=10)
        self.total_info = tk.Label(self.root, text="已選長度: 00:00:00")
        self.total_info.pack(pady=2)

        btn_container = tk.Frame(self.root)
        btn_container.pack(fill=tk.X, padx=10, pady=10)

        self.start_btn = tk.Button(btn_container, text="🚀 影片拼接 (Ctrl+Enter)",
                                   command=self.run_process, bg="#28a745", fg="white",
                                   font=("Arial", 11, "bold"), height=2)
        self.start_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        self.audio_fmt_var = tk.StringVar(value="MP3 (320k)")
        self.audio_fmt_menu = ttk.Combobox(btn_container, textvariable=self.audio_fmt_var,
                                           width=12, state="readonly", font=("Arial", 10))
        self.audio_fmt_menu['values'] = ("MP3 (320k)", "MP3 (192k)", "WAV (無損)")
        self.audio_fmt_menu.pack(side=tk.LEFT, padx=5, ipady=7)

        self.audio_btn = tk.Button(btn_container, text="🎵 純音訊拼接",
                                   command=self.run_audio_process, bg="#007bff", fg="white",
                                   font=("Arial", 11, "bold"), height=2)
        self.audio_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))

    def import_folder(self):
        folder = filedialog.askdirectory()
        if not folder:
            return

        video_exts = ('.mp4', '.mov', '.avi', '.ts', '.mkv')
        audio_exts = ('.mp3', '.wav', '.m4a', '.flac', '.aac')

        for f in os.listdir(folder):
            f_lower = f.lower()
            if f_lower.endswith(video_exts) or f_lower.endswith(audio_exts):
                path = os.path.join(folder, f)
                cap = cv2.VideoCapture(path)

                w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                fps = round(cap.get(cv2.CAP_PROP_FPS), 2)
                frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)

                if fps <= 0 or frame_count <= 0:
                    ratio = "Audio"
                    fps = 0
                    dur = self.get_audio_duration(path)
                else:
                    ratio = self.get_ratio(w, h)
                    dur = frame_count / fps

                cap.release()

                date_str, ts = self.get_video_shooting_date(path)
                idx = len(self.video_list)

                v_data = {
                    "check": False,
                    "name": f,
                    "path": path,
                    "duration": dur,
                    "ratio": ratio,
                    "fps": fps,
                    "size": round(os.path.getsize(path) / (1024 * 1024), 2),
                    "date": date_str,
                    "timestamp": ts
                }
                self.video_list.append(v_data)

                self.tree.insert("", "end", iid=idx, values=(
                    "▢", f, ratio, f"{fps if fps > 0 else '-'}",
                    date_str, f"{v_data['size']}MB", str(timedelta(seconds=int(dur)))
                ))
        self.update_total_display()

    def get_audio_duration(self, filepath):
        cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', filepath]
        try:
            output = subprocess.check_output(cmd, shell=True).decode().strip()
            return float(output) if output else 0
        except:
            return 0

    def update_single_row(self, idx):
        v = self.video_list[idx]
        ck = "▣" if v["check"] else "▢"
        self.tree.item(idx, values=(ck, v["name"], v["ratio"], v["fps"], v["date"], f"{v['size']}MB", str(timedelta(seconds=int(v['duration'])))))

    def ffmpeg_task(self, videos, output):
        list_file = f"task_list_{int(time.time())}.txt"
        is_fast = self.fast_mode_var.get()
        try:
            with open(list_file, "w", encoding="utf-8") as f:
                for v in videos:
                    safe_p = v['path'].replace('\\', '/').replace("'", "'\\''")
                    f.write(f"file '{safe_p}'\n")
            if is_fast:
                cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', list_file, '-c', 'copy', '-movflags', '+faststart', output]
            else:
                cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', list_file, '-c:v', 'libx264', '-preset', 'fast', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', output]
            proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, universal_newlines=True, encoding='utf-8')
            for line in proc.stderr:
                m = re.search(r"time=(\d{2}:\d{2}:\d{2}.\d{2})", line)
                if m:
                    self.status_label.config(text=f"處理中：{m.group(1)}")
                    self.root.update_idletasks()
            proc.wait()
            if os.path.exists(output) and os.path.getsize(output) > 0:
                messagebox.showinfo("完成", f"拼接成功！模式：{'快速' if is_fast else '穩定'}")
            else:
                messagebox.showerror("失敗", "輸出失敗，請確認規格是否一致。")
        except Exception as e:
            messagebox.showerror("錯誤", str(e))
        finally:
            if os.path.exists(list_file):
                os.remove(list_file)
            self.start_btn.config(state="normal")
            self.status_label.config(text="準備就緒")

    def run_process(self):
        selected = [v for v in self.video_list if v["check"]]
        if len(selected) < 2:
            return messagebox.showwarning("提示", "請選至少兩個影片")
        out = filedialog.asksaveasfilename(defaultextension=".mp4")
        if out:
            self.start_btn.config(state="disabled")
            threading.Thread(target=self.ffmpeg_task, args=(selected, out), daemon=True).start()

    def run_audio_process(self):
        selected = [v for v in self.video_list if v["check"]]
        if len(selected) < 2:
            return messagebox.showwarning("提示", "請選至少兩個影片提取聲音")
        fmt_choice = self.audio_fmt_var.get()
        ext = ".wav" if "WAV" in fmt_choice else ".mp3"
        out = filedialog.asksaveasfilename(defaultextension=ext, filetypes=[("Audio File", f"*{ext}")])
        if out:
            self.audio_btn.config(state="disabled")
            threading.Thread(target=self.ffmpeg_audio_task, args=(selected, out, fmt_choice), daemon=True).start()

    def ffmpeg_audio_task(self, videos, output, fmt_choice):
        list_file = f"audio_list_{int(time.time())}.txt"
        is_audio_std = self.audio_std_var.get()
        try:
            with open(list_file, "w", encoding="utf-8") as f:
                for v in videos:
                    safe_p = v['path'].replace('\\', '/').replace("'", "'\\''")
                    f.write(f"file '{safe_p}'\n")
            cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', list_file, '-vn']
            if is_audio_std:
                cmd += ['-filter:a', 'loudnorm']
            if "320k" in fmt_choice:
                cmd += ['-c:a', 'libmp3lame', '-b:a', '320k']
            elif "192k" in fmt_choice:
                cmd += ['-c:a', 'libmp3lame', '-b:a', '192k']
            elif "WAV" in fmt_choice:
                cmd += ['-c:a', 'pcm_s16le']
            cmd.append(output)
            proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, universal_newlines=True, encoding='utf-8')
            for line in proc.stderr:
                m = re.search(r"time=(\d{2}:\d{2}:\d{2}.\d{2})", line)
                if m:
                    self.status_label.config(text=f"音訊處理中：{m.group(1)}")
                    self.root.update_idletasks()
            proc.wait()
            if os.path.exists(output) and os.path.getsize(output) > 0:
                messagebox.showinfo("完成", f"音訊拼接完成！\n格式：{fmt_choice}")
            else:
                messagebox.showerror("失敗", "音訊處理發生錯誤。")
        except Exception as e:
            messagebox.showerror("錯誤", str(e))
        finally:
            if os.path.exists(list_file):
                os.remove(list_file)
            self.audio_btn.config(state="normal")
            self.status_label.config(text="準備就緒")

    def sort_column(self, col):
        self.sort_status[col] = not self.sort_status[col]
        rev = self.sort_status[col]
        if col == "name":
            self.video_list.sort(key=lambda x: x["name"].lower(), reverse=rev)
        else:
            self.video_list.sort(key=lambda x: x.get(col, 0), reverse=rev)
        for i in self.tree.get_children():
            self.tree.delete(i)
        for i, v in enumerate(self.video_list):
            ck = "▣" if v["check"] else "▢"
            self.tree.insert("", "end", iid=i, values=(ck, v["name"], v["ratio"], v["fps"], v["date"], f"{v['size']}MB", str(timedelta(seconds=int(v['duration'])))))

    def stop_video(self):
        self.is_playing = False
        self.btn_play.config(text="▶")
        self.show_frame(0)

    def toggle_play(self):
        if not self.current_cap:
            return
        self.is_playing = not self.is_playing
        self.btn_play.config(text="⏸" if self.is_playing else "▶")
        if self.is_playing:
            self.play_loop()

    def play_loop(self):
        if self.is_playing and self.current_cap:
            n = self.current_frame_idx + 1
            if n < self.total_frames:
                self.show_frame(n)
                self.seek_slider.set(n)
                self.root.after(30, self.play_loop)
            else:
                self.is_playing = False
                self.btn_play.config(text="▶")

    def on_tree_select(self, event):
        if self.preview_timer:
            self.root.after_cancel(self.preview_timer)
        self.preview_timer = self.root.after(100, self.delayed_preview)

    def delayed_preview(self):
        sel = self.tree.selection()
        if sel:
            self.load_video(self.video_list[int(sel[-1])]["path"])

    def load_video(self, path):
        if self.current_cap:
            self.current_cap.release()
        self.current_cap = cv2.VideoCapture(path)
        self.total_frames = int(self.current_cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.seek_slider.config(to=max(0, self.total_frames - 1))
        self.show_frame(0)

    def show_frame(self, idx):
        if self.current_cap:
            self.current_cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = self.current_cap.read()
            if ret:
                img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                img.thumbnail((self.canvas.winfo_width(), self.canvas.winfo_height()), Image.Resampling.LANCZOS)
                self.tk_img = ImageTk.PhotoImage(img)
                self.canvas.config(image=self.tk_img)
                self.current_frame_idx = idx

    def on_seek(self, val):
        if not self.is_playing:
            self.show_frame(int(float(val)))

    def update_total_display(self):
        total = sum(v["duration"] for v in self.video_list if v["check"])
        self.total_info.config(text=f"已選長度: {str(timedelta(seconds=int(total)))}")

    def batch_modify_check(self, status):
        for s_id in self.tree.selection():
            idx = int(s_id)
            self.video_list[idx]["check"] = status
            self.update_single_row(idx)
        self.update_total_display()

    def inverse_batch_selection(self):
        for s_id in self.tree.selection():
            idx = int(s_id)
            self.video_list[idx]["check"] = not self.video_list[idx]["check"]
            self.update_single_row(idx)
        self.update_total_display()

    def delete_selected(self):
        sel = sorted([int(i) for i in self.tree.selection()], reverse=True)
        for i in sel:
            self.video_list.pop(i)
            self.tree.delete(i)
        self.update_total_display()

    def bind_shortcuts(self):
        self.root.bind('<Control-o>', lambda e: self.import_folder())
        self.root.bind('<space>', lambda e: self.batch_modify_check(True))
        self.root.bind('<Return>', self.open_external_player)

    def update_gpu_info(self):
        if self.has_gpu:
            try:
                h = pynvml.nvmlDeviceGetHandleByIndex(0)
                u = pynvml.nvmlDeviceGetUtilizationRates(h)
                self.gpu_label.config(text=f"GPU: {u.gpu}%")
            except:
                pass
        self.root.after(1000, self.update_gpu_info)

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoMasterApp(root)
    root.mainloop()
