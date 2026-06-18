from __future__ import annotations

from dataclasses import dataclass


DESIGN_TYPE_PIXEL = '像素逐点成字'
DESIGN_TYPE_SEQUENTIAL_PIXEL = '逐字像素显现'
DESIGN_TYPE_STAR_GATHER = '随机星点聚合成字'
DESIGN_TYPE_SCANLINE = '扫描线生成文字'
DESIGN_TYPE_FLIPBOARD = '翻页切换字'
DESIGN_TYPE_DECODE = '乱码解码成字'
DESIGN_TYPE_GLITCH = '故障闪烁字'
DESIGN_TYPE_CENTER_BURST = '中心扩散成字'
DESIGN_TYPE_OUTLINE_SCAN = '边框扫描成字'
DESIGN_TYPE_SEQUENTIAL_OUTLINE = '逐字边框扫描'
DESIGN_TYPE_STROKE = '一笔一画'
DESIGN_TYPE_STAMP = '盖章弹出'
DESIGN_TYPE_RAINDROP = '雨滴下落成字'
DESIGN_TYPE_WAVE = '波浪浮现'
DESIGN_TYPE_STRETCH = '横向拉伸展开'
DESIGN_TYPE_BOX = '盒子打开成字'
DESIGN_TYPE_INVERSE = '反色闪现成字'
DESIGN_TYPE_MARQUEE = '走马灯文字'
DESIGN_TYPE_RECOGNITION = '混合灯效'


@dataclass(frozen=True)
class DesignTypeDefinition:
    key: str
    effect_name: str
    display_name: str
    design_aliases: tuple[str, ...] = ()
    effect_aliases: tuple[str, ...] = ()


DESIGN_TYPE_DEFINITIONS: tuple[DesignTypeDefinition, ...] = (
    DesignTypeDefinition(
        key='pixel_reveal_build',
        effect_name='pixel_reveal',
        display_name=DESIGN_TYPE_PIXEL,
        effect_aliases=('pixel_by_pixel_reveal',),
    ),
    DesignTypeDefinition(
        key='sequential_pixel_reveal_build',
        effect_name='sequential_pixel_reveal',
        display_name=DESIGN_TYPE_SEQUENTIAL_PIXEL,
        design_aliases=('逐字母像素显现',),
    ),
    DesignTypeDefinition(
        key='star_gather_build',
        effect_name='star_gather_reveal',
        display_name=DESIGN_TYPE_STAR_GATHER,
        effect_aliases=('star_point_gather',),
    ),
    DesignTypeDefinition(
        key='scanline_reveal_build',
        effect_name='scanline_reveal',
        display_name=DESIGN_TYPE_SCANLINE,
        design_aliases=('扫描线显字',),
    ),
    DesignTypeDefinition(
        key='flipboard_page_switch',
        effect_name='flipboard_reveal',
        display_name=DESIGN_TYPE_FLIPBOARD,
        design_aliases=('像素翻页字',),
        effect_aliases=('pixel_flipboard', 'flipboard_reveal_text'),
    ),
    DesignTypeDefinition(
        key='decode_reveal_build',
        effect_name='decode_reveal',
        display_name=DESIGN_TYPE_DECODE,
    ),
    DesignTypeDefinition(
        key='glitch_hold_motion',
        effect_name='glitch_hold',
        display_name=DESIGN_TYPE_GLITCH,
        effect_aliases=('glitch 故障字',),
    ),
    DesignTypeDefinition(
        key='center_burst_build',
        effect_name='center_burst_reveal',
        display_name=DESIGN_TYPE_CENTER_BURST,
    ),
    DesignTypeDefinition(
        key='outline_scan_build',
        effect_name='outline_scan_reveal',
        display_name=DESIGN_TYPE_OUTLINE_SCAN,
    ),
    DesignTypeDefinition(
        key='sequential_outline_scan_build',
        effect_name='sequential_outline_scan_reveal',
        display_name=DESIGN_TYPE_SEQUENTIAL_OUTLINE,
        design_aliases=('逐字母边框扫描',),
    ),
    DesignTypeDefinition(
        key='stroke_write_build',
        effect_name='stroke_write_reveal',
        display_name=DESIGN_TYPE_STROKE,
        design_aliases=('笔画书写',),
    ),
    DesignTypeDefinition(
        key='stamp_pop_build',
        effect_name='stamp_pop_reveal',
        display_name=DESIGN_TYPE_STAMP,
    ),
    DesignTypeDefinition(
        key='raindrop_build',
        effect_name='raindrop_reveal',
        display_name=DESIGN_TYPE_RAINDROP,
    ),
    DesignTypeDefinition(
        key='wave_reveal_build',
        effect_name='wave_reveal',
        display_name=DESIGN_TYPE_WAVE,
    ),
    DesignTypeDefinition(
        key='horizontal_stretch_build',
        effect_name='horizontal_stretch_reveal',
        display_name=DESIGN_TYPE_STRETCH,
    ),
    DesignTypeDefinition(
        key='box_open_build',
        effect_name='box_open_reveal',
        display_name=DESIGN_TYPE_BOX,
    ),
    DesignTypeDefinition(
        key='inverse_flash_build',
        effect_name='inverse_flash_reveal',
        display_name=DESIGN_TYPE_INVERSE,
    ),
    DesignTypeDefinition(
        key='marquee_scroll_build',
        effect_name='marquee_scroll_reveal',
        display_name=DESIGN_TYPE_MARQUEE,
        design_aliases=('走马灯', '跑马灯'),
    ),
    DesignTypeDefinition(
        key='recognition_handoff_sequence',
        effect_name='recognition_handoff_reveal',
        display_name=DESIGN_TYPE_RECOGNITION,
        effect_aliases=('recognition_handoff', 'recognition_sequence'),
    ),
)


__all__ = [
    'DESIGN_TYPE_BOX',
    'DESIGN_TYPE_CENTER_BURST',
    'DESIGN_TYPE_DECODE',
    'DESIGN_TYPE_DEFINITIONS',
    'DESIGN_TYPE_FLIPBOARD',
    'DESIGN_TYPE_GLITCH',
    'DESIGN_TYPE_INVERSE',
    'DESIGN_TYPE_MARQUEE',
    'DESIGN_TYPE_OUTLINE_SCAN',
    'DESIGN_TYPE_PIXEL',
    'DESIGN_TYPE_RAINDROP',
    'DESIGN_TYPE_RECOGNITION',
    'DESIGN_TYPE_SCANLINE',
    'DESIGN_TYPE_SEQUENTIAL_OUTLINE',
    'DESIGN_TYPE_SEQUENTIAL_PIXEL',
    'DESIGN_TYPE_STAMP',
    'DESIGN_TYPE_STAR_GATHER',
    'DESIGN_TYPE_STRETCH',
    'DESIGN_TYPE_STROKE',
    'DESIGN_TYPE_WAVE',
    'DesignTypeDefinition',
]
