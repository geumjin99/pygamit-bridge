"""
parser.py — Module 3: GAMIT 输出标准化解析器

GAMIT 的处理结果分散在多种自定义格式文件中（o-file, q-file, summary 等），
缺乏统一的结构化输出接口。本模块提供标准化解析，将关键结果导出为 CSV/JSON：

- ZTD (天顶总延迟) 时间序列
- 站点坐标估计值
- 基线长度与精度
- 处理质量指标 (nrms, 模糊度固定率)
"""

import os
import re
import csv
import json
import glob


def parse_ztd(session_dir, expt='anta'):
    """从 GAMIT o-file/q-file 提取 ZTD 估计值。

    GAMIT o-file 中 ATMZEN 行的实际格式（固定列宽）：
      13*CAS1 ATMZEN  m           2.2655438832  -0.0107  0.0060  -1.8  2.25488495
      17*CAS1 ATMZEN  m   1       0.0000000000  -0.0244  0.0114  -2.1 -0.02436935

    无 epoch 编号的行是日均值（apriori ZTD + adjustment = total ZTD）；
    有 epoch 编号 (1-13) 的行是分段调整值（adjustment 相对于日均值）。
    最后一列是最终估计值（m）。

    Args:
        session_dir: GAMIT 会话输出目录
        expt: 实验名前缀

    Returns:
        ZTD 记录列表: [{'station': str, 'epoch_idx': int,
                        'ztd_m': float, 'adjustment_m': float,
                        'sigma_m': float}, ...]
    """
    results = []
    daily_ztd = {}  # 存储每站日均值: station → ztd_m

    # 查找 o-file
    ofiles = glob.glob(os.path.join(session_dir, f'o{expt}*.*'))
    if not ofiles:
        ofiles = glob.glob(os.path.join(session_dir, 'o*.*'))

    # ATMZEN 行解析正则
    # 实际格式（注意 apriori 和 adjustment 紧密相连，无空格！）：
    # "   13*CAS1 ATMZEN  m           2.2655438832-0.1066D-01 0.5965D-02  -1.8       2.25488495"
    # "   17*CAS1 ATMZEN  m   1       0.0000000000-0.2437D-01 0.1142D-01  -2.1      -0.02436935"
    atmzen_re = re.compile(
        r'(\d+)\*(\w{4})\s+ATMZEN\s+m\s*'
        r'(\d+)?\s*'                              # epoch 编号（可选）
        r'(\d+\.\d+)'                              # apriori 值
        r'([-+]?[\d.]+D[+-]?\d+)\s+'              # adjustment（Fortran D 格式，紧密相连）
        r'([\d.]+D[+-]?\d+)\s+'                   # sigma（Fortran D 格式）
        r'([-+]?[\d.]+)\s+'                       # ratio
        r'([-+]?[\d.]+)'                          # 最终估计值
    )

    for ofile in ofiles:
        with open(ofile, 'r', errors='replace') as f:
            for line in f:
                if 'ATMZEN' not in line:
                    continue

                match = atmzen_re.search(line)
                if not match:
                    continue

                station = match.group(2).upper()
                epoch_str = match.group(3)
                adjustment_raw = match.group(5).replace('D', 'E')
                sigma_raw = match.group(6).replace('D', 'E')
                total_ztd = float(match.group(8))

                try:
                    adjustment = float(adjustment_raw)
                    sigma = float(sigma_raw)
                except ValueError:
                    continue

                if epoch_str is None:
                    # 日均值行：total_ztd 是完整的天顶延迟 (m)
                    epoch_idx = 0
                    daily_ztd[station] = total_ztd
                else:
                    # 分段调整行：total_ztd 是 adjustment 值
                    epoch_idx = int(epoch_str)

                results.append({
                    'station': station,
                    'epoch_idx': epoch_idx,
                    'ztd_m': round(total_ztd, 8),
                    'ztd_mm': round(total_ztd * 1000, 1),
                    'adjustment_m': round(adjustment, 6),
                    'sigma_m': round(sigma, 6),
                    'sigma_mm': round(sigma * 1000, 1),
                })

    # 对分段值加上日均值，得到绝对 ZTD
    for rec in results:
        if rec['epoch_idx'] > 0 and rec['station'] in daily_ztd:
            absolute_ztd = daily_ztd[rec['station']] + rec['ztd_m']
            rec['ztd_m'] = round(absolute_ztd, 8)
            rec['ztd_mm'] = round(absolute_ztd * 1000, 1)

    return results


