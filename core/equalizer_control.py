# media_player_project/core/equalizer_control.py

import vlc
import logging

# 导入项目工具模块中的日志器
from ..utils.logger_config import get_logger

# 获取当前模块的 logger 实例
logger = get_logger('MediaPlayer.Core.EqualizerControl')

class EqualizerControl:
    """
    VLC 均衡器控制类。
    封装了 VLC AudioEqualizer 对象的设置和信息获取，
    使其易于在 UI 中集成和操作，而无需直接暴露 VLC 库的复杂性。
    """
    def __init__(self, player_instance, media_player):
        """
        初始化均衡器控制器。
        :param player_instance: VLC 实例 (vlc.Instance)。
        :param media_player: VLC 媒体播放器 (vlc.MediaPlayer)。
        """
        self.instance = player_instance
        self.player = media_player
        self.equalizer = None
        self._setup_vlc_equalizer()
        logger.info("均衡器控制器初始化完成。")

    def _setup_vlc_equalizer(self):
        """
        初始化 VLC 均衡器并将其应用到播放器。
        确保在均衡器对象创建后立即设置到播放器。
        """
        if self.instance and self.player:
            try:
                # 创建一个 VLC AudioEqualizer 对象
                self.equalizer = vlc.AudioEqualizer()
                # 将均衡器应用到媒体播放器
                self.player.set_equalizer(self.equalizer)
                logger.info("VLC 均衡器已成功设置到播放器。")
            except Exception as e:
                logger.error(f"设置 VLC 均衡器失败: {e}")

    def set_equalizer_gain(self, band_index, gain):
        """
        设置指定均衡器频段的增益。
        :param band_index: 均衡器频段的索引 (通常为 0-9)。
        :param gain: 要设置的增益值 (浮点数，单位 dB，通常范围 -20.0 到 20.0)。
        :return: (True, 消息) 如果设置成功，否则 (False, 错误消息)。
        """
        if self.equalizer:
            try:
                # 设置指定频段的增益
                self.equalizer.set_amp_at_index(gain, band_index)
                logger.debug(f"均衡器频段 {band_index} 增益设置为 {gain:.1f} dB。")
                return True, "均衡器增益已设置。"
            except Exception as e:
                logger.error(f"设置均衡器频段 {band_index} 增益失败: {e}")
                return False, f"设置均衡器增益失败: {e}"
        return False, "均衡器未初始化。"

    def set_equalizer_preamp(self, preamp_gain):
        """
        设置均衡器的前置放大增益。
        前置放大器会整体调整所有频段的音量。
        :param preamp_gain: 前置放大增益值 (浮点数，单位 dB，通常范围 -20.0 到 20.0)。
        :return: (True, 消息) 如果设置成功，否则 (False, 错误消息)。
        """
        if self.equalizer:
            try:
                self.equalizer.set_preamp(preamp_gain)
                logger.debug(f"均衡器前置放大设置为 {preamp_gain:.1f} dB。")
                return True, "均衡器前置放大已设置。"
            except Exception as e:
                logger.error(f"设置均衡器前置放大失败: {e}")
                return False, f"设置均衡器前置放大失败: {e}"
        return False, "均衡器未初始化。"

    def get_equalizer_bands_info(self):
        """
        获取均衡器所有频段的当前信息，包括频率和增益。
        将 VLC 均衡器 API 的底层细节封装在此方法中，供 GUI 调用。
        :return: 包含 'preamp' (前置放大增益) 和 'bands' (频段信息列表) 的字典。
                 每个频段信息是包含 'index', 'frequency', 'gain' 的字典。
                 如果均衡器未初始化或获取信息失败，返回默认值。
        """
        bands_info = []
        preamp_gain = 0.0
        if self.equalizer:
            try:
                # VLC 均衡器通常有固定的 10 个频段 (索引 0 到 9)
                band_count = 10 
                
                # 常见的 VLC 均衡器默认频率，作为兼容性回退选项
                common_vlc_frequencies = [
                    60, 120, 250, 500, 1000, 2000, 4000, 8000, 11000, 16000
                ]

                for i in range(band_count):
                    freq = None
                    try:
                        # 尝试通过 equalizer 实例获取频率。这是 vlc.py 库的现代 API 方式。
                        # 对于某些老版本 vlc.py，可能没有这个方法，需要回退。
                        freq = self.equalizer.get_frequency_at_index(i) 
                    except AttributeError:
                        # 如果 get_frequency_at_index 不存在，则使用预定义的常见频率。
                        if i < len(common_vlc_frequencies):
                            freq = common_vlc_frequencies[i]
                        else:
                            freq = f"Band {i} (Freq N/A)" # 如果超过预设范围，提供通用名称
                        logger.warning(f"vlc.AudioEqualizer.get_frequency_at_index({i}) 不可用，使用预设频率。")
                    except Exception as e:
                        # 捕获其他获取频率的异常
                        freq = f"Band {i} (Error)"
                        logger.error(f"获取均衡器频段 {i} 频率失败: {e}")

                    # 获取当前频段的增益值
                    gain = self.equalizer.get_amp_at_index(i)
                    bands_info.append({"index": i, "frequency": freq, "gain": gain})
                
                # 获取前置放大增益
                preamp_gain = self.equalizer.get_preamp()
                return {"preamp": preamp_gain, "bands": bands_info}
            except Exception as e:
                logger.error(f"获取均衡器频段信息失败: {e}", exc_info=True)
        # 如果均衡器未初始化或获取信息过程中发生错误，返回默认的空信息
        return {"preamp": 0.0, "bands": []}