#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Minimal demo: undistort a single chessboard image by searching a simple k1.
- Input: --img path/to/image.png (required)
- Output: undistort_side_by_side.png (in the same folder as the script is run)

How to use:
# 基本用法
python undistort_demo.py --img your_chessboard_image.png
# 可选：调整搜索范围或步数
python undistort_demo.py --img your.png --k1min -0.8 --k1max 0.4 --steps 31 --outdir your_output_path

Notes:
- Intrinsics K are guessed from image size (for demo only).
- Only k1 is searched (k2=p1=p2=k3=0). For rigorous work, calibrate with cv2.calibrateCamera.

自动检测棋盘角点（尝试常见网格大小：9x6、8x6、7x6…）。
根据图像大小猜测一个K（演示足够；严谨请用标定获得K与dist）。
仅搜索 k1（k2=p1=p2=k3=0）来最小化“直线度”RMS（行/列角点拟合线的点到线RMS）。
输出并排图 undistort_side_by_side.png（左原图，右去畸变最佳k1），并在控制台打印原图/去畸变的RMS与最佳 k1。
"""
import argparse
import os
import cv2
import numpy as np

def find_chess_corners(gray):
    # Try a few common inner-corner grid sizes
    for (nx, ny) in [(9,6), (8,6), (7,6), (9,7), (8,5)]:
        ret, corners = cv2.findChessboardCorners(
            gray, (nx, ny),
            cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE
        )
        if ret:
            corners = cv2.cornerSubPix(
                gray, corners, (11,11), (-1,-1),
                (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 1e-3)
            )
            return (nx, ny), corners.reshape(-1, 2)
    return None, None

def straightness_rms(corners, nx, ny):
    """RMS point-to-line distance over chessboard rows & cols."""
    if corners is None:
        return float('inf')
    pts = corners.reshape(ny, nx, 2)
    dists = []

    # Rows
    for r in range(ny):
        row = pts[r, :, :]
        if row.shape[0] < 2: continue
        x = row[:,0]; y = row[:,1]
        A = np.stack([x, np.ones_like(x)], axis=1)
        m, b = np.linalg.lstsq(A, y, rcond=None)[0]
        a, bb, c = m, -1.0, b
        denom = (a*a + bb*bb)**0.5
        if denom < 1e-6: continue
        dist = np.abs(a*x + bb*y + c) / denom
        dists.append(dist)

    # Cols
    for cidx in range(nx):
        col = pts[:, cidx, :]
        if col.shape[0] < 2: continue
        x = col[:,0]; y = col[:,1]
        A = np.stack([y, np.ones_like(y)], axis=1)
        m, b = np.linalg.lstsq(A, x, rcond=None)[0]
        a, bb, c = -1.0, m, b
        denom = (a*a + bb*bb)**0.5
        if denom < 1e-6: continue
        dist = np.abs(a*x + bb*y + c) / denom
        dists.append(dist)

    if not dists:
        return float('inf')
    all_d = np.concatenate(dists)
    return float(np.sqrt(np.mean(all_d**2)))

def main():
    ap = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument("--img", required=True, help="path to a chessboard image")
    ap.add_argument("--k1min", type=float, default=-0.6, help="min k1 to search")
    ap.add_argument("--k1max", type=float, default=0.6, help="max k1 to search")
    ap.add_argument("--steps", type=int, default=25, help="number of k1 steps")
    args = ap.parse_args()

    gray = cv2.imread(args.img, cv2.IMREAD_GRAYSCALE)
    if gray is None:
        raise FileNotFoundError(args.img)
    h, w = gray.shape[:2]

    # Guess K for demo
    fx = fy = float(max(h, w)) * 0.9
    cx = w / 2.0
    cy = h / 2.0
    K = np.array([[fx, 0,  cx],
                  [0,  fy, cy],
                  [0,   0,  1]], dtype=np.float32)

    grid, corners_orig = find_chess_corners(gray)
    if grid is None:
        print("❌ Failed to detect chessboard corners on the original image. Try another image.")
        return
    nx, ny = grid
    metric_orig = straightness_rms(corners_orig, nx, ny)

    # Grid-search k1
    best = {"k1": None, "metric": float('inf'), "und": None, "corners": None}
    k1_values = np.linspace(args.k1min, args.k1max, max(2, args.steps))
    for k1 in k1_values:
        dist = np.array([k1, 0, 0, 0, 0], dtype=np.float32)  # [k1,k2,p1,p2,k3]
        und = cv2.undistort(gray, K, dist, None, K)
        grid2, corners2 = find_chess_corners(und)
        if grid2 is None or grid2 != (nx, ny):
            continue
        m = straightness_rms(corners2, nx, ny)
        if m < best["metric"]:
            best.update({"k1": float(k1), "metric": float(m), "und": und.copy(), "corners": corners2})

    # Visualize and save
    color_orig = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    cv2.drawChessboardCorners(color_orig, (nx, ny), corners_orig.reshape(-1,1,2), True)

    if best["und"] is None:
        print("✅ Chessboard detected, but no better undistortion found with the current search range.")
        print(f"Grid (nx,ny)={nx,ny}  |  Original straightness RMS={metric_orig:.4f}px")
        side = np.hstack([color_orig, color_orig])
    else:
        vis_und = cv2.cvtColor(best["und"], cv2.COLOR_GRAY2BGR)
        cv2.drawChessboardCorners(vis_und, (nx, ny), best["corners"].reshape(-1,1,2), True)
        side = np.hstack([color_orig, vis_und])
        print("✅ Success.")
        print(f"Grid (nx,ny)={nx,ny}")
        print(f"Original straightness RMS: {metric_orig:.4f} px")
        print(f"Best k1: {best['k1']:.4f}")
        print(f"Undistorted straightness RMS: {best['metric']:.4f} px")

    out = "undistort_side_by_side.png"
    cv2.imwrite(out, side)
    print(f"Saved: {out}")
    print("Left: Original (with detected corners) | Right: Undistorted (best k1)")

if __name__ == "__main__":
    main()