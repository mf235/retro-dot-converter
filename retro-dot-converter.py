# ================================================
# レトロ風ドット絵変換ツール
# 
# 【必須インストールコマンド】
# pip install --upgrade pillow numpy
# pip install tkinterdnd2
# pip install scikit-learn
# 
# 【任意インストールコマンド (自動背景除去を使う場合のみ)】
# pip install rembg==2.0.59
# pip install onnxruntime==1.19.2
# ================================================

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinterdnd2 import * # Drag&Drop用
from PIL import Image, ImageTk, ImageEnhance, ImageFilter, ImageOps
import numpy as np
import os
import shutil
from datetime import datetime
import re # 自然順ソート用に追加
from sklearn.cluster import MiniBatchKMeans

# === rembgのインストール＆動作チェック ===
try:
    import rembg
    from rembg import remove, new_session
    REMBG_AVAILABLE = True
except ImportError:
    REMBG_AVAILABLE = False
# ====================================

# === 自然順ソート（Natural Sort）用のヘルパー関数 ===
def natural_sort_key(s):
    """ファイル名の中の数字を数値として評価してソートするためのキー関数"""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]
# ==================================================

SUPPORTED_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")

SAVE_FORMAT_BY_EXTENSION = {
    ".png": "PNG",
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".webp": "WEBP",
    ".bmp": "BMP",
    ".gif": "GIF",
}

