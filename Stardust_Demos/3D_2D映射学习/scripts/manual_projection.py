#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
手动投影验证3D到2D是否准确
- 读取 K、dist（支持 calib_out/params.yaml 或 .npz）
- 从 extrinsics_out/extrinsics.csv 读入指定图片的 rvec/tvec
- 生成一批测试 3D 点（平面角点、平面中心、离平面点），或从 --points 读取自定义点
- 手动投影（可开关畸变） vs cv2.projectPoints，对比 RMS/Max
- 可视化：原图上画出手算(圆点-洋红) 与 OpenCV(叉号-青色)

用法示例（在 scripts/ 下）：
  python manual_project_test.py --img ../data/IMG2025xxxx.jpg --nx 8 --ny 6 --square 1.0 \
    --params calib_out/params.yaml --extr extrinsics_out/extrinsics.csv --subpix

  忽略畸变（no-dist）
  python manual_project_test.py --img ../data/IMG2025xxxx.jpg --nx 8 --ny 6 \
    --params calib_out/params.yaml --extr extrinsics_out/extrinsics.csv --no-dist

  用自定义 3D 点文件（每行: X Y Z）
  python manual_project_test.py --img ../data/IMG2025xxxx.jpg --points ../data/points.txt \
    --params calib_out/params.yaml --extr extrinsics_out/extrinsics.csv
