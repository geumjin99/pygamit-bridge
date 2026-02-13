#!/usr/bin/env python3
"""
process_day.py — PyGAMIT-Bridge 使用示例

演示如何使用 PyGAMIT-Bridge 工具包完成单日 GNSS 数据处理的
全部预处理和结果解析步骤。

用法:
    python3 examples/process_day.py --year 2025 --doy 1 \
        --stations mcm4,auck,syog,cas1 \
        --data-dir ./data/rinex \
        --products-dir ./data/products \
        --expt-dir ./gamit/expt/2025001
"""

import argparse
import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pygamit_bridge.preprocessor import (
    prepare_rinex, prepare_products, prepare_broadcast
)
from pygamit_bridge.batch_fallback import write_batch_file
from pygamit_bridge.parser import parse_session, export_csv, export_json


def main():
    parser = argparse.ArgumentParser(description='PyGAMIT-Bridge 单日处理示例')
    parser.add_argument('--year', type=int, required=True)
    parser.add_argument('--doy', type=int, required=True)
    parser.add_argument('--stations', required=True, help='站点列表(逗号分隔)')
    parser.add_argument('--data-dir', required=True, help='RINEX 数据目录')
    parser.add_argument('--products-dir', required=True, help='产品目录')
    parser.add_argument('--expt-dir', required=True, help='实验目录')
    parser.add_argument('--expt', default='anta', help='实验名')
    args = parser.parse_args()

    stations = args.stations.split(',')
    doy_str = f"{args.doy:03d}"

    print("=" * 60)
    print(f"PyGAMIT-Bridge: 预处理 {args.year} DOY {doy_str}")
    print(f"站点: {', '.join(s.upper() for s in stations)}")
    print("=" * 60)

    # Step 1: RINEX 预处理
    print("\n[Step 1/4] RINEX 数据预处理...")
    n = prepare_rinex(args.year, args.doy, args.data_dir,
                      args.expt_dir, stations)
    print(f"  → {n} 站 RINEX 处理完成")

    if n < 2:
        print("[错误] 站点数不足，无法进行差分处理")
        sys.exit(1)

    # Step 2: IGS 产品
    print("\n[Step 2/4] IGS 产品准备...")
    m = prepare_products(args.year, args.doy,
                         args.products_dir, args.expt_dir)
    print(f"  → {m} 个产品文件就绪")

    # Step 3: 广播星历
    print("\n[Step 3/4] 广播星历...")
    ok = prepare_broadcast(args.year, args.doy,
                           args.data_dir, args.expt_dir)
    print(f"  → {'成功' if ok else '失败（可能需要手动下载）'}")

    # Step 4: 生成 batch 回退文件
    print("\n[Step 4/4] 生成 makex batch 回退文件...")
    batch_path = write_batch_file(
        args.expt, args.year, doy_str,
        output_dir=args.expt_dir,
        rinex_dir=args.expt_dir
    )
    if batch_path:
        print(f"  → {batch_path}")
    else:
        print("  → 未生成（目录中无 RINEX 文件）")

    print("\n" + "=" * 60)
    print("预处理完成！接下来可运行:")
    print(f"  sh_gamit -d {args.year} {args.doy} -expt {args.expt}")
    print()
    print("处理完成后，使用以下命令解析结果:")
    print(f"  pygamit-bridge parse --session-dir {args.expt_dir} -o results.json")
    print("=" * 60)


if __name__ == '__main__':
    main()
