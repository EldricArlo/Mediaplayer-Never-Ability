# media_player_project/core/media_info.py

import os
import re
import logging

# 导入 Mutagen 库，用于读取媒体文件的 ID3 标签或其他元数据
try:
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3NoHeaderError, ID3
    from mutagen.flac import FLAC
    from mutagen.oggvorbis import OggVorbis
    from mutagen.mp4 import MP4
    MUTAGEN_AVAILABLE = True
except ImportError:
    # 如果 Mutagen 模块未安装，记录警告并禁用相关功能
    MUTAGEN_AVAILABLE = False
except Exception as e:
    # 捕获其他可能的 Mutagen 导入错误
    MUTAGEN_AVAILABLE = False

# 导入项目工具模块中的常量和日志器
from ..utils.constants import SUPPORTED_MEDIA_EXT, LYRICS_EXT, COVER_EXT, SUBTITLE_EXT
from ..utils.logger_config import get_logger

# 获取当前模块的 logger 实例
logger = get_logger('MediaPlayer.Core.MediaInfo')

class MediaInfoReader:
    """
    媒体文件信息读取器。
    提供读取媒体文件类型、标签（如标题、艺术家、专辑）和查找关联文件的功能。
    """

    def get_media_type(self, filepath):
        """
        根据文件扩展名判断媒体类型 (视频, 音频, 或未知)。
        :param filepath: 媒体文件的完整路径。
        :return: 'video', 'audio', 或 'unknown'。
        """
        ext = os.path.splitext(filepath)[1].lower() # 获取文件扩展名并转为小写
        if ext in SUPPORTED_MEDIA_EXT:
            if ext in ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.ts', '.m2ts']:
                return 'video'
            elif ext in ['.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a', '.opus', '.wma']:
                return 'audio'
        return 'unknown'

    def get_media_tags(self, filepath):
        """
        使用 Mutagen 库读取媒体文件的 ID3 标签（标题、艺术家、专辑）。
        如果 Mutagen 不可用或读取失败，返回空字典。
        :param filepath: 媒体文件的完整路径。
        :return: 包含 'title', 'artist', 'album' 的字典。
        """
        if not MUTAGEN_AVAILABLE:
            return {} # Mutagen 不可用，直接返回空标签

        tags = {}
        ext = os.path.splitext(filepath)[1].lower() # 获取文件扩展名
        try:
            # 根据文件类型使用 Mutagen 对应的解析器
            if ext == '.mp3':
                audio = MP3(filepath, ID3=ID3) # 尝试使用 ID3v2 标签
                if audio.tags:
                    tags['title'] = audio.tags.get('TIT2', [''])[0] # TIT2: 标题
                    tags['artist'] = audio.tags.get('TPE1', [''])[0] # TPE1: 艺术家
                    tags['album'] = audio.tags.get('TALB', [''])[0] # TALB: 专辑
            elif ext == '.flac':
                audio = FLAC(filepath)
                tags['title'] = audio.get('title', [''])[0]
                tags['artist'] = audio.get('artist', [''])[0]
                tags['album'] = audio.get('album', [''])[0]
            elif ext == '.ogg':
                audio = OggVorbis(filepath)
                tags['title'] = audio.get('title', [''])[0]
                tags['artist'] = audio.get('artist', [''])[0]
                tags['album'] = audio.get('album', [''])[0]
            elif ext == '.mp4' or ext == '.m4a':
                audio = MP4(filepath)
                # MP4/M4A 的标签键是特殊的
                tags['title'] = audio.get('\xa9nam', [''])[0] # ©nam: 标题
                tags['artist'] = audio.get('\xa9ART', [''])[0] # ©ART: 艺术家
                tags['album'] = audio.get('\xa9alb', [''])[0] # ©alb: 专辑
            logger.debug(f"已从 '{os.path.basename(filepath)}' 读取标签: {tags}")
        except ID3NoHeaderError:
            # MP3 文件没有 ID3 标签头
            logger.debug(f"文件 '{filepath}' 没有 ID3 标签头。")
        except Exception as e:
            logger.error(f"读取文件 '{filepath}' 的媒体标签失败: {e}")
        return tags

    def find_associated_files(self, main_path):
        """
        在主媒体文件同目录下查找潜在的关联文件 (歌词、封面、字幕)。
        通常以相同的基础文件名但不同扩展名存在。
        :param main_path: 主媒体文件的完整路径。
        :return: (lyrics_path, cover_path, subtitle_path) 的元组。
        """
        base_name, _ = os.path.splitext(main_path) # 获取不带扩展名的文件名
        
        lyrics_path = None
        cover_path = None
        subtitle_path = None

        # 查找歌词文件
        for ext in LYRICS_EXT:
            potential_path = base_name + ext
            if os.path.exists(potential_path):
                lyrics_path = potential_path
                break # 找到一个就停止
        
        # 查找封面图片文件
        for ext in COVER_EXT:
            potential_path = base_name + ext
            if os.path.exists(potential_path):
                cover_path = potential_path
                break
        
        # 查找字幕文件
        for ext in SUBTITLE_EXT: 
            potential_path = base_name + ext
            if os.path.exists(potential_path):
                subtitle_path = potential_path
                break

        return lyrics_path, cover_path, subtitle_path