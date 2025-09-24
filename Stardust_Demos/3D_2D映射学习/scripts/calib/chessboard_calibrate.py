#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量棋盘标定：读取文件夹内多张棋盘图，估计相机内参K与畸变dist，并导出每张图的外参(rvec,tvec)。
输出：
- calib_out/params.npz  （K、dist、image_size、rvecs、tvecs、RMS）
- calib_out/params.yaml （便于人读/其他程序用）
- calib_out/xxx_corners.jpg （角点可视化）
- 控制台打印整体 RMS 和每张图的重投影误差 （标定好内参和畸变后，把棋盘3D点投影回去，和实际检测到的2D角点比一比，算出的平均误差。
单位是像素。误差越小越好：0.2~0.5 px 通常算很不错，1 px 也能接受。
每张图的误差：同样的逻辑，但分图统计。可以看出哪张图质量差（模糊/反光/角点检测错误）。

用法示例（在 scripts/ 目录中）：
    python chessboard_calibrate.py --path ../data --nx 8 --ny 6 --square 1.0 --subpix --outdir your_output_folder
    说明：脚本所在上一级data/目录下有多张棋盘照片，棋盘内角点8x6，每格24mm，启用亚像素优化
    如果是屏幕棋盘：没有真实物理尺度，--square 用默认 1.0。这样 tvec 的单位就是“格子单位”。
    如果是打印棋盘：比如 A4，格子边长 24 mm，那么运行时加 --square 24.0。这样 tvec 就是毫米单位，你能得到相机距离棋盘的实际毫米数。
"""

import os, glob, argparse, math
import numpy as np
import cv2

def parse_args():
    ap = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument("--path", required=True, help="图片目录")
    ap.add_argument("--nx", type=int, required=True, help="内角点列数（横向）")
    ap.add_argument("--ny", type=int, required=True, help="内角点行数（纵向）")
    ap.add_argument("--square", type=float, default=1.0, help="每格边长（单位任意；打印用真实毫米，屏幕可取1.0）")
    ap.add_argument("--subpix", action="store_true", help="亚像素优化角点")
    ap.add_argument("--fast", action="store_true", help="CALIB_CB_FAST_CHECK（更快，可能漏检）")
    ap.add_argument("--outdir", default="calib_out", help="输出目录")
    return ap.parse_args()

def collect_images(folder):
    exts = ("*.jpg","*.jpeg","*.png","*.bmp","*.tif","*.tiff","*.webp")
    imgs = []
    for e in exts:
        imgs += glob.glob(os.path.join(folder, e))
    imgs.sort()
    return imgs

def build_object_points(nx, ny, square):
    # Z=0 平面，原点在(0,0)
    objp = np.zeros((nx*ny, 3), np.float32)
    objp[:, :2] = np.mgrid[0:nx, 0:ny].T.reshape(-1, 2) * square
    return objp

def per_view_errors(object_points, image_points, K, dist, rvecs, tvecs):
    errs = []
    for objp, imgp, rvec, tvec in zip(object_points, image_points, rvecs, tvecs):
        proj, _ = cv2.projectPoints(objp, rvec, tvec, K, dist)
        proj = proj.reshape(-1,2)
        e = np.linalg.norm(imgp.reshape(-1,2) - proj, axis=1)  # per-point error
        errs.append({
            "mean": float(e.mean()),
            "rms": float(np.sqrt((e**2).mean())),
            "max": float(e.max())
        })
    return errs

def save_yaml(path, K, dist, img_size, rms):
    fs = cv2.FileStorage(path, cv2.FILE_STORAGE_WRITE)
    fs.write("image_width", int(img_size[0]))
    fs.write("image_height", int(img_size[1]))
    fs.write("camera_matrix", K)
    fs.write("distortion_coefficients", dist)
    fs.write("rms_reprojection_error", float(rms))
    fs.release()

def main():
    args = parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    imgs = collect_images(args.path)
    if not imgs:
        print("❌ 未找到图片，请检查 --path")
        return

    nx, ny = args.nx, args.ny
    objp_template = build_object_points(nx, ny, args.square)

    objpoints = []  # 3D points per image
    imgpoints = []  # 2D points per image
    img_size = None

    flags = cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE
    if args.fast:
        flags |= cv2.CALIB_CB_FAST_CHECK
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 1e-3)

    print(f"共 {len(imgs)} 张候选，棋盘内角点 = ({nx},{ny})，square = {args.square}")
    ok_files = 0
    for fp in imgs:
        img = cv2.imread(fp)
        if img is None:
            print(f"[跳过] 无法读取：{fp}")
            continue
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        if img_size is None:
            img_size = (gray.shape[1], gray.shape[0])  # (w,h)

        ret, corners = cv2.findChessboardCorners(gray, (nx, ny), flags)
        vis = img.copy()
        if ret:
            if args.subpix:
                corners = cv2.cornerSubPix(gray, corners, (11,11), (-1,-1), criteria)
            objpoints.append(objp_template.copy())
            imgpoints.append(corners)

            cv2.drawChessboardCorners(vis, (nx, ny), corners, True)
            ok_files += 1
            print(f"[OK]  {fp}")
        else:
            print(f"[FAIL] {fp}")
        base = os.path.splitext(os.path.basename(fp))[0]
        cv2.imwrite(os.path.join(args.outdir, f"{base}_corners.jpg"), vis)

    if len(objpoints) < 3:
        print(f"\n⚠️ 生效图片过少（{len(objpoints)}），建议≥10张、角度/距离多样再试。")
        return

    # 标定
    print("\n开始标定 ...")
    ret, K, dist, rvecs, tvecs = cv2.calibrateCamera(
        objectPoints=objpoints,
        imagePoints=imgpoints,
        imageSize=img_size,
        cameraMatrix=None,
        distCoeffs=None
    )
    # ret 是整体 RMS（像素）
    print("\n=== 标定结果 ===")
    print(f"Image size: {img_size}")
    print(f"RMS reprojection error: {ret:.4f} px")
    print("K = \n", K)
    print("dist = ", dist.ravel())

    # 每张图误差
    view_errs = per_view_errors(objpoints, imgpoints, K, dist, rvecs, tvecs)
    print("\n每张图重投影误差（px）:")
    for i, (fp, e) in enumerate(zip([os.path.basename(p) for p in imgs], view_errs)):
        print(f"  [{i:02d}] {fp:30s}  mean={e['mean']:.3f}  rms={e['rms']:.3f}  max={e['max']:.3f}")

    # 保存参数
    np.savez(os.path.join(args.outdir, "params.npz"),
             K=K, dist=dist, image_size=np.array(img_size),
             rvecs=np.array(rvecs, dtype=object),
             tvecs=np.array(tvecs, dtype=object),
             rms=ret)
    save_yaml(os.path.join(args.outdir, "params.yaml"), K, dist, img_size, ret)
    print(f"\n✅ 已保存：\n  - {os.path.join(args.outdir, 'params.npz')}\n  - {os.path.join(args.outdir, 'params.yaml')}\n  - 角点可视化：{args.outdir}/*.jpg")

if __name__ == "__main__":
    main()
