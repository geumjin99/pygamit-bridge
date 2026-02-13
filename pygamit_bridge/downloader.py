"""
downloader.py — Module 1: CDDIS 智能数据下载器

解决 2020 年后 CDDIS 强制 Earthdata 认证带来的数据获取问题：
- 自动处理 Earthdata cookie 认证
- 检测 HTML 登录页面伪装的数据文件
- 支持 IGS 长文件名和旧格式短文件名自动回退
- 支持 RINEX 观测数据和精密产品（SP3/CLK/ERP/BRDC）下载
"""

import os
import subprocess

from .utils import doy_to_date, doy_to_gps_week, is_gzip, is_html

# CDDIS 基础 URL
CDDIS_BASE = "https://cddis.nasa.gov/archive/gnss/data/daily"
CDDIS_PRODUCTS = "https://cddis.nasa.gov/archive/gnss/products"

# wget Earthdata 认证参数
WGET_AUTH = [
    '--no-check-certificate',
    '--load-cookies', os.path.expanduser('~/.urs_cookies'),
    '--save-cookies', os.path.expanduser('~/.urs_cookies'),
    '--auth-no-challenge',
    '--keep-session-cookies',
]

# 常见 IGS 站点国家代码（用于构造 RINEX3 长文件名）
COUNTRY_CODES = [
    'ATA', 'AUS', 'JPN', 'USA', 'ZAF', 'CHL', 'FRA',
    'NZL', 'NOR', 'DEU', 'GBR', 'ARG', 'RUS', 'CHN',
]

# 最小有效文件大小阈值
MIN_RINEX_SIZE = 5000   # RINEX 文件至少几 KB
MIN_PRODUCT_SIZE = 1000  # 产品文件至少 1 KB


def _wget_download(url, output_file, timeout=120):
    """使用 wget 下载单个文件（带 Earthdata 认证）。

    Args:
        url: 下载 URL
        output_file: 本地保存路径
        timeout: 超时秒数

    Returns:
        True 如果下载成功且文件有效
    """
    try:
        result = subprocess.run(
            ['wget', '-q'] + WGET_AUTH + ['-O', output_file, url],
            capture_output=True, timeout=timeout
        )
        if result.returncode == 0 and os.path.exists(output_file):
            fsize = os.path.getsize(output_file)
            # 检查是否是 HTML 登录页面伪装的假文件
            if fsize > MIN_PRODUCT_SIZE and not is_html(output_file):
                return True
            # 文件太小或是 HTML，删除
            os.remove(output_file)
    except subprocess.TimeoutExpired:
        if os.path.exists(output_file):
            os.remove(output_file)
    except Exception:
        if os.path.exists(output_file):
            os.remove(output_file)
    return False


def download_rinex(station, year, doy, output_dir):
    """下载单站单日 RINEX 观测数据。

    自动尝试 RINEX3 长文件名格式，失败后回退至短文件名。
    下载前检查是否已有有效文件（gzip 魔数验证），避免重复下载。

    Args:
        station: 4 字符站点名（如 'mcm4'）
        year: 4 位年份
        doy: 年积日 (1-366)
        output_dir: 输出根目录

    Returns:
        状态字符串 ('OK: ...', 'EXISTS: ...', 'FAIL: ...')
    """
    doy_str = f"{doy:03d}"
    yr2 = str(year)[2:]
    station_upper = station.upper()

    output_subdir = os.path.join(output_dir, str(year), doy_str)
    os.makedirs(output_subdir, exist_ok=True)

    # 检查已有有效文件
    for f in os.listdir(output_subdir):
        fp = os.path.join(output_subdir, f)
        if f.startswith(station_upper) and f.endswith('.crx.gz'):
            if os.path.getsize(fp) > MIN_RINEX_SIZE and is_gzip(fp):
                return f"EXISTS: {f}"
            else:
                os.remove(fp)

    # 策略 1: RINEX3 长文件名 + 各种国家代码
    url_base = f"{CDDIS_BASE}/{year}/{doy_str}/{yr2}d/"
    for cc in COUNTRY_CODES:
        fname = f"{station_upper}00{cc}_R_{year}{doy_str}0000_01D_30S_MO.crx.gz"
        url = url_base + fname
        output_file = os.path.join(output_subdir, fname)
        if _wget_download(url, output_file):
            fsize = os.path.getsize(output_file)
            return f"OK: {fname} ({fsize // 1024}KB)"

    # 策略 2: 旧格式短文件名
    url_short_base = f"{CDDIS_BASE}/{year}/{doy_str}/{yr2}o/"
    for ext in ['.gz', '.Z']:
        short_name = f"{station}{doy_str}0.{yr2}d{ext}"
        url = url_short_base + short_name
        output_file = os.path.join(output_subdir, short_name)
        if _wget_download(url, output_file):
            fsize = os.path.getsize(output_file)
            return f"OK: {short_name} ({fsize // 1024}KB)"

    return f"FAIL: {station} {year} {doy_str}"


