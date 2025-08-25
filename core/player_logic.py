# media_player_project/core/player_logic.py

import vlc
import os
import time
import re
import random
import sys
import logging

# 导入核心逻辑的子模块和工具模块
from .media_info import MediaInfoReader # 用于获取媒体信息
from .playlist_manager import PlaylistManager # 用于管理播放列表数据
from .equalizer_control import EqualizerControl # 用于控制均衡器
from ..utils.constants import PlaybackMode, SUPPORTED_MEDIA_EXT # 导入常量和播放模式枚举
from ..utils.logger_config import get_logger # 导入日志器

# 获取当前模块的 logger 实例
logger = get_logger('MediaPlayer.Core.PlayerLogic')

class MediaPlayerLogic:
    """
    媒体播放器的核心逻辑类。
    封装了 VLC 库的交互、播放控制、播放模式管理、音量/速度调节。
    它协调媒体信息读取、播放列表管理和均衡器控制。
    """
    def __init__(self, vlc_path=None):
        self.instance = None          # VLC 实例 (vlc.Instance)
        self.player = None            # VLC 媒体播放器 (vlc.MediaPlayer)
        self.event_manager = None     # VLC 事件管理器

        # 媒体信息读取器实例
        self.media_info_reader = MediaInfoReader()

        # 播放列表和历史记录数据由 PlaylistManager 管理，这里只持有引用
        # 实际的列表对象会在初始化 GUI 时通过 setter 传入
        self.playlist = []            
        self.history = []
        self.current_index = -1        # 当前播放歌曲在播放列表中的索引
        self.current_media_item = None # 当前播放的媒体项字典 (包含路径、类型、标签等)
        
        self.volume = 0.5              # 初始音量 (0.0 - 1.0)
        self.playback_rate = 1.0       # 初始播放速度
        self.playback_mode = PlaybackMode.SEQUENTIAL # 初始播放模式枚举值

        # 均衡器控制器实例
        self.equalizer_control = None
        self.equalizer = None # 指向 equalizer_control 内部的 vlc.AudioEqualizer 对象

        # 尝试初始化 VLC 实例和播放器
        self._initialize_vlc_instance(vlc_path)
        
        # 如果 VLC 实例和播放器成功创建，则进行进一步配置
        if self.instance and self.player:
            # 初始化均衡器控制器，并将其内部的 vlc.AudioEqualizer 对象引用到 self.equalizer
            self.equalizer_control = EqualizerControl(self.instance, self.player)
            self.equalizer = self.equalizer_control.equalizer # 方便直接访问 vlc.AudioEqualizer 对象

            self.player.audio_set_volume(int(self.volume * 100)) # 设置初始音量
            self.player.set_rate(self.playback_rate)             # 设置初始播放速度
            self._setup_vlc_events()                              # 绑定 VLC 事件
            logger.info("媒体播放器逻辑初始化完成。")
            
            # 如果播放列表已加载，且当前没有选中歌曲，则默认选中第一首
            if self.playlist and self.current_index == -1:
                self.current_index = 0
                self.current_media_item = self.playlist[self.current_index]
        else:
            logger.error("VLC 实例初始化失败，播放功能将受限。")
            self.player = None
            self.instance = None

    def _initialize_vlc_instance(self, vlc_path_from_gui):
        """
        根据提供的路径初始化 VLC 实例和媒体播放器。
        会尝试将 VLC 的 DLL 目录添加到系统路径 (Windows)。
        此方法封装了 VLC 初始化过程中的所有潜在错误和日志记录。
        """
        logger.info(f"尝试初始化 VLC，传入路径: {vlc_path_from_gui}")
        logger.debug(f"当前 sys.path: {sys.path}")

        # 可选：VLC 命令行参数，用于调试或特殊配置。
        # 例如，可以用于强制音频输出模块，或增加日志级别。
        vlc_args = []
        # vlc_args = ["--verbose=2", "--no-video"] # 调试示例：增加日志并禁用视频
        # vlc_args = ["--aout=directsound"] # 调试示例：Windows 强制使用 DirectSound 音频输出

        if vlc_path_from_gui:
            if sys.platform.startswith('win'):
                try:
                    # 对于 Python 3.8+ 在 Windows 上，需要添加 VLC DLL 搜索路径。
                    # 这有助于 Python 找到 libvlc.dll 和 libvlccore.dll。
                    os.add_dll_directory(vlc_path_from_gui)
                    logger.info(f"已尝试添加 VLC 主目录到 DLL 搜索路径: {vlc_path_from_gui}")
                    
                    # 某些 VLC 安装 (如 SDK) 将 libvlc.dll 放在 'sdk/lib' 子目录中。
                    sdk_lib_path = os.path.join(vlc_path_from_gui, 'sdk', 'lib')
                    if os.path.exists(sdk_lib_path):
                        os.add_dll_directory(sdk_lib_path)
                        logger.info(f"已尝试添加 VLC SDK lib 目录到 DLL 搜索路径: {sdk_lib_path}")
                except OSError as e:
                    # 捕获添加 DLL 目录时的操作系统错误，可能是权限问题或目录已存在。
                    logger.warning(f"添加 DLL 目录失败 (可能权限问题或目录已存在): {e}")
                except Exception as e:
                    logger.error(f"添加 DLL 目录时发生未知错误: {e}", exc_info=True)

            try:
                # 尝试创建 VLC 实例。这是 VLC 库的入口点。
                self.instance = vlc.Instance(vlc_args) 
                # 从 VLC 实例创建媒体播放器对象。
                self.player = self.instance.media_player_new()
                logger.info(f"VLC 实例已成功使用路径 '{vlc_path_from_gui}' 初始化。")
                return # 成功初始化后返回
            except vlc.VlcError as e: 
                # 捕获 VLC 库特有的错误，通常是由于 VLC 安装问题。
                logger.critical(f"无法创建 VLC 实例。VLC Core 错误: {e}. 请确保 VLC 已正确安装且路径 '{vlc_path_from_gui}' 有效。", exc_info=True)
            except Exception as e:
                # 捕获其他通用异常，以防万一。
                logger.critical(f"初始化 VLC 媒体播放器时发生未知错误: {e}", exc_info=True)
            
            # 如果初始化失败 (即捕获到异常)，则将实例和播放器对象设为 None。
            # 这表示 VLC 功能不可用。
            self.instance = None 
            self.player = None
        else:
            # 如果没有提供有效的 VLC 路径，则无法进行初始化。
            logger.error("未提供有效的 VLC 路径，无法初始化 VLC 实例。")
            self.instance = None
            self.player = None

    def _setup_vlc_events(self):
        """
        设置 VLC 播放器事件管理器，并绑定媒体播放结束事件。
        当一首歌曲播放完毕时，会自动触发 `_on_media_ended` 方法。
        """
        if self.player:
            self.event_manager = self.player.event_manager()
            # 绑定 MediaPlayerEndReached 事件，当歌曲播放结束时触发
            self.event_manager.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_media_ended)
            logger.info("VLC 事件管理器已设置。")

    def _on_media_ended(self, event):
        """
        VLC 媒体播放结束事件的回调函数。
        根据当前播放模式自动播放下一首媒体。
        """
        logger.info("媒体播放结束事件触发。")
        self.next_media() 

    def add_media(self, input_path):
        """
        将一个媒体文件或网络流添加到播放列表。
        自动识别媒体类型，并尝试读取标签和查找关联文件。
        :param input_path: 文件路径或网络流 URL。
        :return: (True, 消息) 如果添加成功，否则 (False, 错误消息)。
        """
        # 判断是否是网络流
        if input_path.startswith(('http://', 'https://', 'rtmp://', 'rtsp://', 'ftp://')):
            media_item = {
                'main_path': input_path,
                'type': 'network_stream', 
                'lyrics_path': None,
                'cover_path': None,
                'subtitle_path': None,
                'title': input_path, # 网络流通常直接用 URL 作为标题
                'artist': '网络流',
                'album': '网络流'
            }
            # 检查网络流是否已在播放列表中
            if any(item['main_path'] == input_path for item in self.playlist):
                logger.info(f"网络流 '{input_path}' 已在播放列表中。")
                return False, f"网络流 '{input_path}' 已在播放列表中。"

            self.playlist.append(media_item) # 添加到播放列表
            # 如果播放列表之前为空，且这是第一首歌，则将其设为当前播放歌曲
            if self.current_index == -1 and len(self.playlist) == 1:
                self.current_index = 0
                self.current_media_item = self.playlist[self.current_index]
            logger.info(f"已添加网络流: {input_path}")
            return True, f"已添加到播放列表: {input_path}"

        # 处理本地文件
        if not os.path.exists(input_path):
            logger.warning(f"错误: 文件未找到 - {input_path}")
            return False, f"错误: 文件未找到 - {input_path}"
        
        # 检查文件是否已在播放列表中
        if any(item['main_path'] == input_path for item in self.playlist):
            logger.info(f"文件 '{os.path.basename(input_path)}' 已在播放列表中。")
            return False, f"文件 '{os.path.basename(input_path)}' 已在播放列表中。"

        # 获取媒体文件类型
        media_type = self.media_info_reader.get_media_type(input_path)
        if media_type == 'unknown':
            logger.warning(f"不支持的文件类型: {os.path.basename(input_path)}")
            return False, f"不支持的文件类型: {os.path.basename(input_path)}"

        # 查找关联文件 (歌词、封面、字幕)
        lyrics_path, cover_path, subtitle_path = self.media_info_reader.find_associated_files(input_path)
        # 读取媒体标签
        tags = self.media_info_reader.get_media_tags(input_path)

        # 构建媒体项字典
        media_item = {
            'main_path': input_path,
            'type': media_type,
            'lyrics_path': lyrics_path,
            'cover_path': cover_path,
            # 字幕只对视频文件有效
            'subtitle_path': subtitle_path if media_type == 'video' else None, 
            'title': tags.get('title', os.path.basename(input_path)), # 优先使用标签标题
            'artist': tags.get('artist', '未知艺术家'),
            'album': tags.get('album', '未知专辑')
        }
        self.playlist.append(media_item) # 添加到播放列表
        # 如果播放列表之前为空，且这是第一首歌，则将其设为当前播放歌曲
        if self.current_index == -1 and len(self.playlist) == 1:
            self.current_index = 0
            self.current_media_item = self.playlist[self.current_index] 
        logger.info(f"已添加到播放列表: {os.path.basename(input_path)}")
        return True, f"已添加到播放列表: {os.path.basename(input_path)}"

    def load_playlist_from_folder(self, folder_path):
        """
        加载指定文件夹中所有支持的媒体文件到播放列表。
        :param folder_path: 要加载的文件夹路径。
        :return: (添加的文件数量, 消息)。
        """
        if not os.path.isdir(folder_path):
            logger.error(f"错误: 文件夹未找到 - {folder_path}")
            return 0, f"错误: 文件夹未找到 - {folder_path}"

        new_items_added = 0
        for filename in os.listdir(folder_path):
            filepath = os.path.join(folder_path, filename)
            if os.path.isfile(filepath):
                ext = os.path.splitext(filepath)[1].lower()
                # 检查文件是否是支持的媒体类型
                if ext in SUPPORTED_MEDIA_EXT:
                    success, _ = self.add_media(filepath) # 调用 add_media 添加
                    if success:
                        new_items_added += 1
        
        if new_items_added > 0:
            # 如果播放列表之前为空，且添加了新歌曲，则将第一首设为当前播放歌曲
            if self.current_index == -1 and len(self.playlist) > 0:
                self.current_index = 0 
                self.current_media_item = self.playlist[self.current_index]
            logger.info(f"已从 '{folder_path}' 加载 {new_items_added} 个新文件。")
            return new_items_added, f"已从 '{folder_path}' 加载 {new_items_added} 个新文件。"
        else:
            logger.info(f"在 '{folder_path}' 中未找到支持的媒体文件，或所有文件已在列表中。")
            return 0, f"在 '{folder_path}' 中未找到支持的媒体文件，或所有文件已在列表中。"

    def set_media_association(self, media_index, file_type, associated_filepath):
        """
        为播放列表中的指定媒体项设置关联文件（歌词、封面、字幕）。
        :param media_index: 媒体项在播放列表中的索引。
        :param file_type: 关联文件类型 ('lyrics', 'cover', 'subtitle')。
        :param associated_filepath: 关联文件的完整路径。
        :return: (True, 消息) 如果设置成功，否则 (False, 错误消息)。
        """
        if not (0 <= media_index < len(self.playlist)):
            logger.warning(f"设置关联文件失败: 无效的媒体索引 {media_index}。")
            return False, "无效的媒体索引。"
        
        if not os.path.exists(associated_filepath):
            logger.warning(f"设置关联文件失败: 关联文件未找到 - {associated_filepath}")
            return False, f"关联文件未找到: {associated_filepath}"
        
        item = self.playlist[media_index]
        # 网络流不能设置本地关联文件
        if item['type'] == 'network_stream':
            logger.warning(f"无法为网络流 '{os.path.basename(item['main_path'])}' 设置关联文件。")
            return False, "无法为网络流设置关联文件。"

        old_path = None
        message_suffix = ""

        if file_type == 'lyrics':
            old_path = item.get('lyrics_path')
            item['lyrics_path'] = associated_filepath
            message_suffix = "歌词"
        elif file_type == 'cover':
            old_path = item.get('cover_path')
            item['cover_path'] = associated_filepath
            message_suffix = "封面"
        elif file_type == 'subtitle':
            # 字幕只能为视频文件设置
            if item['type'] != 'video':
                logger.warning(f"文件 '{os.path.basename(item['main_path'])}' 不是视频文件，无法添加字幕。")
                return False, f"文件 '{os.path.basename(item['main_path'])}' 不是视频文件，无法添加字幕。"
            old_path = item.get('subtitle_path')
            item['subtitle_path'] = associated_filepath
            message_suffix = "字幕"
            # 如果关联的是当前播放的视频，则实时更新 VLC 的字幕文件
            if self.current_index == media_index and self.player and self.player.is_playing():
                self.player.video_set_subtitle_file(item['subtitle_path'])
        else:
            logger.warning(f"设置关联文件失败: 无效的关联文件类型 '{file_type}'。")
            return False, "无效的关联文件类型。"
        
        # 如果当前播放的媒体项被修改，更新内部引用
        if self.current_index == media_index:
            self.current_media_item = item 
            
        logger.info(f"已为 '{os.path.basename(item['main_path'])}' 设置 {message_suffix} 文件: {associated_filepath}")
        return True, f"已为 '{os.path.basename(item['main_path'])}' 设置 {message_suffix} 文件。"

    def remove_media(self, indices):
        """
        从播放列表中移除指定索引的媒体项。
        :param indices: 要移除的媒体项索引列表。
        :return: (True, 消息) 如果移除成功，否则 (False, 错误消息)。
        """
        if not isinstance(indices, list):
            indices = [indices]
        
        if not indices:
            return False, "未选择要移除的媒体。"

        # 从大到小排序索引，防止删除元素后索引错位
        indices.sort(reverse=True)
        
        removed_count = 0
        for idx in indices:
            if 0 <= idx < len(self.playlist):
                # 如果移除的是当前播放的歌曲，则停止播放并重置索引
                if self.current_index == idx:
                    self.stop() 
                    self.current_index = -1 
                # 如果当前播放歌曲在被移除歌曲的后面，则当前索引减一
                elif self.current_index > idx:
                    self.current_index -= 1 
                
                logger.info(f"从播放列表移除: {os.path.basename(self.playlist[idx]['main_path'])}")
                del self.playlist[idx] # 从列表中删除
                removed_count += 1
            else:
                logger.warning(f"尝试移除无效索引 {idx}")

        if removed_count > 0:
            # 移除后重新调整当前播放索引和媒体项
            if not self.playlist: # 如果列表为空
                self.current_index = -1
                self.current_media_item = None
            elif self.current_index == -1 and self.playlist: # 如果原来没有选中，现在有歌曲了，选中第一首
                self.current_index = 0 
                self.current_media_item = self.playlist[self.current_index]
            # 如果当前索引超出了新列表范围，则将其设为新列表的最后一项
            elif self.current_index >= len(self.playlist) and self.playlist: 
                 self.current_index = len(self.playlist) - 1
                 self.current_media_item = self.playlist[self.current_index]
            
            logger.info(f"已移除 {removed_count} 个媒体文件。")
            return True, f"已移除 {removed_count} 个媒体文件。"
        return False, "未移除任何文件。"

    def clear_playlist(self):
        """清空整个播放列表。"""
        self.stop() # 停止当前播放
        self.playlist.clear() # 清空列表数据
        self.current_index = -1 # 重置索引
        self.current_media_item = None # 清空当前媒体项
        logger.info("播放列表已清空。")
        return True, "播放列表已清空。"

    def move_media(self, index, direction):
        """
        移动播放列表中指定索引的媒体项（上移或下移）。
        :param index: 要移动的媒体项的当前索引。
        :param direction: 移动方向 ('up' 或 'down')。
        :return: (True, 消息) 如果移动成功，否则 (False, 错误消息)。
        """
        if not (0 <= index < len(self.playlist)):
            logger.warning(f"移动媒体失败: 无效的媒体索引 {index}。")
            return False, "无效的媒体索引。"

        new_index = index
        if direction == 'up':
            new_index = index - 1
        elif direction == 'down':
            new_index = index + 1
        else:
            logger.warning(f"移动媒体失败: 无效的移动方向 '{direction}'。")
            return False, "无效的移动方向。"

        if not (0 <= new_index < len(self.playlist)):
            return False, "无法移动到指定位置。"

        # 交换两个元素的位置
        self.playlist[index], self.playlist[new_index] = self.playlist[new_index], self.playlist[index]

        # 如果当前播放的歌曲被移动了，更新其索引
        if self.current_index == index:
            self.current_index = new_index
        elif self.current_index == new_index:
            self.current_index = index
        
        logger.info(f"已移动 '{os.path.basename(self.playlist[new_index]['main_path'])}' 从 {index} 到 {new_index}。")
        return True, f"已移动 '{os.path.basename(self.playlist[new_index]['main_path'])}'。"

    def move_media_to_position(self, source_index, target_index):
        """
        将播放列表中的媒体项从一个位置移动到另一个位置（拖放排序用）。
        :param source_index: 源索引。
        :param target_index: 目标索引。
        :return: (True, 消息) 如果移动成功，否则 (False, 错误消息)。
        """
        if not (0 <= source_index < len(self.playlist)) or \
           not (0 <= target_index < len(self.playlist)):
            logger.warning(f"移动媒体失败: 无效的源索引 {source_index} 或目标索引 {target_index}。")
            return False, "无效的索引。"
        
        # 弹出源位置的元素，然后插入到目标位置
        item = self.playlist.pop(source_index)
        self.playlist.insert(target_index, item)

        # 更新当前播放歌曲的索引
        if self.current_index == source_index:
            self.current_index = target_index
        elif source_index < self.current_index < target_index:
            self.current_index -= 1
        elif target_index <= self.current_index < source_index:
            self.current_index += 1
        
        logger.info(f"已拖放移动 '{os.path.basename(item['main_path'])}' 从 {source_index} 到 {target_index}。")
        return True, f"已拖放移动 '{os.path.basename(item['main_path'])}'。"

    def play(self, index=None):
        """
        播放指定索引或当前索引的媒体。
        包含 VLC 播放器初始化检查、文件存在性检查和播放状态判断。
        """
        if not self.instance or not self.player:
            logger.error("VLC 播放器未初始化或初始化失败。无法播放。")
            return False, "VLC 播放器未初始化或初始化失败。"

        if not self.playlist:
            logger.warning("播放列表为空。无法播放。")
            return False, "播放列表为空。请先添加媒体文件。"
        
        # 如果提供了索引，则设置当前播放索引
        if index is not None:
            if 0 <= index < len(self.playlist):
                self.current_index = index
            else:
                logger.warning(f"无效的文件索引: {index}。")
                return False, f"无效的文件索引: {index+1}。"
        elif self.current_index == -1: 
            # 如果没有指定索引，且当前没有歌曲被选中，则默认播放第一首
            self.current_index = 0

        # 获取即将播放的媒体信息
        media_item_to_play = self.playlist[self.current_index]
        media_path = media_item_to_play['main_path']
        media_type = media_item_to_play['type']

        # 对于本地文件，检查文件是否存在
        if media_type != 'network_stream' and not os.path.exists(media_path):
            logger.error(f"播放失败：本地文件不存在或路径无效 - {media_path}")
            return False, f"播放失败：本地文件不存在或路径无效 - {os.path.basename(media_path)}"

        # 如果尝试播放同一首歌曲且播放器已在播放或暂停状态，则恢复播放
        if media_item_to_play == self.current_media_item and (self.player.is_playing() or self.player.get_state() == vlc.State.Paused):
            if self.player.get_state() == vlc.State.Paused:
                self.player.play()
                logger.info(f"恢复播放: {os.path.basename(media_path)}")
                return True, f"恢复播放: {os.path.basename(media_path)}"
            else:
                logger.info(f"文件 '{os.path.basename(media_path)}' 已经在播放中。")
                return False, f"文件 '{os.path.basename(media_path)}' 已经在播放中。"
        
        try:
            logger.info(f"尝试加载媒体: {media_path} (类型: {media_type})")
            if media_type == 'network_stream':
                media = self.instance.media_new_location(media_path)
            else:
                media = self.instance.media_new_path(media_path)
            
            # 检查媒体对象是否成功创建
            if media is None:
                logger.error(f"VLC 无法创建媒体对象，可能路径有问题或文件损坏: {media_path}")
                return False, f"VLC 无法创建媒体对象，请检查文件: {os.path.basename(media_path)}"

            self.player.set_media(media) # 将媒体对象设置到播放器
            self.current_media_item = media_item_to_play # 更新当前播放的媒体项
            
            logger.info(f"开始播放媒体: {os.path.basename(media_path)}")
            play_result = self.player.play() # 调用 VLC 的播放方法，返回 0 表示成功，-1 表示失败
            
            if play_result == -1:
                logger.error(f"VLC play() 方法返回失败 (-1)，播放未启动: {os.path.basename(media_path)}")
                return False, f"VLC 播放器无法启动播放: {os.path.basename(media_path)}"

            self.player.audio_set_volume(int(self.volume * 100)) # 应用音量设置
            self.player.set_rate(self.playback_rate)             # 应用播放速度设置

            # 设置字幕 (如果存在且是视频文件)
            self.player.video_set_subtitle_file(None) # 播放新媒体时先清除旧字幕
            if self.current_media_item['type'] == 'video' and \
               self.current_media_item['subtitle_path'] and \
               os.path.exists(self.current_media_item['subtitle_path']):
                self.player.video_set_subtitle_file(self.current_media_item['subtitle_path'])
                logger.info(f"已加载字幕文件: {os.path.basename(self.current_media_item['subtitle_path'])}")
                
            # 添加到播放历史
            # self.playlist_manager.add_to_history(self.current_media_item) # 直接使用 PlaylistManager 实例
            self.add_to_history(self.current_media_item) # 现在由 PlayerLogic 代理调用，因为 PlayManager 是私有的
            logger.info(f"已将 '{os.path.basename(self.current_media_item['main_path'])}' 添加到历史记录。")

            # 给予 VLC 一点时间来启动并检查其真实状态
            time.sleep(0.2) 
            current_state = self.player.get_state()
            current_time_after_play = self.player.get_time()
            logger.info(f"VLC 播放后状态: {current_state}. 当前时间: {current_time_after_play} ms.")
            
            if current_state == vlc.State.Error:
                logger.error(f"VLC 播放器进入错误状态: {os.path.basename(media_path)}")
                return False, f"VLC 播放器遇到错误: {os.path.basename(media_path)}"
            if current_state == vlc.State.Ended:
                 logger.warning(f"VLC 播放器状态为结束，可能无法播放或文件极短。请检查文件是否可用: {os.path.basename(media_path)}")
            
            return True, f"正在播放: {os.path.basename(self.current_media_item['main_path'])}"
        except Exception as e:
            self.current_media_item = None 
            logger.critical(f"播放文件时发生严重错误 '{os.path.basename(media_path)}': {e}", exc_info=True)
            return False, f"播放文件时发生严重错误 '{os.path.basename(media_path)}': {e}"

    def pause(self):
        """暂停当前播放的媒体。"""
        # 只有当播放器处于播放或缓冲状态时才能暂停
        if not self.player or not (self.player.is_playing() or self.player.get_state() == vlc.State.Buffering): 
            return False, "没有媒体正在播放，无法暂停。"
        self.player.pause()
        logger.info("媒体已暂停。")
        return True, "媒体已暂停。"

    def unpause(self):
        """恢复当前暂停的媒体。"""
        # 只有当播放器处于暂停状态时才能恢复
        if not self.player or self.player.get_state() != vlc.State.Paused:
            return False, "没有暂停中的媒体可以恢复。"
        self.player.play()
        logger.info("媒体已恢复播放。")
        return True, "媒体已恢复播放。"

    def stop(self):
        """停止当前播放的媒体。"""
        if not self.player:
            return False, "播放器未初始化。"
            
        # 只有当播放器处于播放、暂停、缓冲或打开状态时才需要停止
        if self.player.get_state() in (vlc.State.Playing, vlc.State.Paused, vlc.State.Buffering, vlc.State.Opening):
            self.player.stop() 
            self.player.video_set_subtitle_file(None) # 停止时清除所有加载的字幕
            
            if self.current_media_item is not None or self.current_index != -1:
                logger.info("媒体已停止。")
                return True, "媒体已停止。"
            else:
                logger.info("没有媒体正在播放或暂停中，无需停止。")
                return False, "没有媒体正在播放或暂停中，无需停止。"
        else:
            logger.info("播放器当前不在播放/暂停/缓冲状态，无需停止。")
            return False, "播放器当前不在播放/暂停/缓冲状态，无需停止。"

    def set_volume(self, volume):
        """
        设置播放器音量。
        :param volume: 音量值 (0.0 - 1.0)。
        :return: (True, 消息) 如果设置成功，否则 (False, 错误消息)。
        """
        if not self.player:
            return False, "播放器未初始化。"

        if 0.0 <= volume <= 1.0:
            self.volume = volume
            self.player.audio_set_volume(int(volume * 100)) # VLC 音量范围是 0-100
            logger.debug(f"音量设置为: {int(volume * 100)}%")
            return True, f"音量设置为: {int(volume * 100)}%"
        else:
            logger.warning(f"设置音量失败: 音量必须在 0.0 到 1.0 之间 (当前: {volume})。")
            return False, "音量必须在 0.0 到 1.0 之间。"

    def set_playback_rate(self, rate):
        """
        设置播放速度。
        :param rate: 播放速度倍率 (例如 0.5, 1.0, 2.0)。VLC 通常支持 0.25x 到 4.0x。
        :return: (True, 消息) 如果设置成功，否则 (False, 错误消息)。
        """
        if not self.player:
            return False, "播放器未初始化。"
        
        if 0.1 <= rate <= 4.0: # 限制合理范围
            self.playback_rate = rate
            self.player.set_rate(rate)
            logger.info(f"播放速度设置为: {rate:.2f}x")
            return True, f"播放速度设置为: {rate:.2f}x"
        else:
            logger.warning(f"设置播放速度失败: 速度必须在 0.1 到 4.0 之间 (当前: {rate})。")
            return False, "播放速度必须在 0.1 到 4.0 之间。"

    def next_media(self):
        """根据当前播放模式（顺序、循环、随机）切换到下一首媒体。"""
        if not self.playlist:
            self.stop() 
            logger.info("播放列表为空，无法播放下一首。")
            return False, "播放列表为空。"
        
        # 处理播放列表为空或当前索引无效的情况
        if self.current_index == -1 or not (0 <= self.current_index < len(self.playlist)):
            if self.playback_mode == PlaybackMode.SHUFFLE and len(self.playlist) > 0:
                self.current_index = random.choice(range(len(self.playlist)))
            elif len(self.playlist) > 0:
                self.current_index = 0
            else:
                self.stop()
                logger.info("播放列表为空，无法播放下一首。")
                return False, "播放列表为空，无法播放下一首。"

        if self.playback_mode == PlaybackMode.LOOP_ONE:
            # 单曲循环：继续播放当前歌曲
            return self.play(self.current_index)
        
        if self.playback_mode == PlaybackMode.SHUFFLE:
            # 随机播放：从列表中随机选择一首 (如果列表大于1，尽量避免重复播放同一首)
            if len(self.playlist) > 1:
                # 获取所有可能的索引
                possible_indices = list(range(len(self.playlist)))
                # 如果当前歌曲在列表中，将其从可能选项中移除，避免立即重复
                if self.current_index in possible_indices:
                    possible_indices.remove(self.current_index)
                
                # 如果只剩一首（或移除当前后只剩零首），则只能选择当前歌曲（或回到第一首）
                new_index = random.choice(possible_indices if possible_indices else [self.current_index if len(self.playlist) > 0 else 0])
            else: 
                new_index = 0 if self.playlist else -1 # 如果只有一个或没有歌曲

            if new_index == -1: 
                self.stop()
                logger.info("播放列表已结束或无法找到下一首随机歌曲。")
                return False, "播放列表已结束或无法找到下一首随机歌曲。"

            self.current_index = new_index
        else: 
            # 顺序播放或列表循环：简单地移动到下一个索引
            old_index = self.current_index
            self.current_index = (self.current_index + 1) % len(self.playlist)
            # 如果是顺序播放，并且已经到达列表末尾并回到了开头，则停止播放
            if self.playback_mode == PlaybackMode.SEQUENTIAL and self.current_index == 0 and old_index == len(self.playlist) - 1:
                self.stop()
                logger.info("顺序播放模式下，播放列表已结束。")
                return False, "播放列表已结束。"
        
        return self.play()

    def prev_media(self):
        """根据当前播放模式（顺序、循环、随机）切换到上一首媒体。"""
        if not self.playlist:
            self.stop()
            logger.info("播放列表为空，无法播放上一首。")
            return False, "播放列表为空。"

        # 处理播放列表为空或当前索引无效的情况
        if self.current_index == -1 or not (0 <= self.current_index < len(self.playlist)): 
            if self.playback_mode == PlaybackMode.SHUFFLE and len(self.playlist) > 0:
                self.current_index = random.choice(range(len(self.playlist)))
            elif len(self.playlist) > 0:
                self.current_index = len(self.playlist) - 1 # 默认到最后一首
            else:
                self.stop()
                logger.info("播放列表为空，无法播放上一首。")
                return False, "播放列表为空，无法播放上一首。"

        if self.playback_mode == PlaybackMode.LOOP_ONE:
            # 单曲循环：继续播放当前歌曲
            return self.play(self.current_index)

        if self.playback_mode == PlaybackMode.SHUFFLE:
            # 随机播放：从列表中随机选择一首 (如果列表大于1，尽量避免重复播放同一首)
            if len(self.playlist) > 1:
                possible_indices = list(range(len(self.playlist)))
                if self.current_index in possible_indices:
                    possible_indices.remove(self.current_index)
                
                new_index = random.choice(possible_indices if possible_indices else [self.current_index if len(self.playlist) > 0 else 0])
            else:
                new_index = 0 if self.playlist else -1
            
            if new_index == -1:
                self.stop()
                logger.info("播放列表已结束或无法找到上一首随机歌曲。")
                return False, "播放列表已结束或无法找到上一首随机歌曲。"

            self.current_index = new_index
        else: 
            # 顺序播放或列表循环：简单地移动到上一个索引
            self.current_index = (self.current_index - 1 + len(self.playlist)) % len(self.playlist)
        
        return self.play()

    def get_current_media_info(self):
        """
        获取当前播放媒体的详细信息，包括文件名、状态、时间、标题、艺术家、专辑等。
        所有信息都被格式化为字符串或标准类型，供 GUI 直接使用。
        此方法封装了 VLC 播放器状态的细节。
        """
        file_name = "无"
        current_time = "00:00"
        total_time = "00:00"
        current_ms = 0
        total_ms = 0
        status = "停止"
        title = "N/A"
        artist = "N/A"
        album = "N/A"
        
        if self.player and self.current_media_item:
            file_name = os.path.basename(self.current_media_item['main_path'])
            title = self.current_media_item.get('title', file_name)
            artist = self.current_media_item.get('artist', '未知艺术家')
            album = self.current_media_item.get('album', '未知专辑')

            # 获取 VLC 播放器状态枚举值并转换为用户友好的字符串
            state = self.player.get_state()
            if state == vlc.State.Playing: status = "播放中"
            elif state == vlc.State.Paused: status = "暂停"
            elif state == vlc.State.Stopped: status = "停止"
            elif state == vlc.State.Ended: status = "已结束"
            elif state == vlc.State.Opening or state == vlc.State.Buffering: status = "加载中..."
            elif state == vlc.State.NothingSpecial: status = "就绪"
            elif state == vlc.State.Error: status = "错误" # 明确处理错误状态
            else: status = "未知" # 任何未知的 VLC 状态

            current_ms = self.player.get_time()   # 获取当前播放时间 (毫秒)
            total_ms = self.player.get_length()   # 获取媒体总长度 (毫秒)

            # 格式化当前时间和总时间为 MM:SS 格式
            if current_ms != -1: # 如果时间有效 (VLC 返回 -1 表示无效)
                current_sec = current_ms / 1000
                current_min = int(current_sec // 60)
                current_sec_rem = int(current_sec % 60)
                current_time = f"{current_min:02d}:{current_sec_rem:02d}"

            if total_ms > 0: # 如果总长度大于 0 (即媒体有长度)
                total_sec = total_ms / 1000
                total_min = int(total_sec // 60)
                total_sec_rem = int(total_sec % 60)
                total_time = f"{total_min:02d}:{total_sec_rem:02d}"
        else:
            # 如果播放器未初始化或当前没有媒体，则返回默认状态
            status = "就绪" if self.instance else "错误" # 根据 VLC 实例是否存在提供更具体状态

        # 返回所有信息，供 GUI 消费
        return file_name, status, current_time, total_time, current_ms, total_ms, title, artist, album

    def load_lyrics_content(self, lyrics_path):
        """
        从 LRC 或 TXT 文件加载歌词内容。
        解析歌词文件中的时间戳，并返回歌词数据列表。
        :param lyrics_path: 歌词文件的完整路径。
        :return: 包含 (时间戳_ms, 歌词文本) 元组的列表。
                 没有时间戳的行时间戳为 -1。
        """
        lyrics_data = []
        if lyrics_path and os.path.exists(lyrics_path):
            try:
                with open(lyrics_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        # 尝试匹配带毫秒的 LRC 格式: [MM:SS.ms]
                        match = re.match(r'\[(\d{2}):(\d{2})\.(\d{2,3})\](.*)', line)
                        if match:
                            minutes = int(match.group(1))
                            seconds = int(match.group(2))
                            milliseconds_str = match.group(3)
                            milliseconds = int(milliseconds_str)
                            
                            # 如果毫秒是两位数，通常表示分母是 100 (例如 .50 代表 500ms)，需要乘以 10 转换为 3 位毫秒
                            if len(milliseconds_str) == 2:
                                milliseconds *= 10 
                            
                            # 计算总毫秒时间戳
                            timestamp_ms = (minutes * 60 + seconds) * 1000 + milliseconds
                            lyric_text = match.group(4).strip()
                            lyrics_data.append((timestamp_ms, lyric_text))
                        else:
                            # 尝试匹配不带毫秒的 LRC 格式: [MM:SS]
                            match_no_ms = re.match(r'\[(\d{2}):(\d{2})\](.*)', line)
                            if match_no_ms:
                                minutes = int(match_no_ms.group(1))
                                seconds = int(match_no_ms.group(2))
                                timestamp_ms = (minutes * 60 + seconds) * 1000
                                lyric_text = match_no_ms.group(3).strip()
                                lyrics_data.append((timestamp_ms, lyric_text))
                            else:
                                # 对于无法解析时间戳的行，将其作为普通文本处理，时间戳设为 -1
                                lyrics_data.append((-1, line.strip())) 
                
                # 过滤掉空歌词文本的行，并按时间戳排序 (无时间戳的排在最后)
                lyrics_data = [item for item in lyrics_data if item[1]] 
                lyrics_data.sort(key=lambda x: x[0] if x[0] != -1 else float('inf')) 
                logger.info(f"已加载歌词文件 '{os.path.basename(lyrics_path)}'，共 {len(lyrics_data)} 行。")
                return lyrics_data
            except FileNotFoundError:
                logger.warning(f"歌词文件 '{lyrics_path}' 未找到。")
            except IOError as e:
                logger.error(f"读取歌词文件 '{lyrics_path}' 失败: {e}")
            except Exception as e:
                logger.error(f"加载歌词文件 '{lyrics_path}' 时发生未知错误: {e}", exc_info=True)
        return []

    def get_current_lyric_line_index(self, current_time_ms, lyrics_data):
        """
        根据当前播放时间 (毫秒) 和歌词数据，查找当前应该高亮的歌词行索引。
        使用二分查找算法提高效率。
        :param current_time_ms: 当前播放时间 (毫秒)。
        :param lyrics_data: 歌词数据列表，包含 (时间戳_ms, 歌词文本) 元组。
        :return: 当前应该高亮的歌词行索引，如果没有找到则返回 -1。
        """
        if not lyrics_data:
            return -1 
        
        low = 0
        high = len(lyrics_data) - 1
        current_line_index = -1

        while low <= high:
            mid = (low + high) // 2
            timestamp, _ = lyrics_data[mid]

            # 处理没有时间戳的歌词行：如果它在带时间戳的歌词后面，则可以跳过或特殊处理
            if timestamp == -1: 
                # 如果是最后一行或者下一行有时间戳，则向后查找
                if mid < len(lyrics_data) - 1 and lyrics_data[mid+1][0] != -1:
                    low = mid + 1 
                else:
                    # 否则，向前查找 (或者直接跳过不处理，因为它没有时间同步点)
                    high = mid - 1
                continue

            if timestamp <= current_time_ms:
                # 当前行的时间戳小于或等于当前播放时间，可能是当前行或之前的行
                current_line_index = mid
                low = mid + 1 # 继续向后查找，看是否有更接近当前时间的行
            else:
                # 当前行的时间戳大于当前播放时间，说明目标行在当前行之前
                high = mid - 1 

        return current_line_index

    # 直接代理 PlaylistManager 的 add_to_history 方法
    # 这样 MediaPlayerLogic 仍然是外部调用的主要接口
    def add_to_history(self, media_item):
        """将媒体项添加到播放历史（代理给 PlaylistManager）。"""
        # 注意：此处假设在 MediaPlayerLogic 外部，PlaylistManager 实例被创建
        # 且其 self.history 列表被赋值给了 MediaPlayerLogic.history
        # 实际上在 main_window.py 中，我们已经做了这个赋值：
        # self.player.playlist = self.playlist_manager.playlist
        # self.player.history = self.playlist_manager.history
        # 所以这里直接操作 self.history 列表即可，然后由 PlaylistManager 负责保存
        if self.history and self.history[-1]['main_path'] == media_item['main_path']:
            return
        
        self.history.append(media_item)
        if len(self.history) > 100: 
            self.history = self.history[-100:]
        # 保存历史记录将由 PlaylistManager 负责，此处不直接调用 save_history_to_file()
        # 而是依赖在 main_window 的 on_closing 中调用 playlist_manager.save_history_to_file()
        logger.debug(f"媒体 '{os.path.basename(media_item['main_path'])}' 已添加到内存中的历史记录。")


    def quit(self):
        """
        在程序退出前保存所有数据并释放 VLC 资源。
        此方法由 GUI 调用，作为应用关闭的最终清理。
        """
        # 保存播放列表和历史记录。
        # 此处不再由 MediaPlayerLogic 直接执行保存，而是由 GUI 在退出时调用 PlaylistManager 来保存。
        # 但为了日志的完整性，可以记录消息。
        logger.info("准备保存播放列表和历史记录...")

        # 释放 VLC 播放器和实例资源。
        if self.player:
            if self.event_manager:
                # 分离事件，防止在 VLC 释放后回调仍然触发
                self.event_manager.event_detach(vlc.EventType.MediaPlayerEndReached)
                logger.info("VLC 事件已分离。")
            self.player.stop()      # 停止播放
            self.player.release()   # 释放播放器资源
            logger.info("VLC 播放器已释放。")
        if self.instance:
            self.instance.release() # 释放 VLC 实例资源
            logger.info("VLC 实例已释放。")
        logger.info("媒体播放器逻辑已关闭。")