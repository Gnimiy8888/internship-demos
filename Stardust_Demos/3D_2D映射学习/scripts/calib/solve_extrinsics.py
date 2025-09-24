#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量/单张棋盘外参求解 + 三轴可视化
- 读取 K/dist（支持 calib_out/params.yaml 或 params.npz）
- 对 --path 指定的单张图片、目录或通配符进行处理
- 每张图片：findChessboardCorners(+亚像素) -> solvePnP -> 画三轴 -> 存CSV

用法示例（在 scripts/ 下）：
# 屏幕棋盘（无物理尺度，square=1.0）
python solve_extrinsics.py --path ../data --nx 8 --ny 6 --params calib_out/params.yaml --subpix

# 指定通配符，只跑几张
python solve_extrinsics.py --path "../data/IMG202509*.jpg" --nx 8 --ny 6 --params calib_out/params.yaml

# 打印棋盘（每格24mm），这样 tvec 单位=毫米；轴长=3格
python solve_extrinsics.py --path ../data --nx 8 --ny 6 --square 24.0 --axes 3 --params calib_out/params.yaml

# 想先不考虑畸变（不考虑calib_out/params.yaml里的畸变参数）
python olve_extrinsics.py --img ../data --nx 8 --ny 6 --params calib_out/params.yaml --subpix --no-dist
"""

import os, glob, argparse, csv
import numpy as np
import cv2

def read_params(params_path: str):
    ext = os.path.splitext(params_path)[1].lower()
    if ext == ".yaml" or ext == ".yml":
        fs = cv2.FileStorage(params_path, cv2.FILE_STORAGE_READ)
        if not fs.isOpened():
            raise FileNotFoundError(params_path)
        K = fs.getNode("camera_matrix").mat()
        dist = fs.getNode("distortion_coefficients").mat()
        fs.release()
    elif ext == ".npz":
        D = np.load(params_path, allow_pickle=True)
        K = D["K"]
        dist = D["dist"]
    else:
        raise ValueError(f"Unsupported params file: {params_path}")
    return K.astype(np.float64), dist.astype(np.float64)

def build_obj_points(nx, ny, square):
    objp = np.zeros((nx*ny, 3), np.float32)
    objp[:, :2] = np.mgrid[0:nx, 0:ny].T.reshape(-1, 2) * square  # Z=0
    return objp

def collect_images(path_arg: str):
    if os.path.isdir(path_arg):
        patterns = ["*.jpg","*.jpeg","*.png","*.bmp","*.tif","*.tiff","*.webp"]
        paths = []
        for p in patterns:
            paths += glob.glob(os.path.join(path_arg, p))
        return sorted(paths)
    else:
        # 可能是文件或通配符
        found = glob.glob(path_arg)
        if found:
            return sorted(found)
        # 当作单个文件
        return [path_arg]

def solve_one(img_path, nx, ny, square, K, dist, outdir, subpix=True, try_swap=False, axes_len_mult=3.0):
    img = cv2.imread(img_path)
    if img is None:
        return False, f"无法读取：{img_path}", None, None, None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    flags = cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE
    ret, corners = cv2.findChessboardCorners(gray, (nx, ny), flags)

    # 如果不成功且允许尝试交换 nx/ny
    swapped = False
    if (not ret) and try_swap:
        ret, corners = cv2.findChessboardCorners(gray, (ny, nx), flags)
        if ret:
            nx, ny = ny, nx
            swapped = True

    if not ret:
        base = os.path.splitext(os.path.basename(img_path))[0]
        cv2.imwrite(os.path.join(outdir, f"{base}_no_corners.jpg"), img)
        return False, "未检测到角点", None, None, None

    if subpix:
        corners = cv2.cornerSubPix(
            gray, corners, (11,11), (-1,-1),
            (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 1e-3)
        )

    objp = build_obj_points(nx, ny, square)

    # 平面目标优选 IPPE，失败再退回 ITERATIVE
    ok, rvec, tvec = cv2.solvePnP(objp, corners, K, dist, flags=cv2.SOLVEPNP_IPPE)
    if not ok:
        ok, rvec, tvec = cv2.solvePnP(objp, corners, K, dist, flags=cv2.SOLVEPNP_ITERATIVE)
    if not ok:
        return False, "solvePnP 失败", None, None, None

    # 计算该图重投影误差（均值/RMS/最大）
    proj, _ = cv2.projectPoints(objp, rvec, tvec, K, dist)
    e = np.linalg.norm(proj.reshape(-1,2) - corners.reshape(-1,2), axis=1)
    err_mean, err_rms, err_max = float(e.mean()), float(np.sqrt((e**2).mean())), float(e.max())

    # 画三轴
    axis_len = float(axes_len_mult) * float(square)
    cv2.drawFrameAxes(img, K, dist, rvec, tvec, axis_len)  # 红X 绿Y 蓝Z

    # 角点可视化（便于回看）
    vis = img.copy()
    cv2.drawChessboardCorners(vis, (nx, ny), corners, True)

    base = os.path.splitext(os.path.basename(img_path))[0]
    os.makedirs(outdir, exist_ok=True)
    out_img = os.path.join(outdir, f"{base}_axes.jpg")
    cv2.imwrite(out_img, vis)

    msg = f"OK  rms={err_rms:.3f}px  mean={err_mean:.3f}px  max={err_max:.3f}px" + (" [swapped nx/ny]" if swapped else "")
    return True, msg, rvec.reshape(3), tvec.reshape(3), out_img

def main():
    ap = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument("--path", required=True, help="图片路径/目录/通配符")
    ap.add_argument("--nx", type=int, required=True, help="内角点列数（横向）")
    ap.add_argument("--ny", type=int, required=True, help="内角点行数（纵向）")
    ap.add_argument("--square", type=float, default=1.0, help="单格边长；屏幕=1.0，打印则填毫米")
    ap.add_argument("--params", default="calib_out/params.yaml", help="标定参数文件（.yaml 或 .npz）")
    ap.add_argument("--outdir", default="extrinsics_out", help="输出目录")
    ap.add_argument("--subpix", action="store_true", help="亚像素角点优化")
    ap.add_argument("--try-swap", action="store_true", help="如果 (nx,ny) 未检出则尝试 (ny,nx)")
    ap.add_argument("--axes", type=float, default=3.0, help="坐标轴长度 = axes * square")
    ap.add_argument("--no-dist", action="store_true", help="Ignore lens distortion (treat distCoeffs=None)")
    args = ap.parse_args()

    K, dist = read_params(args.params)
    dist_use = None if args.no_dist else dist

    imgs = collect_images(args.path)
    if not imgs:
        print("❌ 未找到任何图片：", args.path)
        return

    os.makedirs(args.outdir, exist_ok=True)
    csv_path = os.path.join(args.outdir, "extrinsics.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["filename","rvec_x","rvec_y","rvec_z","tvec_x","tvec_y","tvec_z","reproj_rms_px","out_image"])
        for p in imgs:
            ok, msg, rvec, tvec, out_img = solve_one(
                p, args.nx, args.ny, args.square, K, dist_use,
                outdir=args.outdir, subpix=args.subpix,
                try_swap=args.try_swap, axes_len_mult=args.axes
            )
            if ok:
                # 为了把 rms 一并写入 CSV，再次计算一下
                img = cv2.imread(p); gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                ret, corners = cv2.findChessboardCorners(gray, (args.nx, args.ny),
                        cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE)
                if not ret and args.try_swap:
                    ret, corners = cv2.findChessboardCorners(gray, (args.ny, args.nx),
                        cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE)
                if args.subpix and ret:
                    corners = cv2.cornerSubPix(gray, corners, (11,11), (-1,-1),
                        (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 1e-3))
                objp = build_obj_points(args.nx, args.ny, args.square)
                proj, _ = cv2.projectPoints(objp, rvec.reshape(3,1), tvec.reshape(3,1), K, dist_use)
                e = np.linalg.norm(proj.reshape(-1,2) - corners.reshape(-1,2), axis=1)
                rms = float(np.sqrt((e**2).mean()))
                print(f"[{os.path.basename(p)}] {msg}")
                w.writerow([p, *rvec.tolist(), *tvec.tolist(), rms, out_img])
            else:
                print(f"[{os.path.basename(p)}] FAIL: {msg}")
                w.writerow([p, "", "", "", "", "", "", "", ""])
    print(f"\n✅ 完成。结果：\n- 叠轴图片：{args.outdir}/*_axes.jpg\n- 外参CSV：{csv_path}\n- 注意：tvec 的单位与 --square 一致。")
if __name__ == "__main__":
    main()
