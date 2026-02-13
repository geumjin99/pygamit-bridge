"""
converter.py — Module 2a: RINEX 3 → RINEX 2 格式转换器

GAMIT 的核心 Fortran 模块 (makexp) 无法正确解析 RINEX 3.x 头部中
按卫星系统分组的观测类型声明 (SYS / # / OBS TYPES)。这导致：
- makexp 不生成 X-file
- 后续 makex batch 文件为空
- 整条处理链断裂

本模块将 RINEX 3.x 观测文件完整转换为 GAMIT 兼容的 RINEX 2.11 格式：
1. 头部版本标识：3.xx → 2.11
2. 观测类型映射：3字符码 (C1C,L1C,...) → 2字符码 (C1,L1,...)
3. 数据格式：每卫星一行 → RINEX2 传统多行格式
"""

import os
import sys
import shutil
from collections import OrderedDict

# RINEX3 → RINEX2 观测类型映射表
# RINEX3: 3 字符 (C1C, L1C, S1C, D1C, ...)
# RINEX2: 2 字符 (C1, L1, S1, D1, P1, P2, L2, ...)
OBS_MAPPING = {
    # GPS L1 频段
    'C1C': 'C1', 'C1S': 'C1', 'C1L': 'C1', 'C1X': 'C1',
    'C1P': 'P1', 'C1W': 'P1',
    'L1C': 'L1', 'L1S': 'L1', 'L1L': 'L1', 'L1X': 'L1',
    'L1P': 'L1', 'L1W': 'L1',
    'D1C': 'D1', 'D1S': 'D1', 'D1L': 'D1', 'D1X': 'D1',
    'S1C': 'S1', 'S1S': 'S1', 'S1L': 'S1', 'S1X': 'S1',
    # GPS L2 频段
    'C2C': 'C2', 'C2S': 'C2', 'C2L': 'C2', 'C2X': 'C2',
    'C2P': 'P2', 'C2W': 'P2',
    'L2C': 'L2', 'L2S': 'L2', 'L2L': 'L2', 'L2X': 'L2',
    'L2P': 'L2', 'L2W': 'L2',
    'D2C': 'D2', 'D2S': 'D2', 'D2L': 'D2', 'D2X': 'D2',
    'S2C': 'S2', 'S2S': 'S2', 'S2L': 'S2', 'S2X': 'S2',
    # GPS L5 频段
    'C5I': 'C5', 'C5Q': 'C5', 'C5X': 'C5',
    'L5I': 'L5', 'L5Q': 'L5', 'L5X': 'L5',
    'D5I': 'D5', 'D5Q': 'D5', 'D5X': 'D5',
    'S5I': 'S5', 'S5Q': 'S5', 'S5X': 'S5',
}


def _parse_rinex3_header(lines):
    """解析 RINEX3 文件头部，提取所有关键元数据。

    Args:
        lines: 文件内容行列表

    Returns:
        包含头部信息的字典
    """
    header = {
        'version': '3.04',
        'type': 'O',
        'system': 'M',
        'marker_name': '',
        'marker_number': '',
        'observer': '',
        'agency': '',
        'receiver': {'serial': '', 'type': '', 'version': ''},
        'antenna': {'serial': '', 'type': '', 'delta': (0.0, 0.0, 0.0)},
        'approx_pos': (0.0, 0.0, 0.0),
        'obs_types': {},
        'interval': 30.0,
        'time_first': '',
        'time_last': '',
        'header_end_line': 0,
    }

    i = 0
    while i < len(lines):
        line = lines[i]
        label = line[60:].strip() if len(line) > 60 else ''

        if label == 'RINEX VERSION / TYPE':
            header['version'] = line[0:9].strip()
            header['type'] = line[20:21].strip()
            header['system'] = line[40:41].strip()
        elif label == 'MARKER NAME':
            header['marker_name'] = line[0:60].strip()
        elif label == 'MARKER NUMBER':
            header['marker_number'] = line[0:20].strip()
        elif label == 'OBSERVER / AGENCY':
            header['observer'] = line[0:20].strip()
            header['agency'] = line[20:40].strip()
        elif label == 'REC # / TYPE / VERS':
            header['receiver']['serial'] = line[0:20].strip()
            header['receiver']['type'] = line[20:40].strip()
            header['receiver']['version'] = line[40:60].strip()
        elif label == 'ANT # / TYPE':
            header['antenna']['serial'] = line[0:20].strip()
            header['antenna']['type'] = line[20:40].strip()
        elif label == 'APPROX POSITION XYZ':
            try:
                x = float(line[0:14])
                y = float(line[14:28])
                z = float(line[28:42])
                header['approx_pos'] = (x, y, z)
            except ValueError:
                pass
        elif label == 'ANTENNA: DELTA H/E/N':
            try:
                h = float(line[0:14])
                e = float(line[14:28])
                n = float(line[28:42])
                header['antenna']['delta'] = (h, e, n)
            except ValueError:
                pass
        elif label == 'SYS / # / OBS TYPES':
            # RINEX3 按系统分组的观测类型声明，可能有续行
            sys_code = line[0:1]
            num_obs = int(line[3:6].strip())
            obs_types = line[7:60].split()
            while len(obs_types) < num_obs and i + 1 < len(lines):
                i += 1
                next_line = lines[i]
                next_label = next_line[60:].strip() if len(next_line) > 60 else ''
                if next_label == 'SYS / # / OBS TYPES':
                    obs_types.extend(next_line[7:60].split())
                else:
                    break
            header['obs_types'][sys_code] = obs_types[:num_obs]
        elif label == 'INTERVAL':
            try:
                header['interval'] = float(line[0:10])
            except ValueError:
                pass
        elif label == 'TIME OF FIRST OBS':
            header['time_first'] = line[0:60].strip()
        elif label == 'TIME OF LAST OBS':
            header['time_last'] = line[0:60].strip()
        elif label == 'END OF HEADER':
            header['header_end_line'] = i
            break

        i += 1

    return header