"""
import os, csv, argparse
import numpy as np
import cv2

# ---------- IO ----------
def read_params(params_path: str):
    ext = os.path.splitext(params_path)[1].lower()
    if ext in [".yaml", ".yml"]:
        fs = cv2.FileStorage(params_path, cv2.FILE_STORAGE_READ)
        if not fs.isOpened():
            raise FileNotFoundError(params_path)
        K = fs.getNode("camera_matrix").mat()
        dist = fs.getNode("distortion_coefficients").mat()
        fs.release()
    elif ext == ".npz":
        D = np.load(params_path, allow_pickle=True)
        K, dist = D["K"], D["dist"]
    else:
        raise ValueError(f"Unsupported params file: {params_path}")
    return K.astype(np.float64), dist.astype(np.float64)

def read_extrinsics(extr_csv: str, img_path: str):
    base = os.path.basename(img_path)
    with open(extr_csv, newline="") as f:
        r = csv.reader(f)
        header = next(r, None)
        for row in r:
            if not row: continue
            if os.path.basename(row[0]) == base:
                rvec = np.array(row[1:4], dtype=float).reshape(3,1)
                tvec = np.array(row[4:7], dtype=float).reshape(3,1)
                return rvec, tvec
    raise FileNotFoundError(f"在 {extr_csv} 中找不到该图片的外参：{base}")

def read_points_file(points_path: str):
    pts = []
    with open(points_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"): continue
            xs = line.replace(",", " ").split()
            assert len(xs) >= 3, f"行格式应为: X Y Z；得到: {line}"
            pts.append([float(xs[0]), float(xs[1]), float(xs[2])])
    return np.array(pts, dtype=np.float64)

# ---------- 点生成 ----------
def gen_plane_corners(nx, ny, square):
    objp = np.zeros((nx*ny, 3), np.float64)
    objp[:, :2] = np.mgrid[0:nx, 0:ny].T.reshape(-1,2) * float(square)
    return objp  # Z=0

def gen_plane_centers(nx, ny, square):
    # 每个格子中心（不含最外一圈边缘，因此 (nx-1)*(ny-1) 个）
    xs, ys = np.mgrid[0:nx-1, 0:ny-1]
    centers = np.stack([(xs+0.5)*square, (ys+0.5)*square, np.zeros_like(xs, dtype=float)], axis=-1)
    return centers.reshape(-1,3).astype(np.float64)

def gen_off_plane_points(nx, ny, square, heights=(0.5, 1.0)):
    # 在几处格子中心上方抬高 Z（单位与 square 一致）
    seeds = [(1,1), (nx//2-1, ny//2-1), (nx-3, ny-3)]
    pts = []
    for (i,j) in seeds:
        cx, cy = (i+0.5)*square, (j+0.5)*square
        for h in heights:
            pts.append([cx, cy, h*square])
    return np.array(pts, dtype=np.float64)

# ---------- 手动投影 ----------
def manual_project(Pw, K, rvec, tvec, dist=None):
    """
    Pw: (N,3) 世界点；K: 3x3；rvec/tvec: 3x1；dist: None 或 (k1,k2,p1,p2,k3[,k4,k5,k6])
    return: (N,2) 像素坐标
    """
    R, _ = cv2.Rodrigues(rvec)
    Pw = Pw.T  # (3,N)
    Pc = R @ Pw + tvec  # (3,N)
    X, Y, Z = Pc[0], Pc[1], Pc[2]
    x = (X/Z).astype(np.float64)
    y = (Y/Z).astype(np.float64)

    if dist is not None and dist.size > 0:
        d = dist.ravel().astype(np.float64)
        k1 = d[0] if d.size>0 else 0.0
        k2 = d[1] if d.size>1 else 0.0
        p1 = d[2] if d.size>2 else 0.0
        p2 = d[3] if d.size>3 else 0.0
        k3 = d[4] if d.size>4 else 0.0
        k4 = d[5] if d.size>5 else 0.0
        k5 = d[6] if d.size>6 else 0.0
        k6 = d[7] if d.size>7 else 0.0

        r2 = x*x + y*y
        r4 = r2*r2
        r6 = r4*r2
        r8 = r4*r4
        r10 = r8*r2
        r12 = r6*r6
        radial = 1.0 + k1*r2 + k2*r4 + k3*r6 + k4*r8 + k5*r10 + k6*r12
        x_dist = x*radial + 2*p1*x*y + p2*(r2 + 2*x*x)
        y_dist = y*radial + p1*(r2 + 2*y*y) + 2*p2*x*y
        x, y = x_dist, y_dist  # overwrite with distorted coords

    fx, fy = K[0,0], K[1,1]
    cx, cy = K[0,2], K[1,2]
    u = fx*x + cx
    v = fy*y + cy
    return np.stack([u, v], axis=1)

# ---------- 主流程 ----------
def main():
    ap = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument("--img", required=True, help="单张图片路径（用于匹配外参 & 可视化）")
    ap.add_argument("--params", default="calib_out/params.yaml", help="K/dist 文件（.yaml 或 .npz）")
    ap.add_argument("--extr", default="extrinsics_out/extrinsics.csv", help="外参 CSV（由 solve_extrinsics*.py 生成）")
    ap.add_argument("--nx", type=int, help="棋盘内角点列数（若未提供 --points 时用于生成平面点）")
    ap.add_argument("--ny", type=int, help="棋盘内角点行数")
    ap.add_argument("--square", type=float, default=1.0, help="单格边长（屏幕=1.0；打印=毫米）")
    ap.add_argument("--points", help="自定义 3D 点文件，每行: X Y Z")
    ap.add_argument("--no-dist", action="store_true", help="忽略畸变（distCoeffs=None）")
    ap.add_argument("--outdir", default="manual_proj_out", help="输出目录")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    # 读参数 & 外参
    K, dist = read_params(args.params)
    dist_use = None if args.no_dist else dist
    rvec, tvec = read_extrinsics(args.extr, args.img)

    # 生成/读取 3D 点
    if args.points:
        Pw = read_points_file(args.points)
    else:
        assert args.nx and args.ny, "未提供 --points，则必须提供 --nx --ny --square"
        pw_list = []
        pw_list.append(gen_plane_corners(args.nx, args.ny, args.square))
        pw_list.append(gen_plane_centers(args.nx, args.ny, args.square))
        pw_list.append(gen_off_plane_points(args.nx, args.ny, args.square, heights=(0.5, 1.0)))
        Pw = np.concatenate(pw_list, axis=0)  # (N,3)

    # 手动投影
    uv_manual = manual_project(Pw, K, rvec, tvec, dist=None if args.no_dist else dist)

    # OpenCV 投影
    uv_cv, _ = cv2.projectPoints(Pw.astype(np.float32), rvec, tvec, K, None if args.no_dist else dist_use)
    uv_cv = uv_cv.reshape(-1,2)

    # 误差
    diff = uv_manual - uv_cv
    per_pt = np.linalg.norm(diff, axis=1)
    rms = float(np.sqrt((per_pt**2).mean()))
    mxe = float(per_pt.max())
    print(f"手算 vs cv2.projectPoints → RMS={rms:.6f}px  Max={mxe:.6f}px  (N={len(Pw)})")

    # 可视化
    img = cv2.imread(args.img)
    vis = img.copy()
    for (um, vm), (uc, vc) in zip(uv_manual, uv_cv):
        # 手算：洋红色圆点
        if 0 <= int(um) < vis.shape[1] and 0 <= int(vm) < vis.shape[0]:
            cv2.circle(vis, (int(round(um)), int(round(vm))), 3, (255, 0, 255), -1)
        # OpenCV：青色叉号
        if 0 <= int(uc) < vis.shape[1] and 0 <= int(vc) < vis.shape[0]:
            cv2.drawMarker(vis, (int(round(uc)), int(round(vc))), (255, 255, 0),
                           markerType=cv2.MARKER_TILTED_CROSS, markerSize=10, thickness=1)

    base = os.path.splitext(os.path.basename(args.img))[0]
    out_img = os.path.join(args.outdir, f"{base}_manual_vs_cv.jpg")
    out_csv = os.path.join(args.outdir, f"{base}_uv.csv")
    cv2.imwrite(out_img, vis)

    # 保存数值
    import csv as _csv
    with open(out_csv, "w", newline="") as f:
        w = _csv.writer(f)
        w.writerow(["idx","X","Y","Z","u_manual","v_manual","u_cv","v_cv","abs_err_px"])
        for i, (pw, umv, ucv, e) in enumerate(zip(Pw, uv_manual, uv_cv, per_pt)):
            w.writerow([i, pw[0], pw[1], pw[2], umv[0], umv[1], ucv[0], ucv[1], e])

    print(f"✅ 输出：\n- 叠图：{out_img}\n- 坐标：{out_csv}")
    if args.no_dist:
        print("（当前为 NO-DIST：未应用畸变模型）")
    else:
        print("（当前为 WITH-DIST：已应用畸变模型）")

if __name__ == "__main__":
    main()