def parse_positions(session_dir, expt='anta'):
    """从 GAMIT o-file 提取站点坐标估计值。

    GAMIT o-file 中坐标行的实际格式：
      1*CAS1 GEOC LAT  dms    S66:08:28.75542 0.1971D-02 0.2461D-01  0.1  S66:08:28.75536
      2*CAS1 GEOC LONG dms   E110:31:10.94427-0.2388D-02 0.2465D-01 -0.1 E110:31:10.94408
      3*CAS1 RADIUS    km     6360.2587609893-0.2210D-02 0.2822D-01 -0.1  6360.25875878

    Returns:
        站点坐标字典: {station: {'lat': str, 'lon': str, 'radius_km': float,
                                 'lat_adj_m': float, 'lon_adj_m': float,
                                 'radius_adj_m': float, 'lat_sigma_m': float, ...}}
    """
    positions = {}

    ofiles = glob.glob(os.path.join(session_dir, f'o{expt}*.*'))
    if not ofiles:
        ofiles = glob.glob(os.path.join(session_dir, 'o*.*'))

    # 匹配 GEOC LAT/LONG 行和 RADIUS 行
    coord_re = re.compile(
        r'(\d+)\*(\w{4})\s+(?:GEOC\s+)?(LAT|LONG|RADIUS)\s+'
    )

    for ofile in ofiles:
        with open(ofile, 'r', errors='replace') as f:
            for line in f:
                match = coord_re.search(line)
                if not match:
                    continue

                station = match.group(2).upper()
                coord_type = match.group(3)  # LAT, LONG, RADIUS

                if station not in positions:
                    positions[station] = {}

                # 提取 Fortran D 格式的调整量和 sigma
                d_values = re.findall(r'([-+]?[\d.]+D[+-]?\d+)', line)
                adjustment = float(d_values[0].replace('D', 'E')) if len(d_values) >= 1 else 0.0
                sigma = float(d_values[1].replace('D', 'E')) if len(d_values) >= 2 else 0.0

                if coord_type == 'LAT':
                    # 提取最终纬度值（如 S66:08:28.75536）
                    lat_match = re.search(r'([NS]\d+:\d+:[\d.]+)\s*$', line)
                    positions[station]['lat'] = lat_match.group(1) if lat_match else ''
                    positions[station]['lat_adj_m'] = round(adjustment, 4)
                    positions[station]['lat_sigma_m'] = round(sigma, 4)
                elif coord_type == 'LONG':
                    lon_match = re.search(r'([EW]\d+:\d+:[\d.]+)\s*$', line)
                    positions[station]['lon'] = lon_match.group(1) if lon_match else ''
                    positions[station]['lon_adj_m'] = round(adjustment, 4)
                    positions[station]['lon_sigma_m'] = round(sigma, 4)
                elif coord_type == 'RADIUS':
                    # 提取最终半径值
                    rad_match = re.search(r'(\d{4}\.\d+)\s*$', line)
                    positions[station]['radius_km'] = float(rad_match.group(1)) if rad_match else 0.0
                    positions[station]['radius_adj_m'] = round(adjustment, 4)
                    positions[station]['radius_sigma_m'] = round(sigma, 4)

    return positions


def parse_baselines(session_dir, expt='anta'):
    """从 GAMIT o-file 提取基线长度与精度。

    Args:
        session_dir: GAMIT 会话输出目录
        expt: 实验名前缀

    Returns:
        基线列表: [{'from': str, 'to': str,
                     'length_m': float, 'sigma_m': float}, ...]
    """
    baselines = []

    ofiles = glob.glob(os.path.join(session_dir, f'o{expt}*.*'))
    if not ofiles:
        ofiles = glob.glob(os.path.join(session_dir, 'o*.*'))

    for ofile in ofiles:
        with open(ofile, 'r', errors='replace') as f:
            in_baseline = False
            for line in f:
                if 'Baseline' in line and 'Length' in line:
                    in_baseline = True
                    continue
                if in_baseline and line.strip() == '':
                    in_baseline = False
                    continue
                if in_baseline:
                    parts = line.split()
                    if len(parts) >= 4:
                        try:
                            stn1 = parts[0][:4].upper()
                            stn2 = parts[1][:4].upper()
                            length = float(parts[2])
                            sigma = float(parts[3]) if len(parts) > 3 else 0.0
                            baselines.append({
                                'from': stn1, 'to': stn2,
                                'length_m': round(length, 4),
                                'sigma_m': round(sigma, 4),
                            })
                        except ValueError:
                            continue

    return baselines