def download_products(year, doy, output_dir):
    """下载 IGS 精密产品 (SP3, CLK, ERP) 和广播星历。

    自动尝试 2022 年后的长文件名格式，失败后回退至旧短文件名。

    Args:
        year: 4 位年份
        doy: 年积日
        output_dir: 产品输出根目录

    Returns:
        结果列表，每个元素为状态字符串
    """
    gps_week, dow = doy_to_gps_week(year, doy)
    doy_str = f"{doy:03d}"
    yr2 = str(year)[2:]

    output_subdir = os.path.join(output_dir, str(year), doy_str)
    os.makedirs(output_subdir, exist_ok=True)

    products_url = f"{CDDIS_PRODUCTS}/{gps_week}/"

    # 产品清单：(长文件名, 短文件名)
    product_pairs = [
        (f"IGS0OPSFIN_{year}{doy_str}0000_01D_15M_ORB.SP3.gz",
         f"igs{gps_week}{dow}.sp3.Z"),
        (f"IGS0OPSFIN_{year}{doy_str}0000_01D_30S_CLK.CLK.gz",
         f"igs{gps_week}{dow}.clk.Z"),
        (f"IGS0OPSFIN_{year}{doy_str}0000_07D_01D_ERP.ERP.gz",
         f"igs{gps_week}7.erp.Z"),
    ]

    results = []

    for name_new, name_old in product_pairs:
        downloaded = False
        for fname in [name_new, name_old]:
            output_file = os.path.join(output_subdir, fname)

            # 检查已有有效文件
            if os.path.exists(output_file) and os.path.getsize(output_file) > MIN_PRODUCT_SIZE:
                if is_gzip(output_file) or output_file.endswith('.Z'):
                    results.append(f"EXISTS: {fname}")
                    downloaded = True
                    break
                else:
                    os.remove(output_file)

            url = products_url + fname
            if _wget_download(url, output_file):
                fsize = os.path.getsize(output_file)
                results.append(f"OK: {fname} ({fsize // 1024}KB)")
                downloaded = True
                break

        if not downloaded:
            results.append(f"FAIL: {name_old.split('.')[0]}")

    # 广播星历
    brdc_name = f"brdc{doy_str}0.{yr2}n.gz"
    brdc_out = os.path.join(output_subdir, brdc_name)
    if os.path.exists(brdc_out) and os.path.getsize(brdc_out) > MIN_PRODUCT_SIZE:
        results.append(f"EXISTS: BRDC")
    else:
        brdc_downloaded = False
        for bn in [brdc_name, f"brdc{doy_str}0.{yr2}n.Z"]:
            url = f"{CDDIS_BASE}/{year}/{doy_str}/{yr2}n/{bn}"
            if _wget_download(url, brdc_out):
                fsize = os.path.getsize(brdc_out)
                results.append(f"OK: BRDC ({fsize // 1024}KB)")
                brdc_downloaded = True
                break
        if not brdc_downloaded:
            results.append("FAIL: BRDC")

    return results
