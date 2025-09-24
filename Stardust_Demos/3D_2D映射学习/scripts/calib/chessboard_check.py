#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查拍摄的棋盘格角点是否可被 OpenCV 检测到，并保存可视化结果。
- 支持输入文件或文件夹（自动遍历常见图片后缀）
- 需提供棋盘“内角点”尺寸 (nx, ny)，例如 9x6
- 可开启亚像素优化
用法示例：
    多张照片（指定文件夹, ../data代表data文件夹在这个脚本的上一层目录）：
    python chessboard_check.py --path ../data --nx 8 --ny 6 --subpix
    单张照片（指定文件）：
    python chessboard_check.py --path chess.jpg --nx 11 --ny 7 --subpix
"""

import cv2
import os
import sys
import glob
import argparse
import numpy as np

def parse_args():
    ap = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument("--path", required=True, help="图片路径：单张文件或目录")
    ap.add_argument("--nx", type=int, required=True, help="棋盘内角点列数（横向）")
    ap.add_argument("--ny", type=int, required=True, help="棋盘内角点行数（纵向）")
    ap.add_argument("--outdir", default="chess_check_out", help="结果可视化输出目录")
    ap.add_argument("--subpix", action="store_true", help="是否进行亚像素角点优化")
    ap.add_argument("--fast", action="store_true", help="启用 FAST_CHECK（更快但可能漏检）")
    return ap.parse_args()

def collect_images(p):
    exts = ("*.jpg","*.jpeg","*.png","*.bmp","*.tif","*.tiff","*.webp")
    if os.path.isdir(p):
        imgs = []
        for ext in exts:
            imgs += glob.glob(os.path.join(p, ext))
        imgs = sorted(imgs)
    else:
        imgs = [p]
    return imgs

def main():
    args = parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    imgs = collect_images(args.path)
    if not imgs:
        print("未找到任何图片。请检查路径/后缀。")
        sys.exit(1)

    # OpenCV 棋盘格检测 flags
    flags = cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE
    if args.fast:
        flags |= cv2.CALIB_CB_FAST_CHECK

    # 亚像素参数
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 1e-3)
    win = (11, 11)

    total = 0
    ok_cnt = 0

    print(f"共 {len(imgs)} 张待检测，棋盘内角点尺寸 = ({args.nx}, {args.ny})")
    for fp in imgs:
        total += 1
        img = cv2.imread(fp)
        if img is None:
            print(f"[跳过] 无法读取：{fp}")
            continue

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        ret, corners = cv2.findChessboardCorners(gray, (args.nx, args.ny), flags)
        if ret and args.subpix:
            # 亚像素优化（在灰度图上）
            corners = cv2.cornerSubPix(gray, corners, win, (-1, -1), criteria)

        # 画出检测结果并保存
        vis = img.copy()
        cv2.drawChessboardCorners(vis, (args.nx, args.ny), corners, ret)
        base = os.path.splitext(os.path.basename(fp))[0]
        out_fp = os.path.join(args.outdir, f"{base}_corners.jpg")
        cv2.imwrite(out_fp, vis)

        if ret:
            ok_cnt += 1
            print(f"[OK]  检测到角点：{fp}  → 输出：{out_fp}")
        else:
            print(f"[FAIL] 未检测到角点：{fp}  → 输出：{out_fp}")

    print(f"\n完成：{ok_cnt}/{total} 张检测到角点。结果已保存到：{args.outdir}")

if __name__ == "__main__":
    main()
