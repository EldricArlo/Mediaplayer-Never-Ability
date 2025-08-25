# media_player_project/gui/main_window.py

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import sys
import time # For time.strftime in debug prints
from PIL import Image, ImageTk, UnidentifiedImageError, ImageDraw, ImageFont 

# 导入 TkinterDnD2 模块，用于支持拖放功能
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    # 如果 TkinterDnD2 未安装，显示警告并提供一个回退的 Tk 类，禁用拖放功能
    messagebox.showerror("TkinterDnD2 导入错误",
                         "未找到 TkinterDnD2 模块。\n"
                         "拖放功能将禁用。请运行 'pip install TkinterDnD2' 安装此模块。")
    class TkinterDnD(tk.Tk): # 回退类，不提供拖放功能
        def drop_target_register(self, *args, **kwargs): pass
        def dnd_bind(self, *args, **kwargs): pass
    DND_FILES = None # 标记拖放功能不可用

# 导入核心逻辑和工具模块
from ..core.player_logic import MediaPlayerLogic
from ..core.playlist_manager import PlaylistManager
from ..utils.constants import PlaybackMode, LYRICS_EXT, COVER_EXT, SUBTITLE_EXT, DEFAULT_LOGO_PATH
from ..utils.logger_config import get_logger
from ..utils.vlc_path_manager import load_vlc_path_from_config, save_vlc_path_to_config, is_valid_vlc_path

# 获取当前模块的 logger 实例
logger = get_logger('MediaPlayer.GUI.MainWindow')

