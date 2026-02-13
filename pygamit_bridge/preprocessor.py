"""
preprocessor.py — Module 2c: GAMIT 数据预处理器

将 prepare_day.sh 的核心功能用 Python 重写：
1. Compact RINEX3 (.crx.gz) 解压与格式转换
2. IGS 产品长文件名 → GAMIT 兼容短文件名映射
3. 广播星历准备
4. 全局表和配置文件链接

全部操作纯 Python 实现（调用 crx2rnx 等外部工具除外），
消除对 Shell 脚本的依赖。
"""

import os
import glob
import gzip
import shutil
import subprocess

from .utils import doy_to_gps_week, station_name_short
from .converter import convert_rinex3_to_rinex2


def decompress_crx_gz(crx_gz_path, output_dir):
    """解压 Compact RINEX (.crx.gz) 为标准 RINEX (.rnx)。

    流程：.crx.gz → gunzip → .crx → crx2rnx → .rnx

    Args:
        crx_gz_path: Compact RINEX 压缩文件路径
        output_dir: 输出目录

    Returns:
        解压后的 .rnx 文件路径，失败返回 None
    """
    basename = os.path.basename(crx_gz_path)

    # gunzip
    crx_path = os.path.join(output_dir, basename.replace('.gz', ''))
    try:
        with gzip.open(crx_gz_path, 'rb') as f_in:
            with open(crx_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
    except Exception:
        return None

    # crx2rnx（外部工具）
    rnx_path = crx_path.replace('.crx', '.rnx')
    try:
        result = subprocess.run(
            ['CRX2RNX', crx_path],
            capture_output=True, timeout=60
        )
        if result.returncode != 0:
            # 尝试小写命令
            subprocess.run(
                ['crx2rnx', crx_path],
                capture_output=True, timeout=60
            )
    except FileNotFoundError:
        # crx2rnx 不在 PATH 中，尝试常见路径
        for cmd in [os.path.expanduser('~/gg/bin/crx2rnx'),
                    '/usr/local/bin/crx2rnx']:
            if os.path.exists(cmd):
                subprocess.run([cmd, crx_path], capture_output=True, timeout=60)
                break
    except Exception:
        pass

    # 清理中间文件
    if os.path.exists(crx_path):
        os.remove(crx_path)

    if os.path.exists(rnx_path):
        return rnx_path
    return None


def prepare_rinex(year, doy, data_dir, expt_dir, stations=None):
    """预处理 RINEX 数据：解压、格式转换、短文件名生成。

    对每个站点执行：
    1. 查找 Compact RINEX3 文件 (.crx.gz)
    2. 解压为 RINEX3 (.rnx)
    3. 转换为 RINEX 2.11（调用 converter 模块）
    4. 生成 GAMIT 短文件名（如 mcm40010.25o）

    Args:
        year: 4 位年份
        doy: 年积日 (int)
        data_dir: 原始数据根目录（包含 year/doy 子目录）
        expt_dir: GAMIT 实验目录
        stations: 站点列表（None 表示自动检测）

    Returns:
        成功处理的站点数
    """
    doy_str = f"{doy:03d}"
    yr2 = str(year)[-2:]
    source_dir = os.path.join(data_dir, str(year), doy_str)
    os.makedirs(expt_dir, exist_ok=True)

    station_count = 0

    # 查找所有 .crx.gz 文件
    crx_files = glob.glob(os.path.join(source_dir, '*_MO.crx.gz'))
    if not crx_files:
        crx_files = glob.glob(os.path.join(source_dir, '*.crx.gz'))

    for crx_gz in crx_files:
        basename = os.path.basename(crx_gz)
        # 从长文件名提取站点名
        stn = station_name_short(basename)

        if stations and stn not in stations:
            continue

        # 解压
        rnx_path = decompress_crx_gz(crx_gz, expt_dir)
        if not rnx_path:
            continue

        # RINEX3 → RINEX2
        rnx2_path = os.path.join(expt_dir, f"{stn}_rnx2.tmp")
        if not convert_rinex3_to_rinex2(rnx_path, rnx2_path):
            os.remove(rnx_path)
            continue

        # 生成 GAMIT 短文件名: ssss{doy}0.{yr2}o
        short_name = f"{stn}{doy_str}0.{yr2}o"
        short_path = os.path.join(expt_dir, short_name)
        shutil.move(rnx2_path, short_path)

        # 清理中间文件
        if os.path.exists(rnx_path):
            os.remove(rnx_path)

        station_count += 1

    return station_count


def prepare_products(year, doy, data_dir, expt_dir):
    """准备 IGS 精密产品，映射长文件名为 GAMIT 短文件名。

    创建符号链接：
    - IGS0OPSFIN_*.SP3 → igs{week}{dow}.sp3
    - IGS0OPSFIN_*.CLK → igs{week}{dow}.clk

    Args:
        year: 4 位年份
        doy: 年积日
        data_dir: 产品数据根目录
        expt_dir: GAMIT 实验目录

    Returns:
        成功映射的产品数
    """
    doy_str = f"{doy:03d}"
    gps_week, dow = doy_to_gps_week(year, doy)
    source_dir = os.path.join(data_dir, str(year), doy_str)
    igs_dir = os.path.join(expt_dir, 'igs')
    os.makedirs(igs_dir, exist_ok=True)

    count = 0

    # 复制并解压产品文件
    for pattern in ['*SP3*', '*CLK*', '*ERP*', '*.sp3*', '*.clk*', '*.erp*']:
        for src_file in glob.glob(os.path.join(source_dir, pattern)):
            basename = os.path.basename(src_file)
            dst = os.path.join(igs_dir, basename)
            if not os.path.exists(dst):
                shutil.copy2(src_file, dst)

            # 解压 .gz
            if dst.endswith('.gz'):
                try:
                    decompressed = dst[:-3]
                    with gzip.open(dst, 'rb') as f_in:
                        with open(decompressed, 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    os.remove(dst)
                except Exception:
                    pass

            count += 1

    # 创建 GAMIT 短文件名映射
    # SP3
    sp3_files = glob.glob(os.path.join(igs_dir, 'IGS0OPSFIN_*ORB.SP3'))
    if sp3_files:
        sp3_short = os.path.join(igs_dir, f"igs{gps_week}{dow}.sp3")
        if not os.path.exists(sp3_short):
            try:
                os.symlink(sp3_files[0], sp3_short)
            except OSError:
                shutil.copy2(sp3_files[0], sp3_short)

    # CLK
    clk_files = glob.glob(os.path.join(igs_dir, 'IGS0OPSFIN_*CLK.CLK'))
    if clk_files:
        clk_short = os.path.join(igs_dir, f"igs{gps_week}{dow}.clk")
        if not os.path.exists(clk_short):
            try:
                os.symlink(clk_files[0], clk_short)
            except OSError:
                shutil.copy2(clk_files[0], clk_short)

    return count


def prepare_broadcast(year, doy, data_dir, expt_dir):
    """准备广播星历文件。

    查找并复制/解压广播星历，生成 GAMIT 短文件名。

    Args:
        year: 4 位年份
        doy: 年积日
        data_dir: 数据根目录
        expt_dir: GAMIT 实验目录

    Returns:
        True 如果成功
    """
    doy_str = f"{doy:03d}"
    yr2 = str(year)[-2:]
    source_dir = os.path.join(data_dir, str(year), doy_str)
    brdc_short = f"brdc{doy_str}0.{yr2}n"
    brdc_path = os.path.join(expt_dir, brdc_short)

    if os.path.exists(brdc_path):
        return True

    # 查找广播星历
    for pattern in [f'brdc{doy_str}0.{yr2}n.gz',
                    f'brdc{doy_str}0.{yr2}n.Z',
                    f'BRDC*{doy_str}*MN.rnx.gz']:
        matches = glob.glob(os.path.join(source_dir, pattern))
        if matches:
            src = matches[0]
            if src.endswith('.gz'):
                try:
                    with gzip.open(src, 'rb') as f_in:
                        with open(brdc_path, 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    return True
                except Exception:
                    pass
            else:
                shutil.copy2(src, brdc_path)
                return True

    return False


def link_tables(gg_dir, expt_dir, template_dir=None):
    """链接 GAMIT 全局表和本地配置到实验目录。

    Args:
        gg_dir: GAMIT 安装根目录（如 ~/gg）
        expt_dir: GAMIT 实验目录
        template_dir: 本地配置模板目录（可选）
    """
    tables_dir = os.path.join(expt_dir, 'tables')
    os.makedirs(tables_dir, exist_ok=True)

    # 链接全局表
    global_tables = os.path.join(gg_dir, 'tables')
    if os.path.isdir(global_tables):
        for item in os.listdir(global_tables):
            src = os.path.join(global_tables, item)
            dst = os.path.join(tables_dir, item)
            if not os.path.exists(dst):
                try:
                    os.symlink(src, dst)
                except OSError:
                    pass

    # 复制本地配置
    if template_dir and os.path.isdir(template_dir):
        local_dir = os.path.join(expt_dir, 'tables_local')
        os.makedirs(local_dir, exist_ok=True)
        for config in ['process.defaults', 'sites.defaults', 'sittbl.',
                       'sestbl.', 'station.info']:
            src = os.path.join(template_dir, config)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(local_dir, config))
