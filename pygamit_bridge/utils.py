"""
utils.py — 通用工具函数

提供 GPS 时间系统转换、文件检测等基础功能。
"""

import os
import struct
from datetime import datetime, timedelta


# GPS 纪元起始时间 (1980-01-06)
GPS_EPOCH = datetime(1980, 1, 6)


def doy_to_date(year: int, doy: int) -> datetime:
    """年积日 (DOY) 转换为日期对象。

    Args:
        year: 4 位年份
        doy: 年积日 (1-366)

    Returns:
        对应的 datetime 对象
    """
    return datetime(year, 1, 1) + timedelta(days=doy - 1)


def date_to_doy(dt: datetime) -> tuple:
    """日期对象转换为 (year, doy)。

    Args:
        dt: datetime 对象

    Returns:
        (year, doy) 元组
    """
    doy = dt.timetuple().tm_yday
    return dt.year, doy


def date_to_gps_week(year: int, month: int, day: int) -> tuple:
    """计算 GPS 周和周内日。

    Args:
        year: 4 位年份
        month: 月 (1-12)
        day: 日 (1-31)

    Returns:
        (gps_week, day_of_week) 元组，周内日 0=周日
    """
    dt = datetime(year, month, day)
    delta = dt - GPS_EPOCH
    gps_week = delta.days // 7
    dow = delta.days % 7
    return gps_week, dow


def doy_to_gps_week(year: int, doy: int) -> tuple:
    """从年积日计算 GPS 周和周内日。

    Args:
        year: 4 位年份
        doy: 年积日

    Returns:
        (gps_week, day_of_week) 元组
    """
    dt = doy_to_date(year, doy)
    return date_to_gps_week(dt.year, dt.month, dt.day)


def is_gzip(filepath: str) -> bool:
    """检查文件是否为真正的 gzip 格式（通过魔数 0x1f8b 判断）。

    CDDIS 认证失败时会返回 HTML 页面但保持 .gz 后缀，
    此函数用于检测这种情况。

    Args:
        filepath: 文件路径

    Returns:
        True 如果是合法的 gzip 文件
    """
    try:
        with open(filepath, 'rb') as f:
            magic = f.read(2)
            return magic == b'\x1f\x8b'
    except (IOError, OSError):
        return False


def is_html(filepath: str) -> bool:
    """检查文件是否为 HTML 页面（CDDIS 认证重定向产物）。

    当 CDDIS Earthdata 认证失败时，服务器返回 HTTP 200 + HTML 登录页，
    wget/curl 会将其保存为文件。此函数检测这种假数据文件。

    Args:
        filepath: 文件路径

    Returns:
        True 如果文件内容是 HTML
    """
    try:
        with open(filepath, 'rb') as f:
            head = f.read(512)
        # 检查是否包含 HTML 标签
        head_lower = head.lower()
        return (b'<!doctype html' in head_lower or
                b'<html' in head_lower or
                b'<head' in head_lower)
    except (IOError, OSError):
        return False


def find_gamit_home() -> str:
    """自动检测 GAMIT 安装路径。

    按优先级检查：
    1. 环境变量 GAMIT_HOME
    2. ~/gg/
    3. /opt/gg/

    Returns:
        GAMIT 安装根目录路径

    Raises:
        FileNotFoundError: 未找到 GAMIT 安装
    """
    # 检查环境变量
    gamit_home = os.environ.get('GAMIT_HOME', '')
    if gamit_home and os.path.isdir(gamit_home):
        return gamit_home

    # 检查常见路径
    for candidate in [
        os.path.expanduser('~/gg'),
        '/opt/gg',
        '/usr/local/gg',
    ]:
        if os.path.isdir(candidate):
            return candidate

    raise FileNotFoundError(
        "未找到 GAMIT 安装目录。请设置 GAMIT_HOME 环境变量。"
    )


def station_name_short(long_name: str) -> str:
    """从 RINEX3 长站点名提取 4 字符短名。

    例：'MCM400ATA' → 'mcm4'

    Args:
        long_name: RINEX3 格式 9 字符站点名

    Returns:
        4 字符小写站点名
    """
    return long_name[:4].lower()