class MediaPlayerGUI(TkinterDnD.Tk): 
    """
    主应用程序窗口类。
    它是整个 GUI 的根，负责应用的整体布局、初始化、事件循环和资源管理。
    它协调核心逻辑 (MediaPlayerLogic) 和数据管理 (PlaylistManager)，
    并将它们的状态反映到用户界面。
    """
    def __init__(self, master=None):
        super().__init__() 
        # 调试信息：记录当前文件和版本时间戳
        current_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print(f"DEBUG: Running from {__file__} - Version Check: {current_time_str} (Final Modularization)")
        logger.debug(f"GUI initializing from {__file__} - Version Check: {current_time_str} (Final Modularization)")

        self.title("Python 多媒体播放器") # 设置窗口标题
        self.geometry("1000x700")       # 设置窗口初始大小
        self.resizable(True, True)       # 允许窗口大小调整
        self.protocol("WM_DELETE_WINDOW", self.on_closing) # 绑定窗口关闭事件

        # 1. 初始化 VLC 媒体逻辑 (需要先获取 VLC 路径)
        vlc_path = self._get_vlc_path_from_user() # 引导用户选择 VLC 路径
        if vlc_path is None:
            # 如果用户取消或未能选择有效路径，则显示错误信息并退出程序
            messagebox.showerror("初始化错误", "未设置有效的 VLC 路径，程序将退出。")
            sys.exit(1) 

        self.player = MediaPlayerLogic(vlc_path=vlc_path) # 实例化核心播放逻辑
        self.playlist_manager = PlaylistManager()       # 实例化播放列表和历史管理器
        
        # 将播放列表和历史记录的实际列表对象引用传递给 player 逻辑。
        # 这样，player 逻辑操作的就是 playlist_manager 维护的同一份数据。
        self.player.playlist = self.playlist_manager.playlist
        self.player.history = self.playlist_manager.history

        # 2. UI 状态变量
        self.current_lyrics_data = []      # 当前加载的歌词数据
        self.current_displayed_image = None # 当前显示的封面图片或视频截图的 ImageTk 对象
        self.is_progress_slider_dragging = False # 标记进度条是否正在被用户拖动
        self.status_bar_reset_job = None   # 用于重置状态栏文本的 after() 任务 ID
        self.active_theme = None           # 当前激活的 Tkinter 主题名称

        # 3. 加载默认占位图 (用于无视频/封面时显示)
        self.load_default_placeholder_image() 

        # 4. 设置 UI 界面元素 (调用内部方法构建 Tkinter 控件)
        self.setup_ui()
        
        # 5. 如果 VLC 初始化成功，设置视频输出绑定到 Tkinter 界面
        if self.player.instance and self.player.player:
            self.setup_vlc_video_output() 
        else:
            self.show_message("VLC 播放器初始化失败，部分功能可能无法使用。", temporary=False)

        # 6. 设置拖放功能 (依赖 TkinterDnD2)
        self.setup_dnd() 

        # 7. 启动 GUI 周期性更新任务 (例如更新进度条、歌词高亮)
        self.update_gui_periodic() 

        # 8. 初始化时更新播放列表和历史显示，并尝试显示当前媒体信息
        self.update_playlist_display()
        self.update_history_display() 
        
        # 如果应用程序启动时播放列表有歌曲，则选中第一首并显示其信息
        if self.player.playlist and self.player.current_index != -1: 
            if self.player.current_index < len(self.player.playlist): # 确保索引在有效范围内
                self.playlist_listbox.selection_set(self.player.current_index) # 选中当前歌曲
                self.playlist_listbox.activate(self.player.current_index)       # 激活当前歌曲 (使其获得焦点)
                self.playlist_listbox.see(self.player.current_index)           # 滚动列表框，使当前歌曲可见
            self.update_current_media_display() # 更新媒体信息显示
            self.show_current_media_content(self.player.current_index) # 显示媒体内容 (封面/歌词/视频)
        else:
            self.clear_media_content_display() # 如果没有歌曲，则清空显示区域

    def _get_vlc_path_from_user(self):
        """
        在程序启动时引导用户设置 VLC 安装路径。
        它首先尝试从配置文件加载路径，如果无效或未设置，则弹出文件对话框让用户选择。
        此方法在 GUI 级别处理与用户的交互，并验证路径的有效性。
        """
        vlc_path = load_vlc_path_from_config() # 尝试从配置文件加载 VLC 路径

        # 循环直到用户选择一个有效路径或取消对话框
        while not vlc_path or not is_valid_vlc_path(vlc_path):
            messagebox.showinfo("VLC 路径设置", 
                                 "VLC 媒体播放器路径未设置或无效。\n"
                                 "请手动选择 VLC 安装目录 (通常是包含 'vlc.exe' 或 'libvlc.dylib' 的目录)。")
            vlc_path = filedialog.askdirectory(title="选择 VLC 媒体播放器安装目录") # 弹出目录选择对话框
            
            if not vlc_path: 
                # 用户取消了选择对话框，返回 None，表示 VLC 路径未成功设置
                logger.warning("用户取消 VLC 路径选择。")
                return None

            if not is_valid_vlc_path(vlc_path):
                # 如果用户选择的路径不是一个有效的 VLC 安装目录，提示用户并再次循环
                messagebox.showwarning("VLC 路径警告", f"'{vlc_path}' 似乎不是一个有效的 VLC 安装目录。请重新选择。")
                vlc_path = None # 将 vlc_path 置 None，以便循环继续

        save_vlc_path_to_config(vlc_path) # 将最终有效的 VLC 路径保存到配置文件中
        return vlc_path

    # --- UI 事件回调方法 (直接绑定到 Tkinter 控件的 command 或 bind) ---
    def on_progress_slider_move(self, val): 
        """
        进度条滑动时触发的回调。
        实时更新进度条旁边的时间显示。
        :param val: 滑动条的当前值 (当前播放时间，毫秒)。
        """
        # 如果用户不是在拖动，而是代码自动更新，则不触发此逻辑
        if not self.is_progress_slider_dragging: 
            self.is_progress_slider_dragging = True # 标记正在拖动，以阻止周期性更新覆盖手动拖动
        
        current_ms = int(float(val))
        current_sec = current_ms / 1000
        current_min = int(current_sec // 60)
        current_sec_rem = int(current_sec % 60)
        self.progress_slider_label.config(text=f"{current_min:02d}:{current_sec_rem:02d}")
        logger.debug(f"Moved slider to {current_ms}ms")

    def on_progress_slider_press(self, event): 
        """
        进度条被用户鼠标按下时触发的回调。
        标记进度条正在被拖动。
        """
        self.is_progress_slider_dragging = True
        logger.debug("Progress slider pressed.")

    def on_progress_slider_release(self, event): 
        """
        进度条被用户鼠标释放时触发的回调。
        根据滑动条的最终位置跳转播放进度。
        """
        self.is_progress_slider_dragging = False # 重置拖动标记
        if self.player.player and self.player.current_media_item:
            new_position_ms = int(self.progress_slider.get()) # 获取滑动条的当前值
            self.player.player.set_time(new_position_ms)      # 设置 VLC 播放器的播放时间
            logger.info(f"Progress slider released. Seeked to: {new_position_ms} ms")
        logger.debug("Progress slider released.")
    
    def set_volume_action(self, val):
        """
        音量滑动条被拖动时触发的回调。
        更新播放器音量和音量显示标签。
        :param val: 滑动条的当前值 (0-100)。
        """
        volume = float(val) / 100.0 # 将 0-100 的值转换为 0.0-1.0
        success, message = self.player.set_volume(volume) # 调用核心逻辑设置音量
        if hasattr(self, 'volume_value_label'): # 确保标签存在
            self.volume_value_label.config(text=f"{int(volume*100)}%")
        logger.debug(f"Volume set to {volume*100:.0f}%")

    def set_playback_rate_action(self, val):
        """
        播放速度滑动条被拖动时触发的回调。
        更新播放器速度和速度显示标签。
        :param val: 滑动条的当前值 (例如 0.5, 1.0, 2.0)。
        """
        rate = float(val) # 获取滑动条的当前值
        success, message = self.player.set_playback_rate(rate) # 调用核心逻辑设置播放速度
        if hasattr(self, 'speed_value_label'): # 确保标签存在
            self.speed_value_label.config(text=f"{rate:.2f}x")
        logger.debug(f"Playback rate set to {rate:.2f}x")

    def load_default_placeholder_image(self):
        """
        加载一个默认的占位图片，用于在没有视频内容或封面图片时显示。
        如果指定图片文件不存在或加载失败，则动态创建一个简单的文本占位图。
        """
        try:
            # 构造默认 Logo 图片的完整路径
            script_dir = os.path.dirname(os.path.abspath(__file__))
            logo_path = os.path.join(script_dir, "..", DEFAULT_LOGO_PATH) # 调整路径以适应新结构
            
            img = None
            if os.path.exists(logo_path):
                try:
                    img = Image.open(logo_path) # 尝试使用 Pillow 打开图片
                except (IOError, UnidentifiedImageError) as e:
                    # 捕获文件 IO 错误或无法识别图片格式的错误
                    logger.warning(f"无法加载 '{logo_path}' ({e})，将创建默认文本占位图。")

            if img is None:
                # 如果没有提供图片文件或加载失败，则创建一个新的空白图片
                img = Image.new('RGB', (300, 300), color = '#555555') # 300x300 像素，深灰色背景
                draw = ImageDraw.Draw(img) # 创建绘图对象
                font_size = 24
                try:
                    # 尝试加载常见的系统字体，以获得更好的文本渲染效果
                    font_paths = [
                        "arial.ttf", 
                        "/System/Library/Fonts/Supplemental/Arial.ttf", # macOS 路径
                        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", # Linux 路径
                        "/usr/share/fonts/truetype/freefont/FreeSans.ttf" # 另一个 Linux 路径
                    ]
                    font = None
                    for fp in font_paths:
                        try:
                            font = ImageFont.truetype(fp, font_size)
                            break # 找到第一个可用的字体就停止
                        except IOError:
                            pass # 字体文件不存在，尝试下一个
                    if font is None:
                        font = ImageFont.load_default() # 如果都找不到，使用 Pillow 默认字体
                except Exception as e:
                    logger.error(f"加载字体失败: {e}，将使用默认字体。")
                    font = ImageFont.load_default()

                text = "Python Media Player\n\nNo Media/Video Content"
                # 获取文本的边界框，用于计算文本在图片中居中的位置
                bbox = draw.textbbox((0,0), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                
                # 计算文本的 (x, y) 坐标使其在图片中居中
                x = (img.width - text_width) / 2
                y = (img.height - text_height) / 2
                
                draw.text((x,y), text, fill="white", font=font, align="center") # 绘制文本
            
            # 缩放图片到 300x300 像素，使用 LANCZOS 算法以获得高质量的缩放效果
            img = img.resize((300, 300), Image.LANCZOS) 
            self.default_placeholder_image = ImageTk.PhotoImage(img) # 转换为 Tkinter 图像对象
            logger.info("默认占位图加载成功。")

        except Exception as e:
            logger.error(f"加载或创建默认占位图失败: {e}. 将使用 ttk.Label 的背景色作为占位。", exc_info=True)
            self.default_placeholder_image = None # 如果完全失败，则设置为 None

    def setup_ui(self):
        """
        初始化并布局所有的 Tkinter UI 元素。
        包括菜单栏、状态栏、媒体信息区、控制区和播放列表/历史标签页。
        """
        self.menubar = tk.Menu(self)
        self.config(menu=self.menubar)

        # --- 文件菜单 ---
        file_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="文件", menu=file_menu)
        file_menu.add_command(label="添加文件", command=self.add_media_action)
        file_menu.add_command(label="加载文件夹", command=self.load_folder_action)
        file_menu.add_command(label="添加网络流", command=self.add_network_stream_action) 
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.on_closing)

        # --- 选项菜单 ---
        options_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="选项", menu=options_menu)
        
        self.theme_menu = tk.Menu(options_menu, tearoff=0)
        options_menu.add_cascade(label="主题", menu=self.theme_menu)
        # 动态添加所有可用的 ttk 主题选项
        for theme_name in ttk.Style().theme_names():
            self.theme_menu.add_command(label=theme_name, command=lambda t=theme_name: self.toggle_theme(t))
        
        options_menu.add_command(label="均衡器", command=self.open_equalizer_window) 

        # --- 状态栏 ---
        self.status_bar = ttk.Label(self, text="就绪。", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X, ipady=2) 

        # --- 媒体信息和进度条区域 ---
        self.info_frame = ttk.Frame(self, borderwidth=2, relief="groove")
        self.info_frame.pack(pady=5, fill="x", padx=10)

        self.current_media_title_label = ttk.Label(self.info_frame, text="标题: N/A", font=("Helvetica", 14), wraplength=800)
        self.current_media_title_label.pack(pady=2)
        self.current_media_artist_label = ttk.Label(self.info_frame, text="艺术家: N/A", font=("Helvetica", 12), wraplength=800)
        self.current_media_artist_label.pack(pady=2)
        self.current_media_album_label = ttk.Label(self.info_frame, text="专辑: N/A", font=("Helvetica", 12), wraplength=800)
        self.current_media_album_label.pack(pady=2)

        time_frame = ttk.Frame(self.info_frame)
        time_frame.pack(fill="x", expand=True, pady=5)

        self.progress_slider_label = ttk.Label(time_frame, text="00:00")
        self.progress_slider_label.pack(side=tk.LEFT, padx=5)

        self.progress_slider = ttk.Scale(
            time_frame,
            from_=0, to=1, # 初始范围，会动态更新
            orient="horizontal",
            command=self.on_progress_slider_move 
        )
        self.progress_slider.pack(side=tk.LEFT, fill="x", expand=True, padx=5)
        self.progress_slider.bind("<ButtonRelease-1>", self.on_progress_slider_release) 
        self.progress_slider.bind("<Button-1>", self.on_progress_slider_press) 

        self.total_time_label = ttk.Label(time_frame, text="00:00")
        self.total_time_label.pack(side=tk.RIGHT, padx=5)

        self.status_label = ttk.Label(self.info_frame, text="状态: 停止", font=("Helvetica", 12))
        self.status_label.pack(pady=2)

        # --- 视频/图片/歌词显示区域 ---
        self.display_frame = ttk.Frame(self, borderwidth=2, relief="sunken")
        self.display_frame.pack(pady=5, padx=10, fill="both", expand=True)

        self.video_panel = tk.Frame(self.display_frame, relief="flat", borderwidth=0, bg="black") 
        self.video_panel.pack(side="left", fill="both", expand=True, padx=0, pady=0)
        self.video_panel.bind("<Configure>", self._on_video_panel_resize) # 绑定尺寸变化事件

        self.image_label = tk.Label(self.video_panel, background="black") # 用于显示封面或默认图片

        self.lyrics_frame = ttk.Frame(self.display_frame, borderwidth=0)
        self.lyrics_label = ttk.Label(self.lyrics_frame, text="歌词:", font=("Helvetica", 12, "bold"))
        self.lyrics_label.pack(pady=2)

        self.lyrics_text = tk.Text(self.lyrics_frame, wrap="word", height=10, width=40, font=("等线", 12), bg=self.get_theme_background(), fg=self.get_theme_foreground(), insertbackground="white")
        self.lyrics_text.pack(side="left", fill="y", expand=True)
        self.lyrics_text.tag_config("highlight", background="yellow", foreground="black") # 高亮歌词样式
        self.lyrics_text.tag_config("normal", background=self.get_theme_background(), foreground=self.get_theme_foreground()) # 正常歌词样式
        self.lyrics_scrollbar = ttk.Scrollbar(self.lyrics_frame, command=self.lyrics_text.yview)
        self.lyrics_scrollbar.pack(side="right", fill="y")
        self.lyrics_text.config(yscrollcommand=self.lyrics_scrollbar.set)
        
        # --- 播放控制按钮 ---
        self.control_frame = ttk.Frame(self, borderwidth=2, relief="groove")
        self.control_frame.pack(pady=5)

        self.btn_prev = ttk.Button(self.control_frame, text="上一首", command=self.prev_media_action, width=10)
        self.btn_prev.grid(row=0, column=0, padx=5, pady=5)
        self.btn_play = ttk.Button(self.control_frame, text="播放", command=self.play_action, width=10)
        self.btn_play.grid(row=0, column=1, padx=5, pady=5)
        self.btn_pause = ttk.Button(self.control_frame, text="暂停", command=self.pause_action, width=10)
        self.btn_pause.grid(row=0, column=2, padx=5, pady=5)
        self.btn_unpause = ttk.Button(self.control_frame, text="恢复", command=self.unpause_action, width=10)
        self.btn_unpause.grid(row=0, column=3, padx=5, pady=5)
        self.btn_stop = ttk.Button(self.control_frame, text="停止", command=self.stop_action, width=10)
        self.btn_stop.grid(row=0, column=4, padx=5, pady=5)
        self.btn_next = ttk.Button(self.control_frame, text="下一首", command=self.next_media_action, width=10)
        self.btn_next.grid(row=0, column=5, padx=5, pady=5)

        # 音量控制滑动条
        self.volume_label = ttk.Label(self.control_frame, text="音量:")
        self.volume_label.grid(row=1, column=0, padx=5, pady=5, sticky="W")
        self.volume_slider = ttk.Scale(
            self.control_frame, from_=0, to=100, orient="horizontal",
            command=self.set_volume_action, length=200
        )
        self.volume_slider.set(self.player.volume * 100) # 设置初始值
        self.volume_slider.grid(row=1, column=1, columnspan=4, padx=5, pady=5, sticky="EW")
        self.volume_value_label = ttk.Label(self.control_frame, text=f"{int(self.player.volume*100)}%")
        self.volume_value_label.grid(row=1, column=5, padx=5, pady=5, sticky="E")

        # 播放速度控制滑动条
        self.speed_label = ttk.Label(self.control_frame, text="速度:")
        self.speed_label.grid(row=2, column=0, padx=5, pady=5, sticky="W")
        self.speed_slider = ttk.Scale(
            self.control_frame, from_=0.5, to=2.0, orient="horizontal",
            command=self.set_playback_rate_action, length=150
        )
        self.speed_slider.set(self.player.playback_rate) # 设置初始值
        self.speed_slider.grid(row=2, column=1, columnspan=2, padx=5, pady=5, sticky="EW")
        self.speed_value_label = ttk.Label(self.control_frame, text=f"{self.player.playback_rate:.2f}x")
        self.speed_value_label.grid(row=2, column=3, padx=5, pady=5, sticky="W")

        # 播放模式切换按钮
        self.playback_mode_button = ttk.Button(self.control_frame, text=self.player.playback_mode.value, command=self.toggle_playback_mode, width=12)
        self.playback_mode_button.grid(row=2, column=4, columnspan=2, pady=5)

        # --- Notebook (播放列表和历史记录标签页) ---
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(pady=5, padx=10, fill="both", expand=True)

        # 播放列表标签页
        self.playlist_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.playlist_tab, text="播放列表")
        self.playlist_label = ttk.Label(self.playlist_tab, text="播放列表:", font=("Helvetica", 12, "bold"))
        self.playlist_label.pack(pady=5)
        self.listbox_frame = ttk.Frame(self.playlist_tab)
        self.listbox_frame.pack(fill="both", expand=True)
        self.playlist_listbox = tk.Listbox(self.listbox_frame, selectmode="EXTENDED", font=("Courier", 10), bd=0, highlightthickness=0)
        self.playlist_listbox.pack(side="left", fill="both", expand=True)
        self.playlist_listbox.bind("<<ListboxSelect>>", self.on_listbox_select) # 选中事件
        self.playlist_listbox.bind("<Double-Button-1>", self.on_listbox_double_click) # 双击播放事件
        
        # 播放列表拖放绑定 (只有当 TkinterDnD2 可用时)
        if DND_FILES is not None:
            self.playlist_listbox.dnd_bind('<<DragInitCmd>>', self.on_playlist_drag_init)
            self.playlist_listbox.dnd_bind('<<DropTargetOver>>', self.on_playlist_drop_target_over)
            self.playlist_listbox.dnd_bind('<<DropTargetLeave>>', self.on_playlist_drop_target_leave)
            self.playlist_listbox.dnd_bind('<<Drop>>', self.on_playlist_drop)
        self.drag_data = {"index": None, "original_bg": None} # 用于拖放操作的数据

        self.scrollbar = ttk.Scrollbar(self.listbox_frame, orient="vertical", command=self.playlist_listbox.yview)
        self.scrollbar.pack(side="right", fill="y")
        self.playlist_listbox.config(yscrollcommand=self.scrollbar.set)

        # 播放列表操作按钮
        playlist_ops_frame = ttk.Frame(self.playlist_tab)
        playlist_ops_frame.pack(pady=5, fill="x")
        self.btn_remove_selected = ttk.Button(playlist_ops_frame, text="移除选中", command=self.remove_selected_media, width=12)
        self.btn_remove_selected.pack(side="left", padx=5)
        self.btn_remove_selected.config(state=tk.DISABLED) # 默认禁用，无选中项时不可用
        self.btn_clear_playlist = ttk.Button(playlist_ops_frame, text="清空列表", command=self.clear_playlist_action, width=12)
        self.btn_clear_playlist.pack(side="left", padx=5)
        self.btn_move_up = ttk.Button(playlist_ops_frame, text="上移", command=lambda: self.move_media_action('up'), width=8)
        self.btn_move_up.pack(side="left", padx=5)
        self.btn_move_up.config(state=tk.DISABLED)
        self.btn_move_down = ttk.Button(playlist_ops_frame, text="下移", command=lambda: self.move_media_action('down'), width=8)
        self.btn_move_down.pack(side="left", padx=5)
        self.btn_move_down.config(state=tk.DISABLED)

        # 播放历史标签页
        self.history_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.history_tab, text="播放历史")
        self.history_label = ttk.Label(self.history_tab, text="播放历史:", font=("Helvetica", 12, "bold"))
        self.history_label.pack(pady=5)
        self.history_listbox_frame = ttk.Frame(self.history_tab)
        self.history_listbox_frame.pack(fill="both", expand=True)
        self.history_listbox = tk.Listbox(self.history_listbox_frame, selectmode="BROWSE", font=("Courier", 10), bd=0, highlightthickness=0)
        self.history_listbox.pack(side="left", fill="both", expand=True)
        self.history_listbox.bind("<<ListboxSelect>>", self.on_history_listbox_select) # 选中事件
        self.history_listbox.bind("<Double-Button-1>", self.on_history_listbox_double_click) # 双击播放事件
        self.history_scrollbar = ttk.Scrollbar(self.history_listbox_frame, orient="vertical", command=self.history_listbox.yview)
        self.history_scrollbar.pack(side="right", fill="y")
        self.history_listbox.config(yscrollcommand=self.history_scrollbar.set)
        
        # --- 文件加载和关联操作按钮 ---
        self.load_buttons_frame = ttk.Frame(self, padding=(10, 5))
        self.load_buttons_frame.pack()
        self.btn_load_folder = ttk.Button(self.load_buttons_frame, text="加载文件夹", command=self.load_folder_action, width=12)
        self.btn_load_folder.pack(side="left", padx=5)
        self.btn_add_media = ttk.Button(self.load_buttons_frame, text="添加文件", command=self.add_media_action, width=12)
        self.btn_add_media.pack(side="left", padx=5)
        self.btn_add_lyrics = ttk.Button(self.load_buttons_frame, text="添加歌词", command=lambda: self.add_associated_file_action('lyrics'), width=12)
        self.btn_add_lyrics.pack(side="left", padx=5)
        self.btn_add_lyrics.config(state=tk.DISABLED) # 默认禁用
        self.btn_add_cover = ttk.Button(self.load_buttons_frame, text="添加封面", command=lambda: self.add_associated_file_action('cover'), width=12)
        self.btn_add_cover.pack(side="left", padx=5)
        self.btn_add_cover.config(state=tk.DISABLED)
        self.btn_add_subtitle = ttk.Button(self.load_buttons_frame, text="添加字幕", command=lambda: self.add_associated_file_action('subtitle'), width=12)
        self.btn_add_subtitle.pack(side="left", padx=5)
        self.btn_add_subtitle.config(state=tk.DISABLED)

        # 应用初始主题
        self.toggle_theme(ttk.Style().theme_use())

    def get_theme_background(self):
        """
        获取当前 ttk (Themed Tkinter) 主题的背景色。
        这用于需要手动设置背景色的非 ttk 控件 (如 Text 控件)。
        """
        try:
            return ttk.Style().lookup('TFrame', 'background')
        except:
            return "#F0F0F0" # 回退到默认的 Tkinter 浅灰色
    
    def get_theme_foreground(self):
        """
        获取当前 ttk 主题的前景色。
        这用于需要手动设置前景色的非 ttk 控件。
        """
        try:
            return ttk.Style().lookup('TLabel', 'foreground')
        except:
            return "#000000" # 回退到默认的 Tkinter 黑色

    def toggle_theme(self, theme_name=None):
        """
        切换应用程序的主题。
        如果未指定主题名，则循环切换到下一个可用主题。
        :param theme_name: 要切换到的主题名称 (例如 'clam', 'alt', 'default')。
        """
        style = ttk.Style()
        if theme_name is None:
            current_themes = style.theme_names() # 获取所有可用主题名称
            try:
                current_index = current_themes.index(style.theme_use()) # 获取当前主题的索引
                next_index = (current_index + 1) % len(current_themes) # 计算下一个主题的索引
                theme_name = current_themes[next_index]
            except ValueError: 
                theme_name = "default" # 如果当前主题不在已知列表中，则回退到 'default'
        
        try:
            style.theme_use(theme_name) # 切换主题
            self.active_theme = theme_name
            self.show_message(f"主题已切换到: {theme_name}")
            logger.info(f"主题已切换到: {theme_name}")

            # 更新 Text 控件 (如歌词显示区域) 的背景和前景，因为 Text 控件不受 ttk 样式自动影响
            self.lyrics_text.config(bg=self.get_theme_background(), fg=self.get_theme_foreground())
            self.lyrics_text.tag_config("normal", background=self.get_theme_background(), foreground=self.get_theme_foreground())
            
        except tk.TclError as e:
            # 捕获切换主题时可能发生的 Tcl 错误 (例如，主题名无效)
            self.show_message(f"切换主题失败: {e}", temporary=False)
            logger.error(f"切换主题 '{theme_name}' 失败: {e}")

    def setup_vlc_video_output(self):
        """
        将 VLC 的视频输出绑定到 Tkinter 的视频面板 (`self.video_panel`)。
        这使得 VLC 能够直接在 GUI 窗口的指定区域内渲染视频内容。
        """
        # 强制更新 Tkinter 窗口，确保 `winfo_id()` 返回有效的窗口句柄
        self.update_idletasks() 
        
        # 确保 VLC 播放器实例已成功初始化
        if not self.player.instance or not self.player.player:
            return 

        try:
            # 根据不同的操作系统调用不同的 VLC API 来设置视频输出窗口句柄
            if sys.platform.startswith('linux'):
                self.player.player.set_xwindow(self.video_panel.winfo_id()) # Linux 使用 X Window ID
            elif sys.platform == 'darwin': # macOS
                self.player.player.set_nsobject(self.video_panel.winfo_id()) # macOS 使用 NSView 或 NSWindow 对象
            else: # Windows
                self.player.player.set_hwnd(self.video_panel.winfo_id()) # Windows 使用 HWND 句柄
            logger.info(f"VLC 视频输出已绑定到面板 (ID: {self.video_panel.winfo_id()})。")

        except Exception as e:
            logger.error(f"绑定 VLC 视频输出到面板失败: {e}", exc_info=True)
            self.show_message(f"VLC 视频输出设置失败: {e}", temporary=False)
        
    def _on_video_panel_resize(self, event):
        """
        当视频显示面板 (`self.video_panel`) 大小改变时触发的回调。
        对于视频，它会重新设置 VLC 视频输出以适应新尺寸；
        对于图片，它会重新缩放并显示图片以适应新尺寸。
        :param event: Tkinter Configure 事件对象，包含新的宽度和高度。
        """
        if event.width > 0 and event.height > 0:
            logger.debug(f"视频面板大小改变: {event.width}x{event.height}")
            if self.player.current_media_item and self.player.current_media_item['type'] == 'video':
                # 如果当前正在播放视频，需要重新绑定 VLC 输出以适应面板的新尺寸
                self.setup_vlc_video_output()
            elif self.player.current_media_item and self.player.current_media_item['type'] == 'audio' and self.player.current_media_item.get('cover_path'):
                # 如果是音频且有封面在显示，重新显示封面以适应新尺寸，防止图片拉伸或模糊
                self.show_current_media_content(self.player.current_index) 

    def setup_dnd(self):
        """
        设置 TkinterDnD2 拖放功能，允许用户从文件系统拖放文件到播放器窗口。
        """
        if DND_FILES is not None: # 只有当 TkinterDnD2 成功导入时才设置拖放功能
            # 注册整个主窗口作为拖放目标
            self.drop_target_register(DND_FILES)
            self.bind('<<Drop>>', self.handle_drop_on_window) # 绑定到主窗口的 drop 事件

            # 注册播放列表列表框作为拖放目标
            self.playlist_listbox.drop_target_register(DND_FILES)
            self.playlist_listbox.bind('<<Drop>>', self.handle_drop_on_listbox) # 绑定到列表框的 drop 事件
        else:
            logger.warning("TkinterDnD2 未加载，拖放功能已禁用。")

    def handle_drop_on_window(self, event):
        """处理文件拖放到主窗口任意区域的事件。"""
        self.process_dropped_files(event.data)
        self.update_playlist_display() 

    def handle_drop_on_listbox(self, event):
        """处理文件拖放到播放列表列表框的事件。"""
        self.process_dropped_files(event.data)
        self.update_playlist_display() 

    def process_dropped_files(self, data):
        """
        处理拖放进来的文件路径。
        尝试将文件添加到播放列表；如果文件已存在于列表中，则尝试作为关联文件添加。
        :param data: 拖放操作传递的文件路径字符串 (可能是多个路径)。
        """
        # 将拖放的数据 (可能是多个文件路径的字符串) 分割成列表
        filepaths = self.tk.splitlist(data) 
        new_media_count = 0
        
        for filepath in filepaths:
            # 尝试将文件作为新媒体添加到播放列表
            success, message = self.player.add_media(filepath)
            if success:
                new_media_count += 1
            else:
                # 如果文件未被添加为新媒体 (例如，因为它已经存在于列表中)，
                # 则尝试将其作为当前选中媒体的关联文件
                selected_indices = self.playlist_listbox.curselection()
                if selected_indices:
                    media_index = selected_indices[0]
                    # 根据文件扩展名判断拖放文件的类型 (歌词、封面、字幕)
                    ext = os.path.splitext(filepath)[1].lower()
                    file_type = None
                    if ext in LYRICS_EXT: file_type = 'lyrics'
                    elif ext in COVER_EXT: file_type = 'cover'
                    elif ext in SUBTITLE_EXT: file_type = 'subtitle'
                    
                    if file_type:
                        # 调用核心逻辑设置关联文件
                        success_assoc, message_assoc = self.player.set_media_association(media_index, file_type, filepath)
                        if success_assoc:
                            self.show_message(f"已拖放并关联: {os.path.basename(filepath)}")
                            self.update_playlist_display() 
                            # 如果关联的是当前播放的媒体，需要更新显示区域以反映变化
                            if media_index == self.player.current_index:
                                self.show_current_media_content(media_index)
                            continue # 处理完关联文件，跳过当前文件，继续处理下一个拖放项
                
                # 如果既不是新媒体也不是关联文件，则显示原始的添加失败消息
                self.show_message(message) 

        if new_media_count > 0:
            self.show_message(f"已拖放添加 {new_media_count} 个新媒体文件。")
            self.update_playlist_display()
            # 如果播放列表之前是空的，且添加了新歌曲，则自动选中并显示第一个添加的歌曲
            if self.player.current_index == -1 and self.player.playlist:
                self.player.current_index = 0
                self.playlist_listbox.selection_set(0)
                self.playlist_listbox.activate(0)
                self.playlist_listbox.see(0)
            self.update_current_media_display()
            
    # --- 播放列表拖放排序功能实现 (用于列表项的内部重新排序) ---
    def on_playlist_drag_init(self, event):
        """当播放列表项开始被用户拖动时初始化拖放操作。"""
        selected_indices = self.playlist_listbox.curselection()
        if not selected_indices:
            return None # 如果没有选中项，则不允许拖动

        # 记录被拖动项的原始索引和背景色，以便后续操作和恢复
        self.drag_data["index"] = selected_indices[0]
        self.drag_data["original_bg"] = self.playlist_listbox.itemcget(self.drag_data["index"], "bg")
        
        # 临时改变被拖动项的背景色以提供视觉反馈
        self.playlist_listbox.itemconfig(self.drag_data["index"], bg="lightgray")
        
        # 返回拖动数据，指示可以拖动文件类型（DND_FILES 是一个通用类型），以及被拖动项的索引
        return ((DND_FILES, ), (self.playlist_listbox.index(self.drag_data["index"]),), None)

    def on_playlist_drop_target_over(self, event):
        """
        当拖动项悬停在播放列表的不同位置时提供视觉反馈。
        高亮当前拖动目标位置。
        """
        if self.drag_data["index"] is None:
            return # 如果不是内部拖动操作，则不处理

        try:
            target_index = self.playlist_listbox.nearest(event.y) # 获取鼠标当前位置最近的列表项索引
            # 如果之前有高亮项（并且不是被拖动项本身），则恢复其原始背景色
            if hasattr(self, '_prev_drop_highlight_idx') and \
               self._prev_drop_highlight_idx is not None and \
               self._prev_drop_highlight_idx != self.drag_data["index"]:
                self.playlist_listbox.itemconfig(self._prev_drop_highlight_idx, bg=self.playlist_listbox.cget('background')) 
            
            # 如果当前悬停的项不是被拖动项本身，则将其高亮
            if target_index != self.drag_data["index"]:
                self.playlist_listbox.itemconfig(target_index, bg="gray")
                self._prev_drop_highlight_idx = target_index
            else:
                # 如果悬停回被拖动项本身，取消高亮（如果有）
                if hasattr(self, '_prev_drop_highlight_idx') and self._prev_drop_highlight_idx is not None:
                    self.playlist_listbox.itemconfig(self._prev_drop_highlight_idx, bg=self.playlist_listbox.cget('background'))
                    self._prev_drop_highlight_idx = None

            return "copy" # 表示可以放置到此位置
        except tk.TclError:
            return # 避免在列表框为空或无效时引发错误

    def on_playlist_drop_target_leave(self, event):
        """当拖动项离开播放列表区域时，恢复所有被高亮项的背景色。"""
        if self.drag_data["index"] is not None:
            # 恢复被拖动项的原始背景色
            self.playlist_listbox.itemconfig(self.drag_data["index"], bg=self.drag_data["original_bg"])
            self.drag_data["index"] = None
            self.drag_data["original_bg"] = None
        
        # 恢复之前高亮的目标项的背景色
        if hasattr(self, '_prev_drop_highlight_idx') and self._prev_drop_highlight_idx is not None:
            self.playlist_listbox.itemconfig(self._prev_drop_highlight_idx, bg=self.playlist_listbox.cget('background'))
            self._prev_drop_highlight_idx = None

    def on_playlist_drop(self, event):
        """
        处理拖放操作完成时的逻辑，重新排序播放列表。
        将被拖动项从源位置移动到目标位置。
        """
        if self.drag_data["index"] is None:
            return # 如果没有拖动数据，则不处理

        source_index = self.drag_data["index"]
        target_index = self.playlist_listbox.nearest(event.y) # 最终放置位置的索引

        self.on_playlist_drop_target_leave(event) # 清除拖放时的视觉效果

        if source_index == target_index:
            self.show_message("未改变顺序。")
            return

        # 调用核心逻辑来移动媒体项，更新内部播放列表数据
        success, message = self.player.move_media_to_position(source_index, target_index)
        self.show_message(message)
        if success:
            self.update_playlist_display() # 更新列表框的显示
            # 重新选中并滚动到移动后的项，提供良好的用户体验
            self.playlist_listbox.selection_clear(0, tk.END)
            self.playlist_listbox.selection_set(target_index)
            self.playlist_listbox.activate(target_index)
            self.playlist_listbox.see(target_index)
            self.update_current_media_display() # 更新当前播放信息（因为索引可能改变）

    # --- GUI 操作事件处理函数 ---
    def show_message(self, message, temporary=True, duration_ms=3000):
        """
        在状态栏显示消息。
        消息可以是临时的（在一段时间后消失）或永久的。
        :param message: 要显示的消息字符串。
        :param temporary: 如果为 True，消息将在指定时间后消失。
        :param duration_ms: 消息显示的毫秒数（仅当 temporary 为 True 时有效）。
        """
        if self.status_bar_reset_job:
            self.after_cancel(self.status_bar_reset_job) # 取消之前未完成的消息重置任务
            self.status_bar_reset_job = None
        
        self.status_bar.config(text=message) # 更新状态栏文本
        if temporary:
            # 在指定时间后，将状态栏文本重置为“就绪。”
            self.status_bar_reset_job = self.after(duration_ms, lambda: self.status_bar.config(text="就绪。"))

    def add_network_stream_action(self):
        """弹出对话框，让用户输入网络流 URL 并将其添加到播放列表。"""
        stream_window = tk.Toplevel(self) # 创建一个新的顶级窗口
        stream_window.title("添加网络流")
        stream_window.transient(self)      # 使其成为主窗口的瞬时窗口 (关闭主窗口时它也会关闭)
        stream_window.grab_set()           # 捕获输入，阻止用户与主窗口交互，直到此窗口关闭

        tk.Label(stream_window, text="请输入网络流 URL:").pack(padx=10, pady=5)
        url_entry = ttk.Entry(stream_window, width=50)
        url_entry.pack(padx=10, pady=5)
        url_entry.focus_set() # 自动聚焦输入框

        def add_stream():
            """在对话框中点击“添加”按钮时执行。"""
            url = url_entry.get().strip()
            if url:
                success, message = self.player.add_media(url) # 调用核心逻辑添加网络流
                self.show_message(message)
                if success:
                    self.update_playlist_display() # 更新播放列表显示
                    # 如果播放列表之前为空，且这是通过网络流添加的第一首歌，则将其设为当前播放歌曲并显示
                    if self.player.current_index == -1 and self.player.playlist:
                        self.player.current_index = 0
                        self.playlist_listbox.selection_set(0)
                        self.playlist_listbox.activate(0)
                        self.playlist_listbox.see(0)
                    self.update_current_media_display()
                stream_window.destroy() # 关闭对话框
            else:
                messagebox.showwarning("输入错误", "URL 不能为空。")

        ttk.Button(stream_window, text="添加", command=add_stream).pack(pady=10)
        self.wait_window(stream_window) # 阻止主窗口的执行，直到此对话框关闭

    def open_equalizer_window(self):
        """打开均衡器设置窗口，允许用户调整音频均衡器。"""
        # 确保均衡器已在核心逻辑中初始化
        if not self.player.equalizer:
            self.show_message("均衡器未初始化或不可用。", temporary=False)
            return

        eq_window = tk.Toplevel(self) # 创建一个新的顶级窗口作为均衡器界面
        eq_window.title("均衡器")
        eq_window.transient(self)
        eq_window.grab_set()

        tk.Label(eq_window, text="前置放大 (dB):").pack(pady=5)
        preamp_slider = ttk.Scale(
            eq_window,
            from_=-20.0, to=20.0, # 前置放大增益范围
            orient="horizontal",
            length=300,
            command=lambda val: self.player.equalizer_control.set_equalizer_preamp(float(val))
        )
        
        # 从核心逻辑获取均衡器当前状态（包括前置放大和各频段增益）
        eq_info = self.player.equalizer_control.get_equalizer_bands_info()
        preamp_slider.set(eq_info.get("preamp", 0.0)) # 设置滑动条初始值
        preamp_slider.pack(padx=10, pady=5)

        self.eq_band_sliders = [] # 存储频段滑动条的列表
        # 为每个频段创建标签和滑动条
        for band_data in eq_info.get("bands", []):
            i = band_data["index"]
            freq = band_data["frequency"]
            gain = band_data["gain"]

            tk.Label(eq_window, text=f"{freq:.0f} Hz (dB):").pack(pady=2)
            band_slider = ttk.Scale(
                eq_window,
                from_=-20.0, to=20.0, # 频段增益范围
                orient="horizontal",
                length=300,
                command=lambda val, idx=i: self.player.equalizer_control.set_equalizer_gain(idx, float(val))
            )
            band_slider.set(gain) # 设置滑动条初始值
            band_slider.pack(padx=10, pady=2)
            self.eq_band_sliders.append(band_slider)
        
        def reset_eq():
            """重置均衡器所有增益为 0 dB，并更新 UI。"""
            preamp_slider.set(0.0)
            if self.player.equalizer: 
                self.player.equalizer_control.set_equalizer_preamp(0.0)
            for i, slider in enumerate(self.eq_band_sliders):
                slider.set(0.0)
                if self.player.equalizer: 
                    self.player.equalizer_control.set_equalizer_gain(i, 0.0)
            self.show_message("均衡器已重置。", temporary=True)

        ttk.Button(eq_window, text="重置", command=reset_eq).pack(pady=10)

        self.wait_window(eq_window) # 等待均衡器窗口关闭

    def load_folder_action(self):
        """通过文件对话框选择一个文件夹，并将其中所有支持的媒体文件添加到播放列表。"""
        folder_path = filedialog.askdirectory(title="选择媒体文件夹")
        if folder_path:
            count, message = self.player.load_playlist_from_folder(folder_path) # 调用核心逻辑加载文件夹
            self.show_message(message)
            self.update_playlist_display()
            # 如果添加了新歌曲，且当前没有歌曲在播放、缓冲或暂停，则自动播放第一首
            current_status = self.player.get_current_media_info()[1] # 获取当前播放状态字符串
            if count > 0 and current_status not in ["播放中", "加载中...", "暂停"]:
                self.play_action() # 触发播放操作

    def add_media_action(self):
        """通过文件对话框选择一个或多个媒体文件，并添加到播放列表。"""
        filepaths = filedialog.askopenfilenames(
            title="选择媒体文件",
            # 定义支持的媒体文件类型，使用常量中定义的扩展名
            filetypes=[("Media Files", "*"+ " *".join(SUPPORTED_MEDIA_EXT)), ("All Files", "*.*")] 
        )
        if filepaths:
            count = 0
            for filepath in filepaths:
                success, message = self.player.add_media(filepath) # 调用核心逻辑添加文件
                if success:
                    count += 1
            if count > 0:
                self.show_message(f"已添加 {count} 个新媒体文件。")
                self.update_playlist_display()
                # 如果播放列表之前为空，且添加了新歌曲，则自动选中并显示第一个添加的歌曲
                if self.player.current_index == -1 and self.player.playlist:
                    self.player.current_index = 0
                    self.playlist_listbox.selection_set(0)
                    self.playlist_listbox.activate(0)
                    self.playlist_listbox.see(0)
                self.update_current_media_display()
            else:
                self.show_message("未添加任何新媒体文件。", temporary=False)

    def add_associated_file_action(self, file_type):
        """
        为当前选中的媒体文件添加关联文件 (歌词、封面、字幕)。
        :param file_type: 关联文件类型 ('lyrics', 'cover', 'subtitle')。
        """
        selected_indices = self.playlist_listbox.curselection()
        if not selected_indices:
            self.show_message("请先在播放列表中选择一个媒体文件。")
            return

        media_index = selected_indices[0] # 获取选中项的索引
        media_item = self.player.playlist[media_index] # 获取对应的媒体项数据

        # 根据文件类型设置文件对话框的文件过滤器
        filetypes = []
        if file_type == 'lyrics':
            filetypes = [("Lyric Files", "*"+ " *".join(LYRICS_EXT)), ("All Files", "*.*")]
        elif file_type == 'cover':
            filetypes = [("Image Files", "*"+ " *".join(COVER_EXT)), ("All Files", "*.*")]
        elif file_type == 'subtitle':
            filetypes = [("Subtitle Files", "*"+ " *".join(SUBTITLE_EXT)), ("All Files", "*.*")]
            # 只有视频文件才能添加字幕
            if media_item['type'] != 'video':
                self.show_message(f"'{os.path.basename(media_item['main_path'])}' 不是视频文件，无法添加字幕。", temporary=False)
                return
        else:
            self.show_message("无效关联文件类型。", temporary=False)
            return

        # 弹出文件选择对话框
        filepath = filedialog.askopenfilename(
            title=f"选择 {file_type} 文件 ({os.path.basename(media_item['main_path'])})",
            filetypes=filetypes
        )
        if filepath:
            # 调用核心逻辑设置关联文件
            success, message = self.player.set_media_association(media_index, file_type, filepath)
            self.show_message(message)
            if success:
                self.update_playlist_display() # 更新播放列表显示，以显示关联信息
                # 如果关联的是当前正在播放的媒体，需要更新显示内容（如显示新封面/歌词/字幕）
                if media_index == self.player.current_index:
                    self.show_current_media_content(media_index) 

    def remove_selected_media(self):
        """从播放列表中移除所有选中的媒体文件。"""
        selected_indices = list(self.playlist_listbox.curselection()) # 获取所有选中项的索引
        if not selected_indices:
            self.show_message("请选择要移除的媒体文件。")
            return
        
        # 弹出确认对话框，防止误操作
        if not messagebox.askyesno("确认移除", f"确定要从播放列表中移除选中的 {len(selected_indices)} 个文件吗？"):
            return

        success, message = self.player.remove_media(selected_indices) # 调用核心逻辑移除文件
        self.show_message(message)
        if success:
            self.update_playlist_display() # 更新播放列表的显示
            # 移除后，重新调整当前选中项或清空选择
            if self.player.current_index != -1 and self.player.current_index < len(self.player.playlist):
                # 如果当前有歌曲在播放，并且它仍在列表中，则重新选中它
                self.playlist_listbox.selection_set(self.player.current_index)
                self.playlist_listbox.activate(self.player.current_index)
                self.playlist_listbox.see(self.player.current_index)
            else: 
                self.playlist_listbox.selection_clear(0, tk.END) # 清空所有选择

            self.update_current_media_display() # 更新媒体信息显示
            # 如果播放列表为空，清除显示区域的内容
            if not self.player.current_media_item:
                self.clear_media_content_display() 
            else:
                self.show_current_media_content(self.player.current_index) # 更新显示区域以反映当前歌曲

    def clear_playlist_action(self):
        """清空整个播放列表。"""
        if not self.player.playlist:
            self.show_message("播放列表已为空。")
            return
        
        # 弹出确认对话框
        if not messagebox.askyesno("清空列表", "确定要清空整个播放列表吗？"):
            return
            
        success, message = self.player.clear_playlist() # 调用核心逻辑清空列表
        self.show_message(message)
        if success:
            self.update_playlist_display() # 更新播放列表显示
            self.update_current_media_display() # 更新媒体信息显示
            self.clear_media_content_display() # 清空显示区域

    def move_media_action(self, direction):
        """
        移动播放列表中选中的媒体项（上移或下移）。
        :param direction: 移动方向 ('up' 或 'down')。
        """
        selected_indices = self.playlist_listbox.curselection()
        if not selected_indices:
            self.show_message("请选择要移动的媒体文件。")
            return
        if len(selected_indices) > 1:
            self.show_message("一次只能移动一个文件。")
            return
        
        index_to_move = selected_indices[0] # 获取唯一选中项的索引
        success, message = self.player.move_media(index_to_move, direction) # 调用核心逻辑移动媒体
        self.show_message(message)
        if success:
            self.update_playlist_display() # 更新播放列表显示
            # 移动后重新选中新位置的项，并滚动到该位置
            new_index = index_to_move + (1 if direction == 'down' else -1)
            self.playlist_listbox.selection_clear(0, tk.END)
            self.playlist_listbox.selection_set(new_index)
            self.playlist_listbox.activate(new_index)
            self.playlist_listbox.see(new_index) 
            self.update_current_media_display() # 更新媒体信息显示（因为索引可能改变）

    def play_action(self):
        """播放当前选中或播放列表中的媒体。"""
        selected_indices = self.playlist_listbox.curselection()
        # 优先播放用户当前选中的歌曲
        if selected_indices and (self.player.current_index == -1 or self.player.current_index != selected_indices[0]): 
            index_to_play = selected_indices[0]
            success, message = self.player.play(index_to_play)
        # 如果没有新选中项，但当前有歌曲被记住，则播放当前歌曲（例如从暂停恢复）
        elif self.player.current_index != -1: 
            success, message = self.player.play(self.player.current_index)
        else: 
            # 否则，尝试播放播放列表中的第一项（如果播放列表有歌曲）
            success, message = self.player.play()

        self.show_message(message, temporary=False) 
        if success:
            self.update_current_media_display() # 更新媒体信息和播放列表高亮
            self.show_current_media_content(self.player.current_index) # 更新显示区域内容

    def pause_action(self):
        """暂停当前播放的媒体。"""
        success, message = self.player.pause() # 调用核心逻辑暂停
        self.show_message(message, temporary=False)

    def unpause_action(self):
        """恢复当前暂停的媒体。"""
        success, message = self.player.unpause() # 调用核心逻辑恢复
        self.show_message(message, temporary=False)

    def stop_action(self):
        """停止当前播放的媒体。"""
        success, message = self.player.stop() # 调用核心逻辑停止
        self.show_message(message, temporary=False)
        self.update_current_media_display() # 更新媒体信息显示
        self.clear_media_content_display() # 停止播放后清空显示区域

    def next_media_action(self):
        """切换到播放列表中的下一首媒体（根据当前播放模式）。"""
        success, message = self.player.next_media() # 调用核心逻辑切换到下一首
        self.show_message(message, temporary=True if "已结束" not in message else False) 
        if success:
            self.update_current_media_display() # 更新媒体信息和播放列表高亮
            self.show_current_media_content(self.player.current_index) # 更新显示区域内容

    def prev_media_action(self):
        """切换到播放列表中的上一首媒体（根据当前播放模式）。"""
        success, message = self.player.prev_media() # 调用核心逻辑切换到上一首
        self.show_message(message)
        if success:
            self.update_current_media_display() # 更新媒体信息和播放列表高亮
            self.show_current_media_content(self.player.current_index) # 更新显示区域内容

    def toggle_playback_mode(self):
        """切换播放模式（顺序、列表循环、单曲循环、随机）。"""
        modes = list(PlaybackMode) # 获取所有播放模式枚举值
        current_mode_index = modes.index(self.player.playback_mode) # 获取当前模式的索引
        next_mode_index = (current_mode_index + 1) % len(modes) # 计算下一个模式的索引（循环）
        self.player.playback_mode = modes[next_mode_index] # 更新核心逻辑中的播放模式
        self.playback_mode_button.config(text=self.player.playback_mode.value) # 更新按钮文本
        self.show_message(f"播放模式已切换到: {self.player.playback_mode.value}")
        logger.info(f"播放模式已切换到: {self.player.playback_mode.value}")

    # --- GUI 辅助更新方法 ---
    def update_playlist_display(self):
        """
        更新播放列表的显示内容。
        遍历核心逻辑中的播放列表数据，并将其格式化显示在 Tkinter Listbox 中。
        """
        self.playlist_listbox.delete(0, tk.END) # 清空 Listbox 的所有现有项
        for i, item in enumerate(self.player.playlist):
            # 获取媒体的标题和艺术家，如果不存在则使用文件名或默认值
            main_name = item.get('title', os.path.basename(item['main_path'])) 
            artist = item.get('artist', '未知')
            
            display_name = f"{i+1}. {main_name}" # 格式化显示为“序号. 标题”
            if artist and artist != '未知' and artist != '网络流': 
                display_name += f" - {artist}" # 添加艺术家信息
            
            # 显示关联文件信息缩写 (L: 歌词, C: 封面, S: 字幕)
            assoc_info = []
            if item.get('lyrics_path') and os.path.exists(item['lyrics_path']): assoc_info.append("L")
            if item.get('cover_path') and os.path.exists(item['cover_path']): assoc_info.append("C")
            if item.get('subtitle_path') and os.path.exists(item['subtitle_path']): assoc_info.append("S")
            if assoc_info:
                display_name += f" [{','.join(assoc_info)}]" # 添加关联文件标记
            
            self.playlist_listbox.insert(tk.END, display_name) # 将格式化后的字符串插入 Listbox
        self.update_current_media_display() # 更新播放状态和高亮，确保 Listbox 正确显示当前歌曲

    def update_history_display(self):
        """
        更新播放历史列表的显示内容。
        遍历核心逻辑中的播放历史数据，并将其格式化显示在 Tkinter Listbox 中。
        历史记录通常倒序显示，最新的在最上面。
        """
        self.history_listbox.delete(0, tk.END) # 清空历史 Listbox 的所有现有项
        # 倒序遍历历史记录，以使最新的记录显示在顶部
        for i, item in enumerate(reversed(self.player.history)):
            main_name = item.get('title', os.path.basename(item['main_path']))
            artist = item.get('artist', '未知')
            
            # 格式化显示为“倒序序号. 标题 - 艺术家”
            display_name = f"{len(self.player.history) - i}. {main_name}" 
            if artist and artist != '未知' and artist != '网络流':
                display_name += f" - {artist}"
            self.history_listbox.insert(tk.END, display_name) # 插入到历史 Listbox

    def update_current_media_display(self):
        """
        更新当前播放媒体的信息显示区域，包括标题、艺术家、专辑、时间、播放状态。
        同时高亮播放列表中的当前歌曲。
        """
        # 从核心逻辑获取当前媒体的最新信息
        file_name, status, current_time_str, total_time_str, current_ms, total_ms, title, artist, album = self.player.get_current_media_info()
        
        # 更新信息标签
        self.current_media_title_label.config(text=f"标题: {title}")
        self.current_media_artist_label.config(text=f"艺术家: {artist}")
        self.current_media_album_label.config(text=f"专辑: {album}")
        
        self.status_label.config(text=f"状态: {status}") 
        self.progress_slider_label.config(text=current_time_str) # 更新当前时间
        self.total_time_label.config(text=total_time_str)       # 更新总时间
        
        # 更新进度条的范围和当前值
        if total_ms > 0:
            self.progress_slider.config(to=total_ms) # 将滑动条的最大值设置为媒体总长度
        else:
            self.progress_slider.config(to=1) # 如果没有长度信息，设置为小值，避免错误
        
        # 如果用户没有正在拖动进度条，则自动更新其位置
        if not self.is_progress_slider_dragging:
            self.progress_slider.set(current_ms)

        # 清除所有列表项的高亮，然后高亮当前播放的歌曲
        self.playlist_listbox.selection_clear(0, tk.END) # 清除所有选中
        for i in range(self.playlist_listbox.size()):
            self.playlist_listbox.itemconfig(i, {'bg': self.playlist_listbox.cget('background')}) # 恢复所有项的默认背景
            
            if i == self.player.current_index:
                self.playlist_listbox.selection_set(i)     # 选中当前项
                self.playlist_listbox.activate(i)          # 激活当前项（使其获得焦点）
                self.playlist_listbox.itemconfig(i, {'bg':'lightblue'}) # 将当前项背景色设为浅蓝色以示高亮
                self.playlist_listbox.see(i)               # 滚动列表框，确保当前项可见
            
        # 更新关联文件按钮和播放列表操作按钮的状态（启用/禁用）
        self._update_associated_buttons_state()
        self._update_playlist_operation_buttons_state()

    def _update_associated_buttons_state(self):
        """根据当前播放列表的选中状态更新关联文件按钮（添加歌词、封面、字幕）的可用性。"""
        selected_indices = self.playlist_listbox.curselection()
        if selected_indices:
            media_index = selected_indices[0] # 获取选中的第一个项的索引
            item = self.player.playlist[media_index] # 获取对应的媒体项数据
            
            is_local_file = item['type'] != 'network_stream' # 判断是否为本地文件（网络流不能关联本地文件）
            
            self.btn_add_lyrics.config(state=tk.NORMAL if is_local_file else tk.DISABLED) # 歌词按钮状态
            self.btn_add_cover.config(state=tk.NORMAL if is_local_file else tk.DISABLED)  # 封面按钮状态
            
            if item['type'] == 'video':
                self.btn_add_subtitle.config(state=tk.NORMAL if is_local_file else tk.DISABLED) # 字幕只对视频且本地文件可用
            else:
                self.btn_add_subtitle.config(state=tk.DISABLED) # 非视频禁用字幕按钮
        else:
            # 如果没有选中任何项，所有关联按钮都禁用
            self.btn_add_lyrics.config(state=tk.DISABLED)
            self.btn_add_cover.config(state=tk.DISABLED)
            self.btn_add_subtitle.config(state=tk.DISABLED)

    def _update_playlist_operation_buttons_state(self):
        """根据播放列表的项数量和选中状态更新操作按钮（移除、清空、上移、下移）的可用性。"""
        num_items = len(self.player.playlist) # 播放列表中的歌曲总数
        selected_indices = self.playlist_listbox.curselection() # 获取所有选中项的索引
        
        # 移除选中按钮：有选中项时启用
        if selected_indices:
            self.btn_remove_selected.config(state=tk.NORMAL)
        else:
            self.btn_remove_selected.config(state=tk.DISABLED)

        # 清空列表按钮：播放列表非空时启用
        if num_items == 0:
            self.btn_clear_playlist.config(state=tk.DISABLED)
        else:
            self.btn_clear_playlist.config(state=tk.NORMAL)

        # 上移/下移按钮：仅当且仅当选中一项时，且未在列表边缘时启用
        if len(selected_indices) == 1: # 确保只选中一项
            idx = selected_indices[0]
            if idx > 0: # 如果不是第一项，可以上移
                self.btn_move_up.config(state=tk.NORMAL)
            else:
                self.btn_move_up.config(state=tk.DISABLED)
            
            if idx < num_items - 1: # 如果不是最后一项，可以下移
                self.btn_move_down.config(state=tk.NORMAL)
            else:
                self.btn_move_down.config(state=tk.DISABLED)
        else:
            # 如果没有选中项或选中多项，上移/下移按钮禁用
            self.btn_move_up.config(state=tk.DISABLED)
            self.btn_move_down.config(state=tk.DISABLED)

    def show_current_media_content(self, media_index):
        """
        在显示区域显示当前播放媒体的内容 (视频、封面图片或歌词)。
        :param media_index: 当前播放媒体在播放列表中的索引。
        """
        self.clear_media_content_display() # 首先清空当前显示区域的内容

        if not (0 <= media_index < len(self.player.playlist)):
            return # 无效索引，不显示任何内容

        current_item = self.player.playlist[media_index] # 获取当前媒体项的数据

        if current_item['type'] == 'video':
            # 如果是视频文件，将 VLC 视频输出绑定到指定面板 (`self.video_panel`)
            if self.player.player: 
                self.setup_vlc_video_output() # 重新设置 VLC 视频输出
                # 如果有字幕文件，加载字幕
                if current_item['subtitle_path'] and os.path.exists(current_item['subtitle_path']):
                    self.player.player.video_set_subtitle_file(current_item['subtitle_path'])
            
            # 视频模式下，隐藏歌词面板和图片标签，确保视频能独占显示区域
            self.lyrics_frame.pack_forget() 
            self.image_label.pack_forget() 
            self.current_displayed_image = None # 清除图片引用
            return

        # 以下处理音频文件及其关联内容，或者没有视频时的显示逻辑
        if self.player.player:
            # 对于音频文件，明确将 VLC 的视频输出句柄设为0 (隐藏 VLC 视频窗口)，
            # 防止 VLC 意外显示一个黑色的视频窗口。
            if sys.platform.startswith('linux'):
                self.player.player.set_xwindow(0) 
            elif sys.platform == 'darwin':
                self.player.player.set_nsobject(0) 
            else: # Windows
                self.player.player.set_hwnd(0) 
            self.player.player.video_set_subtitle_file(None) # 确保音频播放时没有字幕

        cover_displayed = False
        if current_item.get('cover_path') and os.path.exists(current_item['cover_path']):
            # 如果媒体项有关联的封面图片，尝试加载并显示
            try:
                img = Image.open(current_item['cover_path'])
                self.update_idletasks() # 强制更新 Tkinter 窗口，确保面板的尺寸信息是最新的
                panel_width = self.video_panel.winfo_width()
                panel_height = self.video_panel.winfo_height()

                # 如果面板尺寸过小 (例如，刚启动时 Tkinter 还没完全渲染)，使用一个默认的安全尺寸
                if panel_width < 100 or panel_height < 100: 
                    panel_width = max(self.display_frame.winfo_width(), 600)
                    panel_height = max(self.display_frame.winfo_height(), 400)

                # 缩放图片以适应面板，保持图片比例，使用 LANCZOS 算法保证缩放质量
                img.thumbnail((panel_width, panel_height), Image.LANCZOS) 
                
                self.current_displayed_image = ImageTk.PhotoImage(img) # 转换为 Tkinter 图像对象
                self.image_label.config(image=self.current_displayed_image) # 设置图片标签的图像
                self.image_label.pack(expand=True, fill=tk.BOTH) # 显示图片标签
                self.lyrics_frame.pack_forget() # 隐藏歌词面板
                cover_displayed = True

            except (IOError, UnidentifiedImageError, Exception) as e:
                # 捕获图片加载过程中的任何错误
                logger.error(f"加载封面图片失败 '{current_item['cover_path']}': {e}")
                self.show_message(f"加载封面图片失败: {e}")
                self.image_label.pack_forget() # 隐藏图片标签
                self.current_displayed_image = None
                cover_displayed = False

        if not cover_displayed and current_item.get('lyrics_path') and os.path.exists(current_item['lyrics_path']):
            # 如果没有封面图片，但有歌词文件，则加载并显示歌词
            self.current_lyrics_data = self.player.load_lyrics_content(current_item['lyrics_path'])
            self.lyrics_text.delete(1.0, tk.END) # 清空旧歌词文本
            for i, (_, lyric) in enumerate(self.current_lyrics_data):
                self.lyrics_text.insert(tk.END, lyric + '\n', "normal") # 插入新歌词
            
            self.lyrics_frame.pack(side="right", fill="y", padx=5) # 显示歌词面板
            self.image_label.pack_forget() # 隐藏图片标签
        elif not cover_displayed:
            # 既没有视频，也没有封面，也没有歌词，则显示默认的占位图
            self.image_label.config(image=self.default_placeholder_image)
            self.image_label.pack(expand=True, fill=tk.BOTH)
            self.lyrics_frame.pack_forget() # 隐藏歌词面板
            

    def clear_media_content_display(self):
        """
        清空显示区的所有内容 (视频、图片、歌词)，并强制显示默认占位图。
        同时确保 VLC 视频输出被隐藏。
        """
        # 清空歌词文本框，并隐藏歌词面板
        self.lyrics_text.delete(1.0, tk.END)
        self.lyrics_frame.pack_forget()
        self.current_lyrics_data = [] # 清空当前歌词数据

        # 清空当前显示的图片并强制显示默认占位符
        self.image_label.config(image=self.default_placeholder_image)
        self.image_label.pack(expand=True, fill=tk.BOTH)
        self.current_displayed_image = self.default_placeholder_image # 更新当前显示的图片引用

        # 确保 VLC 的视频输出被隐藏，并清除可能加载的字幕
        if self.player.player:
            if sys.platform.startswith('linux'):
                self.player.player.set_xwindow(0) # 将 VLC 视频输出句柄设为 0 (隐藏)
            elif sys.platform == 'darwin':
                self.player.player.set_nsobject(0) 
            else: # Windows
                self.player.player.set_hwnd(0) 
            self.player.player.video_set_subtitle_file(None) # 清除任何已加载的字幕

    def update_lyrics_highlight(self, current_time_ms):
        """
        根据当前播放时间 (毫秒) 更新歌词高亮显示。
        使当前播放的歌词行高亮，并自动滚动歌词文本框。
        :param current_time_ms: 当前播放时间 (毫秒)。
        """
        if not self.current_lyrics_data:
            return # 如果没有歌词数据，则不执行任何操作

        # 获取当前时间对应的歌词行索引
        current_line_index = self.player.get_current_lyric_line_index(current_time_ms, self.current_lyrics_data)
        
        # 移除所有现有的高亮，然后将所有行设为正常样式
        self.lyrics_text.tag_remove("highlight", "1.0", tk.END)
        self.lyrics_text.tag_add("normal", "1.0", tk.END)

        if current_line_index != -1:
            # 计算高亮行的开始和结束索引 (Tkinter 文本索引是 "行.列")
            start_index = f"{current_line_index + 1}.0"
            end_index = f"{current_line_index + 1}.end"
            # 应用高亮样式并移除正常样式
            self.lyrics_text.tag_add("highlight", start_index, end_index)
            self.lyrics_text.tag_remove("normal", start_index, end_index)

            # 自动滚动歌词文本框，使当前高亮行保持在可视区域的约 1/3 处
            line_height = self.lyrics_text.font_metrics("linespace") # 获取每行文本的高度
            text_height_pixels = self.lyrics_text.winfo_height()     # 获取文本框的像素高度
            if text_height_pixels > 0 and line_height > 0:
                visible_lines_count = text_height_pixels // line_height # 计算可视行数
                target_offset_lines = visible_lines_count // 3 # 目标偏移量，使高亮行在可视区靠上位置
                scroll_to_line = max(0, current_line_index - target_offset_lines) # 计算目标滚动到的行号
                self.lyrics_text.see(f"{scroll_to_line + 1}.0") # 滚动到指定行

    def on_listbox_select(self, event):
        """
        处理播放列表项选中事件。
        当用户在播放列表中选择歌曲时，更新 UI 状态和显示内容。
        """
        selected_indices = self.playlist_listbox.curselection()
        if selected_indices:
            selected_media_index = selected_indices[0] # 获取选中的第一个项的索引
            
            self.update_current_media_display() # 更新媒体信息显示（包括播放列表高亮）

            # 只有当选中的歌曲发生变化时，才更新显示区域的内容，避免重复加载资源
            if self.player.current_index is None or selected_media_index != self.player.current_index:
                self.show_current_media_content(selected_media_index)
            elif self.player.current_media_item: 
                # 如果是重新选中当前正在播放的歌曲，确保显示内容是最新的
                self.show_current_media_content(self.player.current_index)
            else: 
                self.clear_media_content_display() # 清空显示区域

        else:
            # 如果没有选中任何项，则禁用关联文件按钮和播放列表操作按钮，并清空显示区域
            self._update_associated_buttons_state()
            self._update_playlist_operation_buttons_state() 
            self.clear_media_content_display() 

    def on_listbox_double_click(self, event):
        """处理播放列表项双击事件，双击播放选中歌曲。"""
        self.play_action() # 调用播放操作

    def on_history_listbox_select(self, event):
        """
        处理播放历史列表项选中事件。
        当用户在播放历史中选中歌曲时，尝试在播放列表中找到并高亮该歌曲。
        """
        selected_indices = self.history_listbox.curselection()
        if selected_indices:
            history_list_index = selected_indices[0]
            # 播放历史列表是倒序显示（最新在最上面），所以需要转换到实际在历史数据中的索引
            actual_history_index = len(self.player.history) - 1 - history_list_index
            selected_history_item = self.player.history[actual_history_index]
            
            found_in_playlist = False
            # 尝试在当前播放列表中找到该历史项并选中它
            for i, item in enumerate(self.player.playlist):
                if item['main_path'] == selected_history_item['main_path']:
                    self.playlist_listbox.selection_clear(0, tk.END) # 清除播放列表的现有选中
                    self.playlist_listbox.selection_set(i)          # 选中找到的歌曲
                    self.playlist_listbox.activate(i)               # 激活（聚焦）该歌曲
                    self.playlist_listbox.see(i)                    # 滚动到该歌曲
                    found_in_playlist = True
                    self.notebook.select(self.playlist_tab) # 切换到播放列表标签页
                    break
            
            if not found_in_playlist:
                self.show_message("该历史记录项不在当前播放列表中。") # 如果没找到，显示消息

    def on_history_listbox_double_click(self, event):
        """
        处理播放历史列表项双击事件，双击播放历史歌曲。
        如果歌曲在播放列表中，则播放它；如果不在，则先添加到播放列表再播放。
        """
        selected_indices = self.history_listbox.curselection()
        if selected_indices:
            history_list_index = selected_indices[0]
            actual_history_index = len(self.player.history) - 1 - history_list_index
            selected_history_item = self.player.history[actual_history_index]

            # 尝试在当前播放列表中找到该历史项并播放
            for i, item in enumerate(self.player.playlist):
                if item['main_path'] == selected_history_item['main_path']:
                    self.player.play(i) # 播放找到的歌曲
                    self.update_current_media_display()
                    self.show_current_media_content(i)
                    self.notebook.select(self.playlist_tab) # 切换到播放列表标签页
                    return
            
            # 如果历史项不在当前播放列表中，则先将其添加到播放列表，然后播放
            success, message = self.player.add_media(selected_history_item['main_path'])
            self.show_message(message)
            if success:
                self.update_playlist_display() # 更新播放列表显示
                self.player.play(len(self.player.playlist) - 1) # 播放新添加的项（它将是列表的最后一项）
                self.update_current_media_display()
                self.show_current_media_content(self.player.current_index)
                self.notebook.select(self.playlist_tab) # 切换到播放列表标签页

    def update_gui_periodic(self):
        """
        周期性更新 GUI 界面，包括媒体信息、进度条、歌词高亮等。
        这是 Tkinter 的主循环中最重要的部分，通过 `self.after()` 方法实现。
        """
        self.update_current_media_display() # 更新媒体信息和进度条
        self.update_history_display() # 确保历史记录的显示是最新的

        # 只有在音频播放中且有歌词文件时才更新歌词高亮
        if self.player.current_media_item and \
           self.player.current_media_item['type'] == 'audio' and \
           self.player.current_media_item.get('lyrics_path') and \
           os.path.exists(self.player.current_media_item['lyrics_path']) and \
           self.player.player and self.player.player.is_playing():
            current_time_ms = self.player.player.get_time() # 获取当前播放时间
            self.update_lyrics_highlight(current_time_ms) # 更新歌词高亮
        else:
            # 如果没有歌词或不在播放音频，则清除歌词高亮
            self.lyrics_text.tag_remove("highlight", "1.0", tk.END)
            self.lyrics_text.tag_add("normal", "1.0", tk.END) # 确保所有歌词恢复正常样式

        self.after(100, self.update_gui_periodic) # 每 100 毫秒 (0.1 秒) 再次调用自身，实现周期性更新

    def on_closing(self):
        """
        处理窗口关闭事件。
        在应用程序退出前，执行必要的清理工作：保存所有数据并释放 VLC 资源。
        """
        # 弹出确认对话框，防止用户意外关闭
        if messagebox.askokcancel("退出", "确定要退出播放器吗？"):
            # 保存播放列表和历史记录数据
            self.playlist_manager.save_playlist_to_file()
            self.playlist_manager.save_history_to_file()
            logger.info("播放列表和历史记录已在退出前保存。")

            self.player.quit() # 调用核心逻辑层的 quit 方法，释放 VLC 资源
            self.destroy() # 销毁 Tkinter 窗口，结束应用程序