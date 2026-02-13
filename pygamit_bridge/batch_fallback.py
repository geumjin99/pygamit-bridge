"""
batch_fallback.py — Module 2b: makexp batch 文件回退生成器

当 GAMIT 的 makexp 无法正确处理 RINEX 头部时（即使经过 RINEX3→2 转换，
某些接收机类型或观测类型组合仍可能导致 makexp 不生成 batch 文件），
本模块提供回退机制，直接从 RINEX 头部信息生成 makex 所需的 batch 文件。

这使得 GAMIT 的 X-file 生成步骤能够正常完成。
"""

import os
import re
import glob

# 接收机类型 → GAMIT 3 字符缩写映射
RECEIVER_MAP = {
    'SEPT': 'SEP',
    'JAVAD': 'JAV',
    'TRIMBLE': 'TRM',
    'LEICA': 'LEI',
    'ASHTECH': 'ASH',
    'TOPCON': 'TOP',
    'NOVATEL': 'NOV',
    'TPS': 'TPS',
    'ROGUE': 'ROG',
}


def _get_receiver_abbrev(rec_type):
    """将完整接收机类型名映射为 GAMIT 使用的 3 字符缩写。

    Args:
        rec_type: 完整接收机类型字符串（如 'SEPT POLARX5'）

    Returns:
        3 字符缩写（如 'SEP'）
    """
    rec_upper = rec_type.upper()
    for key, abbrev in RECEIVER_MAP.items():
        if key in rec_upper:
            return abbrev
    return rec_type[:3].upper()


def _get_receiver_version(rec_version_str):
    """从固件版本字符串中提取数值版本号。

    Args:
        rec_version_str: 固件版本字符串（如 '5.4.0'）

    Returns:
        浮点版本号（如 5.4）
    """
    match = re.search(r'(\d+\.\d+)', rec_version_str)
    if match:
        return float(match.group(1))
    return 0.00


def _parse_rinex_header(filepath):
    """从 RINEX 文件头部提取站点和接收机信息。

    Args:
        filepath: RINEX 文件路径

    Returns:
        包含 station, rec_type, rec_version, ant_type 的字典
    """
    info = {
        'station': '',
        'rec_type': '',
        'rec_version': '',
        'ant_type': '',
    }

    with open(filepath, 'r', errors='replace') as f:
        for line in f:
            label = line[60:].strip() if len(line) > 60 else ''
            if label == 'MARKER NAME':
                info['station'] = line[0:4].strip().lower()
            elif label == 'REC # / TYPE / VERS':
                info['rec_type'] = line[20:40].strip()
                info['rec_version'] = line[40:60].strip()
            elif label == 'ANT # / TYPE':
                info['ant_type'] = line[20:40].strip()
            elif label == 'END OF HEADER':
                break

    return info


def generate_makex_batch(expt, year, doy, orbt='igsg',
                         nav_file=None, xver='5', rinex_dir='./'):
    """生成 GAMIT makex batch 文件内容。

    当 makexp 未能自动生成 batch 文件时，本函数作为回退机制，
    直接从工作目录中的 RINEX 文件头部读取站点和接收机信息。

    Args:
        expt: 实验名（4字符，如 'anta'）
        year: 4 位年份
        doy: 年积日字符串（3位补零，如 '001'）
        orbt: 轨道类型标识（默认 'igsg'）
        nav_file: 导航文件名（如 'brdc0010.25n'），None 则自动构造
        xver: X-file 版本号（默认 '5'）
        rinex_dir: RINEX 文件所在目录

    Returns:
        batch 文件内容字符串，失败返回 None
    """
    yr2 = str(year)[-2:]

    # 自动构造导航文件名
    if nav_file is None:
        nav_file = f"brdc{doy}0.{yr2}n"

    # 查找目录中的 RINEX 文件
    pattern = os.path.join(rinex_dir, f"????{doy}0.{yr2}o")
    rinex_files = sorted(glob.glob(pattern))

    if not rinex_files:
        return None

    # batch 文件固定头部
    l_file = f"l{expt}{xver}.{doy}"
    j_file = f"jbrdc{xver}.{doy}"

    lines = [
        "infor 1",
        "sceno 1 session.info",
        f"rinex 1 {rinex_dir}",
        "fica  0 ",
        f"coord 1 {l_file}",
        "stnfo 1 station.info",
        f"xfile 1 {rinex_dir}x",
        f"svclk 1 {j_file}",
        f"clock 1 {rinex_dir}k",
        "sp3   0 ",
        f"rdorb 1 {nav_file}",
        "gnss  1 G ",
        "site year doy sn  sw  ver",
        "(a4,1x,a4,1x,a3,1x,a1,2x,a3,1x,f5.2)",
    ]

    # 为每个 RINEX 文件添加站点条目
    for rinex_file in rinex_files:
        info = _parse_rinex_header(rinex_file)
        if not info['station']:
            continue

        rec_abbrev = _get_receiver_abbrev(info['rec_type'])
        rec_ver = _get_receiver_version(info['rec_version'])
        site_line = f"{info['station']:4s} {year} {doy} 1  {rec_abbrev}  {rec_ver:5.2f}"
        lines.append(site_line)

    return "\n".join(lines) + "\n"


def write_batch_file(expt, year, doy, output_dir='./', **kwargs):
    """生成并写入 makex batch 文件。

    Args:
        expt: 实验名
        year: 4 位年份
        doy: 年积日字符串
        output_dir: 输出目录
        **kwargs: 传递给 generate_makex_batch 的额外参数

    Returns:
        batch 文件路径，失败返回 None
    """
    content = generate_makex_batch(expt, year, doy, **kwargs)
    if content is None:
        return None

    batch_path = os.path.join(output_dir, f"{expt}.makex.batch")
    with open(batch_path, 'w') as f:
        f.write(content)

    return batch_path