class RetroConverter:
    def __init__(self, root):
        """GUI初期化"""
        self.root = root
        self.root.title("レトロ風ドット絵変換ツール")

        window_width = 1280
        window_height = 860
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        x_coordinate = (screen_width // 2) - (window_width // 2)
        y_coordinate = (screen_height // 2) - (window_height // 2)
        root.geometry(f"{window_width}x{window_height}+{x_coordinate}+{y_coordinate}")

        self.input_paths = []
        self.output_img = None
        self.input_img_tk = None
        self.output_img_tk = None
        self.preview_after_id = None
        self._auto_preview_running = False
        self.rembg_sessions = {}

        main_frame = tk.Frame(root)
        main_frame.pack(fill="both", expand=True, padx=15, pady=10)

        # ====================== 左エリア ======================
        left_frame = tk.Frame(main_frame, width=650)
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 20))

        tk.Label(left_frame, text="レトロ風ドット絵変換ツール", 
                 font=("メイリオ", 16, "bold"), anchor="w").pack(fill="x", pady=8)

        self.btn_select = tk.Button(left_frame, text="1. 画像を選択 (複数可)", command=self.select_image, width=25, height=2)
        self.btn_select.pack(anchor="w", pady=8)

        self.lbl_input = tk.Label(left_frame, text="入力画像: 未選択", anchor="w")
        self.lbl_input.pack(fill="x", pady=(0, 10))

        preview_area = tk.Frame(left_frame)
        preview_area.pack(pady=10)

        input_frame = tk.LabelFrame(preview_area, text="入力画像", font=("メイリオ", 9))
        input_frame.pack(side="left", padx=15)
        self.input_preview_frame = tk.Frame(input_frame, width=320, height=320, bg="#e8e8e8", relief="sunken", bd=3)
        self.input_preview_frame.pack(padx=10, pady=10)
        self.input_preview_frame.pack_propagate(False)
        self.lbl_input_preview = tk.Label(self.input_preview_frame, bg="#e8e8e8")
        self.lbl_input_preview.place(relx=0.5, rely=0.5, anchor="center")

        output_frame = tk.LabelFrame(preview_area, text="出力プレビュー", font=("メイリオ", 9))
        output_frame.pack(side="left", padx=15)
        self.output_preview_frame = tk.Frame(output_frame, width=320, height=320, bg="#e8e8e8", relief="sunken", bd=3)
        self.output_preview_frame.pack(padx=10, pady=10)
        self.output_preview_frame.pack_propagate(False)
        self.lbl_output_preview = tk.Label(self.output_preview_frame, bg="#e8e8e8")
        self.lbl_output_preview.place(relx=0.5, rely=0.5, anchor="center")
        self.lbl_preview_status = tk.Label(output_frame, text="パラメータ変更で自動プレビューできます", fg="#666666", font=("メイリオ", 8))
        self.lbl_preview_status.pack(pady=(0, 6))

        # ====================== ボタンエリア ======================
        button_frame = tk.Frame(left_frame)
        button_frame.pack(fill="x", pady=20)

        self.var_dnd_auto = tk.BooleanVar(value=False)
        self.chk_dnd_auto = tk.Checkbutton(button_frame, text="✅ ファイルドロップで即時変換", variable=self.var_dnd_auto, font=("メイリオ", 10, "bold"), fg="#333333")
        self.chk_dnd_auto.pack(anchor="w", pady=(0, 5))

        self.var_dnd_folder_overwrite = tk.BooleanVar(value=False)
        self.chk_dnd_folder_overwrite = tk.Checkbutton(
            button_frame,
            text="✅ フォルダの場合は上書きモードで即時変換保存する",
            variable=self.var_dnd_folder_overwrite,
            font=("メイリオ", 10, "bold"),
            fg="#8a3a00"
        )
        self.chk_dnd_folder_overwrite.pack(anchor="w", pady=(0, 5))

        self.var_auto_preview = tk.BooleanVar(value=True)
        self.chk_auto_preview = tk.Checkbutton(
            button_frame,
            text="✅ パラメータ変更で自動プレビュー（保存なし）",
            variable=self.var_auto_preview,
            command=lambda: self.schedule_auto_preview(delay=100),
            font=("メイリオ", 10),
            fg="#333333"
        )
        self.chk_auto_preview.pack(anchor="w", pady=(0, 5))

        filename_frame = tk.Frame(button_frame)
        filename_frame.pack(anchor="w", pady=(0, 10))
        
        tk.Label(filename_frame, text="ファイル名:", font=("メイリオ", 10)).pack(side="left")
        self.var_filename_prefix = tk.StringVar(value="retro")
        tk.Entry(filename_frame, textvariable=self.var_filename_prefix, width=15).pack(side="left", padx=(5, 5))
        
        self.var_filename_num = tk.StringVar(value="001")
        tk.Entry(filename_frame, textvariable=self.var_filename_num, width=5).pack(side="left")

        self.btn_convert = tk.Button(button_frame, text="2. レトロ風に変換して保存！",
                                     command=self.convert, bg="#00FF00", fg="black",
                                     font=("メイリオ", 14, "bold"), width=25, height=4)
        self.btn_convert.pack(side="left", padx=(0, 10))

        # ====================== 右エリア ======================
        right_frame = tk.Frame(main_frame, width=580)
        right_frame.pack(side="right", fill="both", expand=True)

        tk.Label(right_frame, text="設定オプション", font=("メイリオ", 12, "bold"), anchor="w").pack(fill="x", pady=(10, 15))

        # プリセット
        tk.Label(right_frame, text="プリセット", font=("メイリオ", 10), anchor="w").pack(fill="x", pady=(0, 2))
        self.preset_var = tk.StringVar(value="")
        self.preset_combo = ttk.Combobox(right_frame, textvariable=self.preset_var, state="readonly", width=35)
        self.preset_combo['values'] = ("", "PC98", "PC88", "MSX", "MSX2", "MSX2 インターレース")
        self.preset_combo.pack(anchor="w", pady=2)
        self.preset_combo.bind("<<ComboboxSelected>>", self.apply_preset)

        tk.Label(right_frame, text="出力サイズ", font=("メイリオ", 10), anchor="w").pack(fill="x", pady=(8,0))
        self.size_var = tk.StringVar(value="640x400")
        self.size_combo = ttk.Combobox(right_frame, textvariable=self.size_var, state="readonly", width=35)
        self.size_combo['values'] = ("現状維持", "80x80", "128x72", "128x96", "128x128",
        "256x256", "256x192", "256x144",
        "320x180", "320x240", "320x320",
        "480x270", "480x360", "480x480",
        "512x212", "512x424",
        "640x200", "640x360", "640x400", "640x480", "640x640",
        "1024x768", "1280x720", "1920x1080")
        self.size_combo.pack(anchor="w", pady=2)

        tk.Label(right_frame, text="色数", font=("メイリオ", 10), anchor="w").pack(fill="x", pady=(10,0))
        self.colors_var = tk.StringVar(value="8")
        self.colors_combo = ttk.Combobox(right_frame, textvariable=self.colors_var, state="readonly", width=35)
        self.colors_combo['values'] = ("4", "8", "16", "32", "64", "128", "256", "512")
        self.colors_combo.pack(anchor="w", pady=2)

        tk.Label(right_frame, text="保存形式", font=("メイリオ", 10), anchor="w").pack(fill="x", pady=(10,0))
        self.format_var = tk.StringVar(value="png")
        self.format_combo = ttk.Combobox(right_frame, textvariable=self.format_var, state="readonly", width=35)
        self.format_combo['values'] = ("png", "gif", "jpg")
        self.format_combo.pack(anchor="w", pady=2)

        tk.Label(right_frame, text="余白/背景処理", font=("メイリオ", 10), anchor="w").pack(fill="x", pady=(10,0))
        self.bg_var = tk.StringVar(value="切り抜き (crop) ※縦横比維持・サイズ可変")
        self.bg_combo = ttk.Combobox(right_frame, textvariable=self.bg_var, state="readonly", width=35)
        self.bg_combo['values'] = ("拡大 (stretch)", "切り抜き (crop) ※縦横比維持・サイズ可変", "透過 (transparent)", "緑 (#00FF00)", "黒 (#000000)")
        self.bg_combo.pack(anchor="w", pady=2)

        tk.Label(right_frame, text="リサイズ方法", font=("メイリオ", 10), anchor="w").pack(fill="x", pady=(10,0))
        self.resize_var = tk.StringVar(value="Bicubic (高品質・滑らか)")
        self.resize_combo = ttk.Combobox(right_frame, textvariable=self.resize_var, state="readonly", width=35)
        self.resize_combo['values'] = ("Nearest", "Bilinear", "Bicubic (高品質・滑らか)")
        self.resize_combo.pack(anchor="w", pady=2)

        # === rembg依存エリア ===
        lbl_rembg = tk.Label(right_frame, text="rembg モデル選択", font=("メイリオ", 10), anchor="w")
        lbl_rembg.pack(fill="x", pady=(10,0))
        self.model_var = tk.StringVar(value="isnet-anime")
        self.model_combo = ttk.Combobox(right_frame, textvariable=self.model_var, state="readonly", width=35)
        self.model_combo['values'] = ("isnet-anime", "u2net_human_seg", "u2net", "u2netp", "silueta", "u2net_cloth_seg", "isnet-general-use")
        self.model_combo.pack(anchor="w", pady=2)

        self.var_auto_bg = tk.BooleanVar(value=False)
        bg_chk_text = "✅ 自動背景除去（選択したモデルを使用）" if REMBG_AVAILABLE else "❌ 自動背景除去（rembg未インストールの為無効）"
        self.chk_auto_bg = tk.Checkbutton(right_frame, text=bg_chk_text, variable=self.var_auto_bg, font=("メイリオ", 10), anchor="w")
        self.chk_auto_bg.pack(fill="x", pady=6)

        # rembgがない場合は無効化
        if not REMBG_AVAILABLE:
            self.model_combo.config(state="disabled")
            self.chk_auto_bg.config(state="disabled", fg="gray")
            lbl_rembg.config(fg="gray")
        # ====================

        self.var_pre_dot = tk.BooleanVar(value=True)
        self.chk_pre_dot = tk.Checkbutton(right_frame, text="✅ 事前ドット化（高解像度画像を先に低解像度化）", variable=self.var_pre_dot, font=("メイリオ", 10), anchor="w")
        self.chk_pre_dot.pack(fill="x", pady=4)

        self.var_outline = tk.BooleanVar(value=False)
        self.chk_outline = tk.Checkbutton(right_frame, text="✅ 輪郭線を黒に統一（レトロ風アウトライン強化）", variable=self.var_outline, font=("メイリオ", 10), anchor="w")
        self.chk_outline.pack(fill="x", pady=4)

        tk.Label(right_frame, text="ドット化強調（縮小→拡大）", font=("メイリオ", 10), anchor="w").pack(fill="x", pady=(12,0))
        self.var_dot_boost = tk.StringVar(value="なし")
        self.dot_combo = ttk.Combobox(right_frame, textvariable=self.var_dot_boost, state="readonly", width=35)
        self.dot_combo['values'] = ("なし", "10%", "20%", "30%", "40%", "50%", "60%", "70%", "80%", "90%")
        self.dot_combo.pack(anchor="w", pady=2)
        tk.Label(right_frame, text="※小さい％ほど強いドット強調（10%が最強）", fg="red", font=("メイリオ", 9), anchor="w").pack(fill="x")

        self.var_anti_alias = tk.BooleanVar(value=True)
        self.chk_anti_alias = tk.Checkbutton(right_frame, text="✅ アンチエイリアス（輪郭部分のみ）", variable=self.var_anti_alias, font=("メイリオ", 10), anchor="w")
        self.chk_anti_alias.pack(fill="x", pady=6)

        # ====================== 色ずれ（色収差）オプション ======================
        self.var_chromatic = tk.BooleanVar(value=False)
        self.chk_chromatic = tk.Checkbutton(right_frame, text="✅ 色ずれ（色収差）効果を追加", variable=self.var_chromatic, font=("メイリオ", 10), anchor="w")
        self.chk_chromatic.pack(fill="x", pady=(4, 0))

        chromatic_frame = tk.Frame(right_frame)
        chromatic_frame.pack(fill="x", padx=25, pady=2)
        tk.Label(chromatic_frame, text="ずれの強度 (ピクセル):", font=("メイリオ", 9)).pack(side="left")
        self.var_chromatic_intensity = tk.StringVar(value="2")
        tk.Entry(chromatic_frame, textvariable=self.var_chromatic_intensity, width=5, justify="center").pack(side="left", padx=5)

        # ====================== 実験用オプション ======================
        self.var_exp_skin_protect = tk.BooleanVar(value=False)
        self.chk_exp_skin_protect = tk.Checkbutton(right_frame, text="✅ 肌の黒ドット撲滅（事前バリア＋事後補正）", variable=self.var_exp_skin_protect, font=("メイリオ", 10), anchor="w")
        self.chk_exp_skin_protect.pack(fill="x", pady=(4, 0))

        param_frame = tk.Frame(right_frame)
        param_frame.pack(fill="x", padx=25, pady=2)
        
        tk.Label(param_frame, text="1:事前バリア [", font=("メイリオ", 9)).pack(side="left")
        self.var_pre_thresh = tk.StringVar(value="130")
        tk.Entry(param_frame, textvariable=self.var_pre_thresh, width=4, justify="center").pack(side="left")
        
        tk.Label(param_frame, text="]   2:事後補正 [", font=("メイリオ", 9)).pack(side="left")
        self.var_post_thresh = tk.StringVar(value="45")
        tk.Entry(param_frame, textvariable=self.var_post_thresh, width=4, justify="center").pack(side="left")
        
        tk.Label(param_frame, text="]", font=("メイリオ", 9)).pack(side="left")

        # ====================== 自動プレビュー設定 ======================
        self.setup_auto_preview_bindings()

        # ====================== Drag & Drop 設定 ======================
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind('<<Drop>>', self.drop_image)

    # ====================== 透過画像処理メソッド ======================
    def load_image_with_bg(self, path, for_preview=False):
        img = Image.open(path).convert("RGBA")
        
        if for_preview:
            bg_color = (232, 232, 232, 255) 
        else:
            bg_mode = self.bg_var.get()
            if "緑" in bg_mode:
                bg_color = (0, 255, 0, 255)
            elif "黒" in bg_mode:
                bg_color = (0, 0, 0, 255)
            else:
                bg_color = (0, 0, 0, 0)

        bg = Image.new("RGBA", img.size, bg_color)
        bg.alpha_composite(img)
        return bg.convert("RGB")

    # ====================== Drag & Drop 処理 ======================
    def drop_image(self, event):
        dropped_paths = [os.path.abspath(p) for p in self.root.tk.splitlist(event.data)]
        folder_paths = [p for p in dropped_paths if os.path.isdir(p)]
        direct_files = [p for p in dropped_paths if os.path.isfile(p) and self.is_supported_image_file(p)]

        # フォルダ上書きモード: フォルダD&D時だけ、サブフォルダ込みで即時変換・上書き保存
        if folder_paths and getattr(self, "var_dnd_folder_overwrite", None) and self.var_dnd_folder_overwrite.get():
            folder_paths.sort(key=lambda x: natural_sort_key(os.path.basename(x)))
            direct_files.sort(key=lambda x: natural_sort_key(os.path.basename(x)))
            folder_image_paths = self.collect_image_files_from_folders(folder_paths)
            overwrite_paths = self.unique_paths(direct_files + folder_image_paths)

            if not overwrite_paths:
                messagebox.showwarning("エラー", "フォルダ内に有効な画像ファイルがありません")
                return

            self.input_paths = overwrite_paths
            self.update_input_preview(overwrite_paths[0])

            folder_label = os.path.basename(folder_paths[0]) or folder_paths[0]
            if len(folder_paths) == 1:
                self.lbl_input.config(text=f"入力フォルダ: {folder_label} / 画像 {len(overwrite_paths)}件")
            else:
                self.lbl_input.config(text=f"入力フォルダ: {folder_label} ほか {len(folder_paths)-1}件 / 画像 {len(overwrite_paths)}件")

            self.btn_convert.config(state="normal")
            if hasattr(self, "lbl_preview_status"):
                self.lbl_preview_status.config(text="フォルダ上書き変換待ち...")
            self.root.after(100, lambda: self.convert_overwrite_paths(overwrite_paths, folder_paths))
            return

        valid_files = direct_files

        if not valid_files:
            messagebox.showwarning("エラー", "有効な画像ファイルがありません")
            return

        # 自然順ソート（ファイル名の数字を数値として解釈して並び替え）
        valid_files.sort(key=lambda x: natural_sort_key(os.path.basename(x)))

        self.input_paths = valid_files
        
        if len(valid_files) == 1:
            self.lbl_input.config(text=f"入力画像: {os.path.basename(valid_files[0])}")
        else:
            self.lbl_input.config(text=f"入力画像: {os.path.basename(valid_files[0])} ほか {len(valid_files)-1}件")
        
        self.update_input_preview(valid_files[0])

        self.btn_convert.config(state="normal")
        self.schedule_auto_preview(delay=100)

        if self.var_dnd_auto.get():
            self.root.after(100, self.convert) 

    def is_supported_image_file(self, path):
        return os.path.splitext(path)[1].lower() in SUPPORTED_IMAGE_EXTENSIONS

    def unique_paths(self, paths):
        """同じ画像が二重指定された場合に、順序を保って1回だけ処理する。"""
        seen = set()
        unique = []
        for path in paths:
            key = os.path.normcase(os.path.abspath(path))
            if key in seen:
                continue
            seen.add(key)
            unique.append(path)
        return unique

    def collect_image_files_from_folders(self, folder_paths):
        """D&Dされたフォルダ以下の画像をサブフォルダ込みで集める。バックアップフォルダは除外する。"""
        image_paths = []
        for folder in folder_paths:
            for current_dir, dir_names, file_names in os.walk(folder):
                dir_names[:] = [d for d in dir_names if not d.startswith("_backup.")]
                file_names.sort(key=natural_sort_key)
                for file_name in file_names:
                    path = os.path.join(current_dir, file_name)
                    if self.is_supported_image_file(path):
                        image_paths.append(path)
        image_paths.sort(key=lambda x: natural_sort_key(os.path.normcase(os.path.abspath(x))))
        return image_paths

    def update_input_preview(self, path):
        preview = self.load_image_with_bg(path, for_preview=True)
        preview.thumbnail((300, 300))
        self.input_img_tk = ImageTk.PhotoImage(preview)
        self.lbl_input_preview.config(image=self.input_img_tk)

    # ====================== 画像選択処理 ======================
    def select_image(self):
        files = filedialog.askopenfilenames(
            title="変換したい画像を選んでね（複数可）",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.webp *.bmp")]
        )
        if not files:
            return
            
        # 自然順ソート（ファイル名の数字を数値として解釈して並び替え）
        self.input_paths = sorted(list(files), key=lambda x: natural_sort_key(os.path.basename(x)))
        
        if len(self.input_paths) == 1:
            self.lbl_input.config(text=f"入力画像: {os.path.basename(self.input_paths[0])}")
        else:
            self.lbl_input.config(text=f"入力画像: {os.path.basename(self.input_paths[0])} ほか {len(self.input_paths)-1}件")
        
        self.update_input_preview(self.input_paths[0])

        self.btn_convert.config(state="normal")
        self.schedule_auto_preview(delay=100)

    # ====================== プリセット ======================
    def apply_preset(self, event=None):
        preset = self.preset_var.get()
        
        if not preset:
            self.size_combo.config(state="readonly")
            self.colors_combo.config(state="readonly")
            self.schedule_auto_preview(delay=100)
            return

        if preset == "PC98":
            self.size_var.set("640x400")
            self.colors_var.set("16")
        elif preset == "PC88":
            self.size_var.set("640x200")
            self.colors_var.set("8")
        elif preset == "MSX":
            self.size_var.set("256x192")
            self.colors_var.set("16")
        elif preset == "MSX2":
            self.size_var.set("512x212")
            self.colors_var.set("16")
        elif preset == "MSX2 インターレース":
            self.size_var.set("512x424")
            self.colors_var.set("16")

        self.size_combo.config(state="disabled")
        self.colors_combo.config(state="disabled")
        self.schedule_auto_preview(delay=100)

    # ====================== 輪郭線処理 ======================
    def enhance_outline_weak(self, img):
        edges = img.filter(ImageFilter.FIND_EDGES).convert("L")
        thick = edges.filter(ImageFilter.MaxFilter(3))
        mask = thick.point(lambda x: 0 if x < 120 else 255, "1")

        mask_array = np.array(mask)
        border = 2
        mask_array[0:border, :] = 0
        mask_array[-border:, :] = 0
        mask_array[:, 0:border] = 0
        mask_array[:, -border:] = 0
        mask = Image.fromarray(mask_array)
        black = Image.new("RGB", img.size, (0, 0, 0))
        result = Image.composite(black, img.convert("RGB"), mask)
        return result.convert("RGB")

    # ====================== 色収差（色ずれ）処理 ======================
    def apply_chromatic_aberration(self, img, intensity):
        if intensity <= 0:
            return img
        
        arr = np.array(img)
        shifted = np.copy(arr)
        
        if intensity >= arr.shape[1]:
            return img

        shifted[:, :-intensity, 0] = arr[:, intensity:, 0]
        shifted[:, intensity:, 2] = arr[:, :-intensity, 2]
        
        return Image.fromarray(shifted, mode=img.mode)

    # ====================== 自動プレビュー関連 ======================
    def setup_auto_preview_bindings(self):
        """パラメータ変更時に保存なしプレビューを遅延実行する"""
        vars_to_trace = [
            self.preset_var,
            self.size_var,
            self.colors_var,
            self.format_var,
            self.bg_var,
            self.resize_var,
            self.model_var,
            self.var_auto_bg,
            self.var_pre_dot,
            self.var_outline,
            self.var_dot_boost,
            self.var_anti_alias,
            self.var_chromatic,
            self.var_chromatic_intensity,
            self.var_exp_skin_protect,
            self.var_pre_thresh,
            self.var_post_thresh,
        ]

        for var in vars_to_trace:
            try:
                var.trace_add("write", lambda *args: self.schedule_auto_preview())
            except Exception:
                pass

    def schedule_auto_preview(self, *args, delay=500):
        """入力中に何度も変換しないよう、少し待ってから1回だけプレビューする"""
        if not getattr(self, "var_auto_preview", None) or not self.var_auto_preview.get():
            if hasattr(self, "lbl_preview_status"):
                self.lbl_preview_status.config(text="自動プレビュー: OFF")
            return

        if not self.input_paths:
            return

        if self.preview_after_id is not None:
            try:
                self.root.after_cancel(self.preview_after_id)
            except Exception:
                pass

        if hasattr(self, "lbl_preview_status"):
            self.lbl_preview_status.config(text="プレビュー更新待ち...")

        self.preview_after_id = self.root.after(delay, self.preview_current_settings)

    def preview_current_settings(self):
        """現在の設定で1枚目だけプレビューする。保存と連番更新はしない"""
        self.preview_after_id = None

        if self._auto_preview_running or not self.input_paths:
            return

        self._auto_preview_running = True
        try:
            if hasattr(self, "lbl_preview_status"):
                self.lbl_preview_status.config(text="プレビュー更新中...")

            preview_path = self.input_paths[0]
            self.output_img = self.process_image(preview_path, show_rembg_notice=False)
            self.show_output_preview(self.output_img)

            if hasattr(self, "lbl_preview_status"):
                self.lbl_preview_status.config(
                    text=f"自動プレビュー: {os.path.basename(preview_path)} / 保存なし"
                )

        except Exception as e:
            if hasattr(self, "lbl_preview_status"):
                self.lbl_preview_status.config(text=f"プレビュー不可: {str(e)}")
        finally:
            self._auto_preview_running = False

    def show_output_preview(self, img):
        """出力画像をプレビュー枠に表示する"""
        preview_out = img.copy()
        if preview_out.mode in ('RGBA', 'LA'):
            bg = Image.new("RGBA", preview_out.size, (232, 232, 232, 255))
            bg.alpha_composite(preview_out)
            preview_out = bg.convert("RGB")

        preview_out.thumbnail((300, 300))
        self.output_img_tk = ImageTk.PhotoImage(preview_out)
        self.lbl_output_preview.config(image=self.output_img_tk)

    def get_rembg_session(self):
        """rembgセッションをモデルごとにキャッシュする"""
        model_name = self.model_var.get()
        if model_name not in self.rembg_sessions:
            self.rembg_sessions[model_name] = new_session(model_name)
        return self.rembg_sessions[model_name]

    # ====================== 変換コア処理 ======================
    def process_image(self, path, show_rembg_notice=False):
        """画像1枚を現在の設定で変換する。保存はしない"""
        orig_img_raw = Image.open(path)
        has_alpha = orig_img_raw.mode in ('RGBA', 'LA') or (orig_img_raw.mode == 'P' and 'transparency' in orig_img_raw.info)
        if has_alpha:
            orig_alpha = orig_img_raw.convert("RGBA").getchannel('A')

        img = self.load_image_with_bg(path, for_preview=False)

        mode = self.bg_var.get()
        resample = Image.BICUBIC if "Bicubic" in self.resize_var.get() else \
                   Image.BILINEAR if "Bilinear" in self.resize_var.get() else Image.NEAREST

        size_str = self.size_var.get()
        if size_str == "現状維持":
            target_w, target_h = img.size
        else:
            if "(" in size_str:
                size_str = size_str.split()[0]
            target_w, target_h = map(int, size_str.split('x'))

        if mode == "拡大 (stretch)":
            img = img.resize((target_w, target_h), resample)
        elif mode == "切り抜き (crop) ※縦横比維持・サイズ可変":
            orig_w, orig_h = img.size
            scale = min(target_w / orig_w, target_h / orig_h)
            new_w = int(orig_w * scale)
            new_h = int(orig_h * scale)
            img = img.resize((new_w, new_h), resample)
        else:
            if self.var_pre_dot.get():
                orig_w, orig_h = img.size
                scale = min(target_w / orig_w, target_h / orig_h)
                new_w = int(orig_w * scale)
                new_h = int(orig_h * scale)
                img = img.resize((new_w, new_h), resample)

        if self.var_outline.get():
            img = self.enhance_outline_weak(img)

        if self.var_anti_alias.get() and self.var_outline.get():
            img = self.apply_anti_alias_to_outline(img)

        if self.var_dot_boost.get() != "なし":
            img = self.dot_boost(img, self.var_dot_boost.get())

        if getattr(self, "var_exp_skin_protect", None) and self.var_exp_skin_protect.get():
            edges = img.filter(ImageFilter.FIND_EDGES).convert("L")
            smoothed = img.filter(ImageFilter.SMOOTH_MORE).filter(ImageFilter.SMOOTH_MORE)
            edge_mask = edges.point(lambda x: 255 if x > 20 else 0, "1")
            img = Image.composite(img, smoothed, edge_mask)

        colors = int(self.colors_var.get())
        preset = self.preset_var.get()
        skin_protect = getattr(self, "var_exp_skin_protect", None) and self.var_exp_skin_protect.get()

        try:
            pre_thresh = float(self.var_pre_thresh.get())
        except ValueError:
            pre_thresh = 130.0

        try:
            post_thresh = float(self.var_post_thresh.get())
        except ValueError:
            post_thresh = 45.0

        output_img = self.bayer_ordered_dither(
            img,
            colors,
            preset,
            skin_protect=skin_protect,
            pre_thresh=pre_thresh,
            post_thresh=post_thresh
        )

        if "透過" in self.bg_var.get() and has_alpha:
            final_alpha = orig_alpha.resize(output_img.size, resample)
            output_img.putalpha(final_alpha)

        # --- rembgが有効かつチェックされている場合のみ処理 ---
        if REMBG_AVAILABLE and getattr(self, "var_auto_bg", None) and self.var_auto_bg.get():
            if show_rembg_notice:
                messagebox.showinfo("処理中", f"自動背景除去を実行しています...\nモデル: {self.model_var.get()}")
            session = self.get_rembg_session()
            output_img = remove(output_img, session=session)

        # --- 色ずれ（色収差）処理を追加 ---
        if getattr(self, "var_chromatic", None) and self.var_chromatic.get():
            try:
                intensity = int(self.var_chromatic_intensity.get())
                output_img = self.apply_chromatic_aberration(output_img, intensity)
            except ValueError:
                pass

        return output_img

    def make_backup_root(self):
        """スクリプトと同じフォルダに _backup.日付 フォルダを作る。"""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_root = os.path.join(script_dir, f"_backup.{timestamp}")

        suffix = 2
        unique_backup_root = backup_root
        while os.path.exists(unique_backup_root):
            unique_backup_root = f"{backup_root}_{suffix}"
            suffix += 1

        os.makedirs(unique_backup_root, exist_ok=True)
        return unique_backup_root

    def backup_path_for_source(self, source_path, folder_roots, backup_root):
        """元画像の配置をなるべく保ったバックアップ先パスを返す。"""
        source_abs = os.path.abspath(source_path)
        matching_root = None

        for root in sorted(folder_roots, key=len, reverse=True):
            root_abs = os.path.abspath(root)
            try:
                common = os.path.commonpath([source_abs, root_abs])
            except ValueError:
                continue
            if common == root_abs:
                matching_root = root_abs
                break

        if matching_root:
            root_name = os.path.basename(os.path.normpath(matching_root)) or "dropped_folder"
            relative_path = os.path.relpath(source_abs, matching_root)
            backup_path = os.path.join(backup_root, root_name, relative_path)
        else:
            backup_path = os.path.join(backup_root, "_files", os.path.basename(source_abs))

        return self.make_unique_path(backup_path)

    def make_unique_path(self, path):
        """同名バックアップがある場合だけ _2, _3... を付ける。"""
        if not os.path.exists(path):
            return path

        base, ext = os.path.splitext(path)
        index = 2
        while True:
            candidate = f"{base}_{index}{ext}"
            if not os.path.exists(candidate):
                return candidate
            index += 1

    def save_converted_over_original(self, img, source_path):
        """変換後画像を元ファイルと同じ拡張子・同じ場所に安全に上書き保存する。"""
        ext = os.path.splitext(source_path)[1].lower()
        save_format = SAVE_FORMAT_BY_EXTENSION.get(ext)
        if not save_format:
            raise ValueError(f"未対応の保存形式です: {ext}")

        save_img = img
        if save_format in ("JPEG", "BMP"):
            save_img = img.convert("RGB")

        temp_path = f"{source_path}.retro_tmp{ext}"
        try:
            save_kwargs = {}
            if save_format == "JPEG":
                save_kwargs.update({"quality": 95, "subsampling": 0})
            elif save_format == "WEBP":
                save_kwargs.update({"quality": 95})

            save_img.save(temp_path, format=save_format, **save_kwargs)
            os.replace(temp_path, source_path)
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    def convert_overwrite_paths(self, image_paths, folder_roots):
        """フォルダD&D用。元画像をバックアップしてから、同じ場所へ上書き保存する。"""
        if not image_paths:
            return

        backup_root = self.make_backup_root()
        success_count = 0
        error_messages = []
        last_success_path = None

        try:
            for index, path in enumerate(image_paths, start=1):
                if hasattr(self, "lbl_preview_status"):
                    self.lbl_preview_status.config(text=f"フォルダ上書き変換中... {index}/{len(image_paths)}")
                    self.root.update_idletasks()

                try:
                    backup_path = self.backup_path_for_source(path, folder_roots, backup_root)
                    os.makedirs(os.path.dirname(backup_path), exist_ok=True)
                    shutil.copy2(path, backup_path)

                    output_img = self.process_image(path, show_rembg_notice=False)
                    self.save_converted_over_original(output_img, path)

                    self.output_img = output_img
                    last_success_path = path
                    success_count += 1

                except Exception as item_error:
                    error_messages.append(f"{os.path.basename(path)}: {item_error}")

            if last_success_path:
                self.update_input_preview(last_success_path)
                self.show_output_preview(self.output_img)

            if hasattr(self, "lbl_preview_status"):
                self.lbl_preview_status.config(text=f"フォルダ上書き保存済み: {success_count}/{len(image_paths)}件")

            if error_messages:
                preview_errors = "\n".join(error_messages[:8])
                if len(error_messages) > 8:
                    preview_errors += f"\n...ほか {len(error_messages)-8}件"
                messagebox.showwarning(
                    "フォルダ上書き変換 完了（一部エラー）",
                    f"成功: {success_count}件 / 失敗: {len(error_messages)}件\n"
                    f"バックアップ: {backup_root}\n\n"
                    f"{preview_errors}"
                )
            else:
                messagebox.showinfo(
                    "フォルダ上書き変換完了",
                    f"{success_count}件の画像を上書き保存したぜ！\n"
                    f"バックアップ: {backup_root}"
                )

        except Exception as e:
            messagebox.showerror("エラー", f"フォルダ上書き変換中にエラーが発生しました:\n{str(e)}")

    # ====================== メイン変換処理 (複数ファイル対応) ======================
    def convert(self):
        if not self.input_paths:
            return

        success_count = 0
        filename = ""

        try:
            for path in self.input_paths:
                self.output_img = self.process_image(path, show_rembg_notice=(success_count == 0))

                # --- 自動保存処理 ---
                ext = self.format_var.get().lower()
                save_img = self.output_img.convert("RGB") if ext == "jpg" else self.output_img

                prefix = self.var_filename_prefix.get()
                num_str = self.var_filename_num.get()
                filename = f"{prefix}{num_str}.{ext}"

                save_dir = os.path.dirname(os.path.abspath(__file__))
                save_path = os.path.join(save_dir, filename)

                save_img.save(save_path)

                try:
                    num = int(num_str)
                    next_num = num + 1
                    self.var_filename_num.set(str(next_num).zfill(len(num_str)))
                except ValueError:
                    pass

                success_count += 1

            last_path = self.input_paths[-1]
            preview_in = self.load_image_with_bg(last_path, for_preview=True)
            preview_in.thumbnail((300, 300))
            self.input_img_tk = ImageTk.PhotoImage(preview_in)
            self.lbl_input_preview.config(image=self.input_img_tk)

            self.show_output_preview(self.output_img)

            if hasattr(self, "lbl_preview_status"):
                self.lbl_preview_status.config(text=f"保存済みプレビュー: {os.path.basename(last_path)}")

            if len(self.input_paths) == 1:
                messagebox.showinfo("変換＆保存完了", f"{self.output_img.size[0]}x{self.output_img.size[1]} 完了！\n{filename} を保存したぜ！")
            else:
                messagebox.showinfo("バッチ変換完了", f"{success_count}件の画像を変換して保存したぜ！\n全て連番で出力済みだ。")

        except Exception as e:
            messagebox.showerror("エラー", f"変換中にエラーが発生しました:\n{str(e)}")

    # ====================== ディザリング処理 ======================
    def bayer_ordered_dither(self, img, colors=16, preset="", skin_protect=False, pre_thresh=130.0, post_thresh=45.0):

        img_rgb = img.convert("RGB")
        enhancer = ImageEnhance.Contrast(img_rgb)
        img_enhanced = enhancer.enhance(1.2) 
        
        arr = np.array(img_enhanced, dtype=np.float32)
        
        bayer_matrix = np.array([[ 0,  8,  2, 10],
                                 [12,  4, 14,  6],
                                 [ 3, 11,  1,  9],
                                 [15,  7, 13,  5]], dtype=np.float32)
        
        if preset == "PC88" or colors <= 8:
            amplitude = 128.0 
        else:
            amplitude = 255.0 / colors * 2.0
            
        bayer = (bayer_matrix / 16.0 - 0.5) * amplitude
        
        h, w = arr.shape[:2]
        bayer = np.tile(bayer, (h // 4 + 1, w // 4 + 1))[:h, :w]
        bayer = np.expand_dims(bayer, axis=2)
        
        luminance = np.dot(arr[..., :3], [0.299, 0.587, 0.114])

        if skin_protect:
            lum_mask = np.clip((170.0 - luminance) / 60.0, 0.0, 1.0)
            lum_mask = np.expand_dims(lum_mask, axis=2)
            bayer = bayer * lum_mask

        noisy = arr + bayer

        if skin_protect:
            bright_mask = np.expand_dims(luminance > pre_thresh, axis=2)
            noisy = np.where(bright_mask, np.clip(noisy, pre_thresh, 255), noisy)

        noisy = np.clip(noisy, 0, 255)
        noisy_img = Image.fromarray(noisy.astype(np.uint8))

        result_img = None
        
        if preset == "PC88" or colors == 8:
            pal_img_tmp = Image.new("P", (1, 1))
            pal_img_tmp.putpalette([
                0,0,0,       # 黒
                255,0,0,     # 赤
                0,255,0,     # 緑
                255,255,0,   # 黄
                0,0,255,     # 青
                255,0,255,   # マゼンタ
                0,255,255,   # シアン
                255,255,255  # 白
            ] + [0]*248*3)
            result_img = noisy_img.quantize(palette=pal_img_tmp, dither=0).convert("RGB")
            
        else:
            if preset in ["MSX2", "MSX2 インターレース"] or colors == 512:
                noisy_arr = np.array(noisy_img, dtype=np.float32)
                quantized_512 = np.round(noisy_arr / 36.428) * 36.428
                noisy_img = Image.fromarray(np.clip(quantized_512, 0, 255).astype(np.uint8))
            
            if colors >= 512:
                result_img = noisy_img.convert("RGB")
            else:
                if colors > 256:
                    img_array = np.array(noisy_img.convert('RGB')).reshape((-1, 3))
                    kmeans = MiniBatchKMeans(n_clusters=colors, random_state=0, n_init='auto')
                    labels = kmeans.fit_predict(img_array)
                    palette = kmeans.cluster_centers_.astype('uint8')
                    quantized = palette[labels].reshape(noisy_img.size[1], noisy_img.size[0], 3)
                    result_img = Image.fromarray(quantized).convert("RGB")
                else:
                    result_img = noisy_img.quantize(colors=colors, method=2, kmeans=0).convert("RGB")

        if skin_protect:
            q_arr = np.array(result_img)
            orig_arr = np.array(img_rgb)
            
            orig_lum = np.dot(orig_arr, [0.299, 0.587, 0.114])
            q_lum = np.dot(q_arr, [0.299, 0.587, 0.114])
            
            bad_mask = (orig_lum > 120) & (q_lum < post_thresh)
            
            if np.any(bad_mask):
                unique_colors = np.unique(q_arr.reshape(-1, 3), axis=0)
                safe_colors = [c for c in unique_colors if np.dot(c, [0.299, 0.587, 0.114]) >= post_thresh]
                
                if len(safe_colors) == 0:
                    safe_colors = [np.array([255, 255, 255], dtype=np.uint8)]
                
                safe_colors = np.array(safe_colors)
                bad_orig_colors = orig_arr[bad_mask]
                
                diff = bad_orig_colors[:, np.newaxis, :] - safe_colors[np.newaxis, :, :]
                dist = np.sum(diff**2, axis=2)
                best_color_idx = np.argmin(dist, axis=1)
                
                q_arr[bad_mask] = safe_colors[best_color_idx]
                result_img = Image.fromarray(q_arr)

        return result_img.convert("RGBA")

    def apply_anti_alias_to_outline(self, img):
        edges = img.filter(ImageFilter.FIND_EDGES).convert("L")
        mask = edges.point(lambda x: 0 if x < 100 else 255, "1")
        smoothed = img.filter(ImageFilter.SMOOTH)
        result = Image.composite(smoothed, img, mask)
        return result.convert("RGB")

    def dot_boost(self, img, percent_str):
        percent = int(percent_str.rstrip("%")) / 100.0
        w, h = img.size
        small_w = max(1, int(w * percent))
        small_h = max(1, int(h * percent))
        
        small = img.resize((small_w, small_h), Image.BICUBIC)
        boosted = small.resize((w, h), Image.NEAREST)
        return boosted.convert("RGB")

if __name__ == "__main__":
    root = TkinterDnD.Tk()
    app = RetroConverter(root)
    root.mainloop()