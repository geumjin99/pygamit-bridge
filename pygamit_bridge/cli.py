"""
cli.py — PyGAMIT-Bridge 统一命令行接口

提供 download / convert / preprocess / parse 四个子命令：

    pygamit-bridge download  --station mcm4 --year 2025 --doy 1
    pygamit-bridge convert   --input file.rnx --output file.obs
    pygamit-bridge preprocess --year 2025 --doy 1 --data-dir ./data --expt-dir ./expt
    pygamit-bridge parse     --session-dir ./expt/2025001 --output results.csv
"""

import argparse
import sys
import os


def cmd_download(args):
    """download 子命令处理"""
    from .downloader import download_rinex, download_products

    stations = args.stations.split(',')
    year = args.year

    for doy in range(args.start_doy, args.end_doy + 1):
        # 下载 RINEX
        if not args.products_only:
            for station in stations:
                result = download_rinex(station, year, doy, args.output)
                print(f"  [{station.upper()} DOY {doy:03d}] {result}")

        # 下载产品
        if not args.stations_only:
            results = download_products(year, doy, args.products_output)
            print(f"  [Products DOY {doy:03d}] {results}")


def cmd_convert(args):
    """convert 子命令处理"""
    from .converter import convert_rinex3_to_rinex2

    success = convert_rinex3_to_rinex2(args.input, args.output)
    if success:
        fsize = os.path.getsize(args.output)
        print(f"[OK] {args.input} → {args.output} ({fsize // 1024}KB)")
    else:
        print(f"[FAIL] 转换失败: {args.input}")
        sys.exit(1)


def cmd_preprocess(args):
    """preprocess 子命令处理"""
    from .preprocessor import (prepare_rinex, prepare_products,
                               prepare_broadcast, link_tables)

    stations = args.stations.split(',') if args.stations else None

    print(f"[1/4] 预处理 RINEX...")
    n = prepare_rinex(args.year, args.doy, args.data_dir,
                      args.expt_dir, stations)
    print(f"  {n} 站处理完成")

    print(f"[2/4] 准备 IGS 产品...")
    m = prepare_products(args.year, args.doy,
                         args.products_dir, args.expt_dir)
    print(f"  {m} 个产品文件就绪")

    print(f"[3/4] 准备广播星历...")
    ok = prepare_broadcast(args.year, args.doy,
                           args.data_dir, args.expt_dir)
    print(f"  {'成功' if ok else '失败'}")

    if args.gg_dir:
        print(f"[4/4] 链接全局表...")
        link_tables(args.gg_dir, args.expt_dir)
        print(f"  完成")

    print(f"\n预处理完成: {args.year} DOY {args.doy:03d}")


def cmd_parse(args):
    """parse 子命令处理"""
    from .parser import parse_session, export_csv, export_json

    results = parse_session(args.session_dir, args.expt)

    # 打印摘要
    summary = results.get('summary', {})
    ztd = results.get('ztd', [])
    positions = results.get('positions', {})
    baselines = results.get('baselines', [])

    print(f"=== GAMIT Session: {args.session_dir} ===")
    print(f"  ZTD records:  {len(ztd)}")
    print(f"  Stations:     {len(positions)}")
    print(f"  Baselines:    {len(baselines)}")
    if summary.get('nrms'):
        print(f"  nrms:         {summary['nrms']}")
    if summary.get('ambiguity_rate'):
        print(f"  Ambiguity:    {summary['ambiguity_rate']}%")

    # 导出
    if args.output:
        if args.output.endswith('.json'):
            export_json(results, args.output)
        else:
            export_csv(results, args.output)
        print(f"\n  → Exported to {args.output}")


def main():
    """CLI 主入口"""
    parser = argparse.ArgumentParser(
        prog='pygamit-bridge',
        description='PyGAMIT-Bridge: GAMIT/GLOBK 现代数据格式桥接工具包',
    )
    parser.add_argument('--version', action='version', version='0.1.0')
    subparsers = parser.add_subparsers(dest='command', help='子命令')

    # --- download ---
    p_dl = subparsers.add_parser('download', help='下载 GNSS 数据和产品')
    p_dl.add_argument('--stations', required=True, help='站点列表(逗号分隔)')
    p_dl.add_argument('--year', type=int, required=True)
    p_dl.add_argument('--start-doy', type=int, default=1)
    p_dl.add_argument('--end-doy', type=int, default=1)
    p_dl.add_argument('--output', default='./data/rinex')
    p_dl.add_argument('--products-output', default='./data/products')
    p_dl.add_argument('--stations-only', action='store_true')
    p_dl.add_argument('--products-only', action='store_true')

    # --- convert ---
    p_cv = subparsers.add_parser('convert', help='RINEX 3 → RINEX 2 转换')
    p_cv.add_argument('--input', '-i', required=True, help='RINEX 3 输入文件')
    p_cv.add_argument('--output', '-o', required=True, help='RINEX 2 输出文件')

    # --- preprocess ---
    p_pp = subparsers.add_parser('preprocess', help='预处理数据用于 GAMIT')
    p_pp.add_argument('--year', type=int, required=True)
    p_pp.add_argument('--doy', type=int, required=True)
    p_pp.add_argument('--data-dir', required=True, help='原始数据目录')
    p_pp.add_argument('--products-dir', default=None, help='产品目录')
    p_pp.add_argument('--expt-dir', required=True, help='GAMIT 实验目录')
    p_pp.add_argument('--stations', default=None, help='站点过滤(逗号分隔)')
    p_pp.add_argument('--gg-dir', default=None, help='GAMIT 安装目录')

    # --- parse ---
    p_ps = subparsers.add_parser('parse', help='解析 GAMIT 输出')
    p_ps.add_argument('--session-dir', required=True, help='会话输出目录')
    p_ps.add_argument('--expt', default='anta', help='实验名前缀')
    p_ps.add_argument('--output', '-o', default=None,
                      help='导出路径 (.csv 或 .json)')

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    {
        'download': cmd_download,
        'convert': cmd_convert,
        'preprocess': cmd_preprocess,
        'parse': cmd_parse,
    }[args.command](args)


if __name__ == '__main__':
    main()