def parse_summary(session_dir, expt='anta'):
    """从 GAMIT 处理摘要文件提取质量指标。

    提取的指标包括：
    - nrms (归一化均方根残差)
    - postfit_nrms (后验 nrms)
    - 模糊度固定率（WL 和 NL）
    - 观测值数和参数数

    summary 文件中的实际格式：
      Prefit nrms:  0.41331E+00    Postfit nrms: 0.23542E+00
      Phase ambiguities (Total  WL-fixed   NL-fixed): 89 87 76
      Phase ambiguities WL fixed  97.8% NL fixed  85.4%

    Returns:
        质量指标字典
    """
    summary = {
        'nrms': None,
        'postfit_nrms': None,
        'num_ambiguities': None,
        'wl_fixed': None,
        'nl_fixed': None,
        'wl_rate': None,
        'nl_rate': None,
        'num_observations': None,
        'num_parameters': None,
    }

    # 尝试从 sh_gamit summary 文件提取
    summary_files = glob.glob(os.path.join(session_dir, f'sh_{expt}*summary'))
    summary_files += glob.glob(os.path.join(session_dir, '*.summary'))

    for sf in summary_files:
        with open(sf, 'r', errors='replace') as f:
            for line in f:
                # 提取 nrms（Fortran E 格式）
                # "Prefit nrms:  0.41331E+00    Postfit nrms: 0.23542E+00"
                if 'Prefit nrms' in line:
                    pre_match = re.search(r'Prefit\s+nrms\s*:\s*([\d.]+E[+-]?\d+)', line)
                    post_match = re.search(r'Postfit\s+nrms\s*:\s*([\d.]+E[+-]?\d+)', line)
                    if pre_match:
                        summary['nrms'] = round(float(pre_match.group(1)), 5)
                    if post_match:
                        summary['postfit_nrms'] = round(float(post_match.group(1)), 5)

                # 提取模糊度数量
                # "Phase ambiguities (Total  WL-fixed   NL-fixed): 89 87 76"
                if 'Phase ambiguities' in line and 'Total' in line:
                    nums = re.findall(r'\)\s*:\s*(\d+)\s+(\d+)\s+(\d+)', line)
                    if nums:
                        summary['num_ambiguities'] = int(nums[0][0])
                        summary['wl_fixed'] = int(nums[0][1])
                        summary['nl_fixed'] = int(nums[0][2])

                # 提取模糊度固定率
                # "Phase ambiguities WL fixed  97.8% NL fixed  85.4%"
                if 'WL fixed' in line and '%' in line:
                    wl_match = re.search(r'WL\s+fixed\s+([\d.]+)%', line)
                    nl_match = re.search(r'NL\s+fixed\s+([\d.]+)%', line)
                    if wl_match:
                        summary['wl_rate'] = float(wl_match.group(1))
                    if nl_match:
                        summary['nl_rate'] = float(nl_match.group(1))

    # 从 o-file 提取观测值数和参数数
    ofiles = glob.glob(os.path.join(session_dir, f'o{expt}*.*'))
    if not ofiles:
        ofiles = glob.glob(os.path.join(session_dir, 'o*.*'))
    for ofile in ofiles:
        with open(ofile, 'r', errors='replace') as f:
            for line in f:
                if 'Double-difference observations' in line:
                    m = re.search(r'(\d+)', line)
                    if m:
                        summary['num_observations'] = int(m.group(1))
                if 'Total parameters' in line:
                    nums = re.findall(r'(\d+)', line)
                    if len(nums) >= 1:
                        summary['num_parameters'] = int(nums[0])
                    if len(nums) >= 2:
                        summary['live_parameters'] = int(nums[1])

    # 回退：从 q-file 提取 nrms
    if summary['nrms'] is None:
        qfiles = glob.glob(os.path.join(session_dir, f'q{expt}*.*'))
        if not qfiles:
            qfiles = glob.glob(os.path.join(session_dir, 'q*.*'))
        for qf in qfiles:
            with open(qf, 'r', errors='replace') as f:
                for line in f:
                    if 'nrms' in line.lower():
                        match = re.search(r'([\d.]+E[+-]?\d+|[\d.]+)', line)
                        if match:
                            val = float(match.group(1))
                            if 0 < val < 10:
                                summary['nrms'] = round(val, 5)

    return summary


def parse_session(session_dir, expt='anta'):
    """一站式解析 GAMIT 会话的全部输出。

    整合 ZTD、坐标、基线和质量指标的解析结果。

    Args:
        session_dir: GAMIT 会话输出目录
        expt: 实验名前缀

    Returns:
        包含所有解析结果的字典
    """
    return {
        'ztd': parse_ztd(session_dir, expt),
        'positions': parse_positions(session_dir, expt),
        'baselines': parse_baselines(session_dir, expt),
        'summary': parse_summary(session_dir, expt),
    }


def export_csv(results, output_path):
    """将解析结果导出为 CSV 文件。

    ZTD 数据导出为时间序列格式。

    Args:
        results: parse_session 的返回值
        output_path: CSV 输出文件路径
    """
    ztd_data = results.get('ztd', [])
    if not ztd_data:
        return

    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['station', 'epoch_idx',
                                                'ztd_mm', 'sigma_mm',
                                                'ztd_m', 'sigma_m',
                                                'adjustment_m'])
        writer.writeheader()
        writer.writerows(ztd_data)


def export_json(results, output_path):
    """将全部解析结果导出为 JSON 文件。

    Args:
        results: parse_session 的返回值
        output_path: JSON 输出文件路径
    """
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
