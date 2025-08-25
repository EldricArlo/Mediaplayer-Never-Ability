# media_player_project/utils/logger_config.py

import logging
import sys
import os

# --- 日志配置 ---
def setup_logging():
    """
    配置应用程序的日志系统。
    - 日志输出到文件 (media_player.log) 和控制台 (stdout)。
    - 为不同模块和输出目标设置不同的日志级别，以控制日志的详细程度。
    """
    # 获取或创建名为 'MediaPlayer' 的根日志器。
    # 这是一个层级结构的顶层日志器，其他模块的日志器将是它的子日志器。
    logger = logging.getLogger('MediaPlayer')
    logger.setLevel(logging.INFO) # 默认所有信息都记录到日志 (INFO 及以上)

    # 确保不重复添加处理器。
    # 这在应用多次启动或模块被多次导入时非常重要，避免日志重复输出。
    if not logger.handlers:
        # 创建一个文件处理器，用于将日志写入文件。
        # 日志文件路径定义在 constants.py 中，这里确保 'data' 目录存在。
        log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "media_player.log")
        os.makedirs(os.path.dirname(log_file_path), exist_ok=True) # 确保目录存在
        
        file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
        file_handler.setLevel(logging.INFO) # 文件中记录 INFO 及以上级别日志

        # 创建一个控制台处理器，用于将日志输出到标准输出 (终端)。
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.WARNING) # 控制台只显示 WARNING 及以上级别日志，避免刷屏

        # 定义日志的输出格式。
        # %(asctime)s: 日志时间
        # %(name)s: 日志器名称 (例如 MediaPlayer.Core.PlayerLogic)
        # %(levelname)s: 日志级别 (如 INFO, WARNING, ERROR)
        # %(message)s: 日志内容
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # 将处理器添加到日志器。
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    # 降低特定第三方库的日志级别，避免它们输出过多不必要的调试信息。
    # 例如，vlc 库在 INFO 级别会有非常多的内部输出，会污染日志。
    logging.getLogger('vlc').setLevel(logging.WARNING) # VLC 库只记录 WARNING 及以上
    logging.getLogger('PIL').setLevel(logging.WARNING) # Pillow 库 (图片处理) 只记录 WARNING 及以上

    logger.info("Loggers initialized.")

# 提供一个方便的获取日志器实例的函数。
# 其他模块调用此函数来获取其专属的子日志器。
def get_logger(name):
    return logging.getLogger(name)

# 在模块导入时立即执行日志设置，确保日志系统在应用程序启动初期就被配置好。
setup_logging()