def _build_obs_type_mapping(header):
    """构建 RINEX3→RINEX2 观测类型映射。

    仅保留 GPS (G) 系统的观测类型，去重并保持顺序。

    Args:
        header: 解析后的头部字典

    Returns:
        (rnx2_types, mapping) — RINEX2 类型列表和索引映射字典
    """
    gps_types = header['obs_types'].get('G', [])
    rnx2_types = []
    seen = set()
    mapping = {}

    for idx, rnx3_type in enumerate(gps_types):
        rnx2_type = OBS_MAPPING.get(rnx3_type, None)
        if rnx2_type and rnx2_type not in seen:
            seen.add(rnx2_type)
            rnx2_types.append(rnx2_type)
        mapping[idx] = rnx2_type

    return rnx2_types, mapping


def _write_rinex2_header(f, header, rnx2_types):
    """生成并写入 RINEX 2.11 格式头部。"""
    # RINEX VERSION / TYPE
    f.write(f"     2.11           OBSERVATION DATA    {'G':20s}RINEX VERSION / TYPE\n")
    # PGM / RUN BY / DATE
    f.write(f"{'pygamit-bridge':20s}{'':20s}{'':20s}PGM / RUN BY / DATE\n")
    # MARKER NAME
    f.write(f"{header['marker_name']:60s}MARKER NAME\n")
    # MARKER NUMBER
    if header['marker_number']:
        f.write(f"{header['marker_number']:60s}MARKER NUMBER\n")
    # OBSERVER / AGENCY
    f.write(f"{header['observer']:20s}{header['agency']:40s}OBSERVER / AGENCY\n")
    # REC # / TYPE / VERS
    r = header['receiver']
    f.write(f"{r['serial']:20s}{r['type']:20s}{r['version']:20s}REC # / TYPE / VERS\n")
    # ANT # / TYPE
    a = header['antenna']
    f.write(f"{a['serial']:20s}{a['type']:20s}{'':20s}ANT # / TYPE\n")
    # APPROX POSITION XYZ
    pos = header['approx_pos']
    f.write(f"{pos[0]:14.4f}{pos[1]:14.4f}{pos[2]:14.4f}{'':18s}APPROX POSITION XYZ\n")
    # ANTENNA: DELTA H/E/N
    delta = a['delta']
    f.write(f"{delta[0]:14.4f}{delta[1]:14.4f}{delta[2]:14.4f}{'':18s}ANTENNA: DELTA H/E/N\n")
    # WAVELENGTH FACT L1/2 (RINEX2 特有)
    f.write(f"     1     1{'':48s}WAVELENGTH FACT L1/2\n")
    # # / TYPES OF OBSERV（每行最多 9 个类型，每类型 6 字符宽）
    num = len(rnx2_types)
    lines_needed = (num + 8) // 9
    for line_idx in range(lines_needed):
        if line_idx == 0:
            obs_line = f"{num:6d}"
        else:
            obs_line = "      "
        start = line_idx * 9
        end = min(start + 9, num)
        for j in range(start, end):
            obs_line += f"{rnx2_types[j]:>6s}"
        obs_line = obs_line.ljust(60)
        obs_line += "# / TYPES OF OBSERV\n"
        f.write(obs_line)
    # INTERVAL
    f.write(f"{header['interval']:10.3f}{'':50s}INTERVAL\n")
    # TIME OF FIRST OBS
    if header['time_first']:
        f.write(f"{header['time_first']:60s}TIME OF FIRST OBS\n")
    # TIME OF LAST OBS
    if header['time_last']:
        f.write(f"{header['time_last']:60s}TIME OF LAST OBS\n")
    # END OF HEADER
    f.write(f"{'':60s}END OF HEADER\n")


