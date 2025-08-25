# media_player_project/main.py

import sys
import os
import logging

# --- IMPORTANT: Adjust sys.path for direct script execution ---
# 此段代码旨在解决 Python 的相对导入 (e.g., from .module import ...) 问题，
# 特别是当您直接运行包内部的某个文件 (e.g., python my_package/main.py) 而不是通过
# python -m my_package.main 启动时。
#
# 1. 获取当前脚本 (main.py) 所在的目录的绝对路径。
current_script_dir = os.path.dirname(os.path.abspath(__file__))
# 2. 获取项目根目录的绝对路径。
# 假设 'media_player_project' 文件夹就在 'current_script_dir' 的父目录。
# 例如，如果 main.py 在 D:/Project/Pygame/media_player_project/main.py
# 那么 current_script_dir 是 D:/Project/Pygame/media_player_project
# 它的父目录 (project_root_containing_package) 就是 D:/Project/Pygame
project_root_containing_package = os.path.dirname(current_script_dir)

# 3. 将项目根目录添加到 Python 的模块搜索路径 (sys.path) 的最前面。
# 这样做之后，Python 就能找到 'media_player_project' 这个包，
# 从而允许 'from media_player_project.gui.main_window import MediaPlayerGUI' 这样的绝对导入成功。
if project_root_containing_package not in sys.path:
    sys.path.insert(0, project_root_containing_package)
# --- End sys.path adjustment ---


# 导入日志配置模块。
# 导入此模块会执行其中的 setup_logging() 函数，从而配置好日志系统。
from media_player_project.utils import logger_config 

# 获取根日志器实例。此日志器已通过 logger_config 模块配置好。
logger = logging.getLogger('MediaPlayer')

# 导入主 GUI 应用程序类。
# 现在使用完整的包路径进行绝对导入，确保在任何运行环境下都能被正确找到。
from media_player_project.gui.main_window import MediaPlayerGUI


if __name__ == "__main__":
    logger.info("Application starting...")
    
    # 在应用程序启动时，确保 'data' 和 'assets' 目录存在。
    # 这些目录用于存放配置文件、播放列表、历史记录和静态资源（如 Logo）。
    # os.path.join() 用于构建跨操作系统的正确路径。
    # os.makedirs(..., exist_ok=True) 会在目录不存在时创建，如果存在则不进行任何操作。
    os.makedirs(os.path.join(current_script_dir, "data"), exist_ok=True)
    os.makedirs(os.path.join(current_script_dir, "assets"), exist_ok=True)

    # 实例化主 GUI 应用程序。这将触发 GUI 的初始化以及 VLC 播放逻辑的初始化。
    app = MediaPlayerGUI() 
    # 启动 Tkinter 的主事件循环。这会使 GUI 窗口保持打开状态，并响应用户交互。
    app.mainloop()
    # 当 mainloop 退出（例如用户关闭窗口）时，此行代码会执行。
    logger.info("Application exiting.")