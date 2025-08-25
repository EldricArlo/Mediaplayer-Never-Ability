# media_player_project/utils/vlc_path_manager.py

import os
import json
import sys
import logging

# 从常量文件中导入 VLC 配置文件的路径
from .constants import VLC_CONFIG_FILE

# 获取 logger 实例，用于记录 VLC 路径管理相关的日志
logger = logging.getLogger('MediaPlayer.Utils.VLCPathManager')

def load_vlc_path_from_config():
    """
    从配置文件加载之前保存的 VLC 安装路径。
    如果文件不存在、格式错误或路径无效，则返回 None。
    """
    # 确保配置文件所在的 'data' 目录存在，避免 FileNotFoundError
    data_dir = os.path.dirname(VLC_CONFIG_FILE)
    if not os.path.exists(data_dir):
        logger.info(f"数据目录 '{data_dir}' 不存在，无需加载 VLC 路径。")
        return None

    if os.path.exists(VLC_CONFIG_FILE):
        try:
            with open(VLC_CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                vlc_path = config.get("VLC_PATH")
                # 检查加载的路径是否为空且实际存在
                if vlc_path and os.path.exists(vlc_path):
                    logger.info(f"VLC 路径已从配置文件加载: {vlc_path}")
                    return vlc_path
        except json.JSONDecodeError:
            logger.error(f"VLC 配置 '{VLC_CONFIG_FILE}' 格式错误 (JSON 解码失败)。")
        except FileNotFoundError:
            # 理论上 os.path.exists 已经检查过，但这是一种预防性捕获
            logger.warning(f"VLC 配置 '{VLC_CONFIG_FILE}' 未找到。")
        except Exception as e:
            logger.error(f"加载 VLC 配置时发生未知错误: {e}")
    return None

def save_vlc_path_to_config(path):
    """
    将 VLC 安装路径保存到配置文件。
    在保存之前，会确保目标目录 (data 文件夹) 存在。
    """
    # 确保 'data' 目录存在，如果不存在则创建
    data_dir = os.path.dirname(VLC_CONFIG_FILE)
    os.makedirs(data_dir, exist_ok=True)
    
    try:
        with open(VLC_CONFIG_FILE, 'w', encoding='utf-8') as f:
            # 使用 json.dump 写入配置，ensure_ascii=False 允许写入非 ASCII 字符，indent=4 格式化输出
            json.dump({"VLC_PATH": path}, f, ensure_ascii=False, indent=4)
        logger.info(f"VLC 路径已保存到 '{VLC_CONFIG_FILE}'。")
    except Exception as e:
        logger.error(f"保存 VLC 路径失败: {e}")

def is_valid_vlc_path(path):
    """
    检查给定路径是否包含 VLC 核心库文件 (libvlc.dll/libvlc.dylib/libvlc.so)。
    此函数用于验证用户选择的 VLC 路径是否有效，确保 VLC 库可被加载。
    """
    if not os.path.isdir(path):
        logger.warning(f"VLC 路径 '{path}' 不是一个有效的目录。")
        return False
    
    # 根据当前操作系统检查对应的 VLC 核心库文件
    if sys.platform.startswith('win'):
        # Windows 系统：查找 'libvlc.dll'。它可能在 VLC 根目录或 'sdk/lib' 子目录。
        dll_path_root = os.path.join(path, 'libvlc.dll')
        dll_path_sdk = os.path.join(path, 'sdk', 'lib', 'libvlc.dll')
        if os.path.exists(dll_path_root) or os.path.exists(dll_path_sdk):
            logger.info(f"在 '{path}' 中找到 Windows VLC DLL。")
            return True
    elif sys.platform == 'darwin': # macOS
        # macOS 系统：查找 'libvlc.dylib'。它可能在应用程序包内 'Contents/MacOS/lib' 或直接在 'lib' 目录。
        dylib_path_app = os.path.join(path, 'Contents', 'MacOS', 'lib', 'libvlc.dylib')
        dylib_path_lib = os.path.join(path, 'lib', 'libvlc.dylib')
        if os.path.exists(dylib_path_app) or os.path.exists(dylib_path_lib):
            logger.info(f"在 '{path}' 中找到 macOS VLC dylib。")
            return True
    elif sys.platform.startswith('linux'):
        # Linux 系统：查找 'libvlc.so'。它可能在 VLC 根目录或 'lib' 子目录。
        so_path_root = os.path.join(path, 'libvlc.so')
        so_path_lib = os.path.join(path, 'lib', 'libvlc.so')
        if os.path.exists(so_path_root) or os.path.exists(so_path_lib):
            logger.info(f"在 '{path}' 中找到 Linux VLC so。")
            return True
    
    # 如果未能找到任何匹配的 VLC 核心库文件
    logger.warning(f"在 '{path}' 中未找到有效的 VLC 核心库文件。")
    return False