def _convert_data(lines, data_start, header, rnx2_types, mapping, outf):
    """将 RINEX3 观测数据记录转换为 RINEX2 格式。

    RINEX3: 每颗卫星占一行，'>' 前缀标记 epoch
    RINEX2: 传统多行格式，epoch 行包含卫星列表
    """
    gps_types = header['obs_types'].get('G', [])
    i = data_start

    while i < len(lines):
        line = lines[i]

        if line.startswith('>'):
            try:
                yr = int(line[2:6])
                mo = int(line[7:9])
                dy = int(line[10:12])
                hr = int(line[13:15])
                mn = int(line[16:18])
                sc = float(line[18:29])
                flag = int(line[29:32])
                num_sats = int(line[32:35])
            except (ValueError, IndexError):
                i += 1
                continue

            # 收集 GPS 卫星数据
            sats = []
            sat_data = {}
            for j in range(num_sats):
                i += 1
                if i >= len(lines):
                    break
                sat_line = lines[i]
                sat_id = sat_line[0:3].strip()
                if not sat_id.startswith('G'):
                    continue

                values = []
                for k in range(len(gps_types)):
                    start_pos = 3 + k * 16
                    end_pos = start_pos + 16
                    if start_pos < len(sat_line):
                        values.append(sat_line[start_pos:end_pos])
                    else:
                        values.append(' ' * 16)

                sats.append(sat_id)
                sat_data[sat_id] = values

            if not sats:
                i += 1
                continue

            # 写入 RINEX2 epoch 头
            yr2 = yr % 100
            epoch_hdr = (f" {yr2:2d} {mo:2d} {dy:2d} {hr:2d} {mn:2d}"
                         f"{sc:11.7f}  {flag:1d}{len(sats):3d}")
            for k, sat in enumerate(sats):
                epoch_hdr += f"{sat:>3s}"
                if (k + 1) % 12 == 0 and k + 1 < len(sats):
                    epoch_hdr += "\n" + " " * 32
            outf.write(epoch_hdr + "\n")

            # 写入观测值（每行最多 5 个）
            for sat in sats:
                values = sat_data[sat]
                rnx2_values = []
                for rnx2_type in rnx2_types:
                    found = False
                    for idx, rnx3_type in enumerate(gps_types):
                        if mapping.get(idx) == rnx2_type:
                            if idx < len(values):
                                rnx2_values.append(values[idx])
                            else:
                                rnx2_values.append(' ' * 16)
                            found = True
                            break
                    if not found:
                        rnx2_values.append(' ' * 16)

                obs_line = ""
                for k, val in enumerate(rnx2_values):
                    val_str = val.rstrip() if len(val) > 0 else ''
                    if len(val_str) >= 14:
                        num_part = val_str[:14]
                        lli = val_str[14:15] if len(val_str) > 14 else ' '
                        sig = val_str[15:16] if len(val_str) > 15 else ' '
                    elif len(val_str) > 0:
                        num_part = f"{val_str:>14s}"
                        lli = ' '
                        sig = ' '
                    else:
                        num_part = ' ' * 14
                        lli = ' '
                        sig = ' '

                    obs_line += f"{num_part}{lli}{sig}"
                    if (k + 1) % 5 == 0:
                        outf.write(obs_line + "\n")
                        obs_line = ""

                if obs_line:
                    outf.write(obs_line + "\n")

        i += 1


def convert_rinex3_to_rinex2(input_file, output_file):
    """RINEX 3.x → RINEX 2.11 完整格式转换。

    如果输入文件已经是 RINEX 2 格式，直接复制。

    Args:
        input_file: RINEX 3.x 输入文件路径
        output_file: RINEX 2.11 输出文件路径

    Returns:
        True 如果转换成功
    """
    with open(input_file, 'r', errors='replace') as f:
        lines = f.readlines()

    # 检查版本号
    if not lines[0][0:9].strip().startswith('3'):
        # 已经是 RINEX 2，直接复制
        shutil.copy2(input_file, output_file)
        return True

    header = _parse_rinex3_header(lines)
    rnx2_types, mapping = _build_obs_type_mapping(header)

    if not rnx2_types:
        return False

    with open(output_file, 'w') as outf:
        _write_rinex2_header(outf, header, rnx2_types)
        _convert_data(
            lines, header['header_end_line'] + 1,
            header, rnx2_types, mapping, outf
        )

    return True
