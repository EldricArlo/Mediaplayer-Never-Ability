# media_player_project/core/playlist_manager.py

import os
import json
import logging

# 导入项目工具模块中的常量和日志器
from ..utils.constants import PLAYLIST_FILE, HISTORY_FILE
from ..utils.logger_config import get_logger

# 获取当前模块的 logger 实例
logger = get_logger('MediaPlayer.Core.PlaylistManager')

class PlaylistManager:
    """
    负责播放列表和播放历史的数据管理。
    包括从文件加载、保存到文件以及添加/删除/移动播放列表项。
    它不直接与 VLC 播放器交互，专注于数据持久化和结构操作。
    """
    def __init__(self):
        self.playlist_file = PLAYLIST_FILE 
        self.history_file = HISTORY_FILE 
        self.playlist = self._load_playlist_from_file() # 应用程序启动时加载播放列表
        self.history = self._load_history_from_file()   # 应用程序启动时加载播放历史
        logger.info("播放列表管理器初始化完成。")

    def _load_playlist_from_file(self):
        """
        从 JSON 文件加载播放列表。
        - 检查文件是否存在。
        - 验证加载的数据结构是否正确。
        - 过滤掉本地文件路径已不存在的项（保留网络流）。
        """
        if os.path.exists(self.playlist_file):
            try:
                with open(self.playlist_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 验证加载的数据是否是列表，且每个字典项都包含 'main_path' 键
                    if isinstance(data, list) and all(isinstance(item, dict) and 'main_path' in item for item in data):
                        # 过滤掉不存在的本地文件，但保留网络流
                        valid_playlist = [item for item in data if os.path.exists(item['main_path']) or item.get('type') == 'network_stream']
                        logger.info(f"已从 '{self.playlist_file}' 加载 {len(valid_playlist)} 个有效文件。")
                        return valid_playlist
                    else:
                        logger.warning(f"播放列表文件 '{self.playlist_file}' 格式不正确，将创建一个新列表。")
                        return []
            except json.JSONDecodeError:
                logger.error(f"播放列表文件 '{self.playlist_file}' 格式错误 (JSON 解码失败)。")
                return []
            except FileNotFoundError:
                logger.warning(f"播放列表文件 '{self.playlist_file}' 未找到。")
                return []
            except Exception as e:
                logger.error(f"加载播放列表时发生未知错误: {e}")
                return []
        return [] # 如果文件不存在，返回空列表

    def save_playlist_to_file(self):
        """将当前播放列表（in `self.playlist`）保存到 JSON 文件。"""
        # 确保数据目录存在，如果不存在则创建
        data_dir = os.path.dirname(self.playlist_file)
        os.makedirs(data_dir, exist_ok=True)

        try:
            with open(self.playlist_file, 'w', encoding='utf-8') as f:
                json.dump(self.playlist, f, ensure_ascii=False, indent=4) # 格式化保存
            logger.info(f"播放列表已保存到 '{self.playlist_file}'。")
        except IOError as e:
            logger.error(f"保存播放列表失败 (IO 错误): {e}")
        except Exception as e:
            logger.error(f"保存播放列表时发生未知错误: {e}")

    def _load_history_from_file(self):
        """
        从 JSON 文件加载播放历史。
        - 限制历史记录数量，默认只保留最新的 100 条。
        - 过滤掉本地文件路径已不存在的项（保留网络流）。
        """
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list) and all(isinstance(item, dict) and 'main_path' in item for item in data):
                        # 过滤掉不存在的本地文件，并限制历史记录最多 100 条
                        valid_history = [item for item in data if os.path.exists(item['main_path']) or item.get('type') == 'network_stream'][-100:] 
                        logger.info(f"已从 '{self.history_file}' 加载 {len(valid_history)} 条历史记录。")
                        return valid_history
                    else:
                        logger.warning(f"历史记录文件 '{self.history_file}' 格式不正确，将创建一个新列表。")
                        return []
            except json.JSONDecodeError as e:
                logger.error(f"加载历史记录文件失败 (JSON 格式错误): {e}，将创建一个新列表。")
                return []
            except FileNotFoundError:
                logger.info(f"历史记录文件 '{self.history_file}' 未找到，将创建一个新列表。")
                return []
            except Exception as e:
                logger.error(f"加载历史记录文件时发生未知错误: {e}，将创建一个新列表。")
                return []
        return [] # 如果文件不存在，返回空列表

    def save_history_to_file(self):
        """将当前播放历史（in `self.history`）保存到 JSON 文件。"""
        # 确保数据目录存在
        data_dir = os.path.dirname(self.history_file)
        os.makedirs(data_dir, exist_ok=True)

        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=4)
            logger.info(f"历史记录已保存到 '{self.history_file}'。")
        except IOError as e:
            logger.error(f"保存历史记录失败 (IO 错误): {e}")
        except Exception as e:
            logger.error(f"保存历史记录时发生未知错误: {e}")

    def add_to_history(self, media_item):
        """
        将媒体项添加到播放历史列表（in `self.history`）。
        - 避免添加与历史记录中最后一项重复的项。
        - 限制历史记录列表的最大长度。
        :param media_item: 要添加到历史记录的媒体项字典。
        """
        # 检查是否与历史记录中的最后一项相同，避免重复添加
        if self.history and self.history[-1]['main_path'] == media_item['main_path']:
            logger.debug(f"媒体 '{os.path.basename(media_item['main_path'])}' 已在历史记录末尾，跳过添加。")
            return
        
        self.history.append(media_item)
        # 限制历史记录的最大数量，只保留最新的 100 条
        if len(self.history) > 100: 
            self.history = self.history[-100:]
        self.save_history_to_file() # 每次添加后保存，确保数据新鲜度
        logger.info(f"已将 '{os.path.basename(media_item['main_path'])}' 添加到历史记录。")