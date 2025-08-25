# media_player_project/utils/constants.py

import os
from enum import Enum

# --- 配置文件路径定义 ---
# 这些文件用于持久化应用的设置、播放列表和播放历史。
# 路径是相对于 'media_player_project' 目录下的 'data' 文件夹。
VLC_CONFIG_FILE = os.path.join("data", "vlc_config.json")
PLAYLIST_FILE = os.path.join("data", "playlist.json")
HISTORY_FILE = os.path.join("data", "history.json")

# --- 播放模式枚举定义 ---
# 定义播放器支持的几种播放模式，提高代码可读性和可维护性。
class PlaybackMode(Enum):
    SEQUENTIAL = "顺序播放"  # 按照列表顺序播放，到末尾停止
    LOOP_ALL = "列表循环"    # 列表播放完后从头开始循环
    LOOP_ONE = "单曲循环"    # 当前歌曲循环播放
    SHUFFLE = "随机播放"    # 随机选择下一首歌曲

# --- 支持的媒体文件扩展名 ---
# 用于过滤和识别可播放的音频和视频文件。
SUPPORTED_MEDIA_EXT = [
    # 常见音频格式
    '.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a', '.opus', '.wma',  
    # 常见视频格式
    '.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.ts', '.m2ts' 
]

# --- 关联文件扩展名 ---
# 用于自动查找或手动关联媒体文件旁边的歌词、封面和字幕文件。
LYRICS_EXT = ['.lrc', '.txt']
COVER_EXT = ['.jpg', '.jpeg', '.png', '.gif', '.bmp']
SUBTITLE_EXT = ['.srt', '.ass', '.ssa', '.vtt']

# --- 默认占位图路径 ---
# 当没有视频内容或封面图片时，用于显示在播放区域的默认图片。
# 路径是相对于 'media_player_project' 目录下的 'assets' 文件夹。
DEFAULT_LOGO_PATH = os.path.join("assets", "player_logo.png")