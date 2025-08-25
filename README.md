# mediaPlayer-never-ability
A filed media player, I don't konw why this player can't paly. And the player pelying on vlc component.

** --- 一个失败得媒体播放器 --- **

# 代码架构

```
media_player_project/
├── main.py                          # 主入口点，负责应用启动和根窗口初始化
├── core/                            # 核心逻辑目录
│   ├── __init__.py                  # 包初始化文件 (空)
│   ├── player_logic.py              # VLC 媒体播放核心操作
│   ├── playlist_manager.py          # 播放列表和历史记录的加载、保存和管理
│   ├── media_info.py                # 媒体文件信息（标签、关联文件）的读取
│   └── equalizer_control.py         # VLC 均衡器控制封装
├── gui/                             # 用户界面目录
│   ├── __init__.py                  # 包初始化文件 (空)
│   ├── main_window.py               # 主应用程序窗口和布局
│   ├── control_panel.py             # 播放控制按钮和进度条
│   ├── display_area.py              # 视频/封面/歌词显示区域
│   ├── playlist_view.py             # 播放列表和历史列表显示
│   ├── associated_files_panel.py    # 关联文件操作按钮
│   └── equalizer_window.py          # 均衡器设置窗口
├── utils/                           # 工具函数和配置
│   ├── __init__.py                  # 包初始化文件 (空)
│   ├── constants.py                 # 常量定义（文件路径、枚举）
│   ├── logger_config.py             # 日志系统配置
│   └── vlc_path_manager.py          # VLC 路径的存储、加载和验证
├── assets/                          # 静态资源
│   └── player_logo.png              # 播放器 Logo (可选)
└── data/                            # 运行时数据
    ├── vlc_config.json              # VLC 路径配置 (应用生成)
    ├── playlist.json                # 播放列表数据 (应用生成)
    └── history.json                 # 播放历史数据 (应用生成)
```

# 注意事项

需要安装vlc组件，否则运行的时候会报错

# 运行代码

直接运行main.py文件即可，虽然会出现一个非常简陋的ui界面，但是没有任何的办法播放音频，修改了很多次都没办法。
希望未来学习得深之后可以解决这个“历史遗留问题”...

# 许可证明

本项采用[MIT license](LICENSE.md)授权
