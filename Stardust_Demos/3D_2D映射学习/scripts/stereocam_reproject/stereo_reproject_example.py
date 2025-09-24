# -*- coding: utf-8 -*-
"""
Middlebury Stereo 2014 反投影示例
读取:
  - x_im0.png (左图)
  - x_im1.png (右图)
  - x_calib.txt (标定参数: cam0, cam1, doffs, baseline ...)
流程:
  1) 读取并灰度化左右图
  2) 用 SGBM 计算视差 d  (单位: 像素)
  3) 由标定参数计算深度 Z = f * B / (d + doffs)
  4) 反投影为三维点 (X,Y,Z)，颜色来自左图
  5) 保存为 PLY 点云 middlebury_cloud.ply
"""

import re
import cv2
import numpy as np
import open3d as o3d
from pathlib import Path

# ---------- 路径设置（按你的实际目录改） ----------
root = Path("data/stereocam_images")   # 你截图里的路径
left_path  = root / "3_im0.png"
right_path = root / "3_im1.png"
calib_path = root / "3_calib.txt"
out_ply    = Path("outputs/stereocam_out/middlebury_cloud3.ply")

# ---------- 读取 calib.txt 并解析需要的参数 ----------
def parse_calib(calib_file):
    """
    解析 Middlebury 的 calib.txt:
      cam0=[fx 0 cx; 0 fy cy; 0 0 1]
      cam1=[...]
      doffs=...
      baseline=...
    返回: fx, fy, cx0, cy0, cx1, cy1, doffs, baseline
    """
    txt = Path(calib_file).read_text()
    # 把 cam0 方括号里的 9 个数字提取出来
    def parse_cam(name):
        m = re.search(rf"{name}=\[([^\]]+)\]", txt)
        assert m, f"未找到 {name}"
        nums = list(map(float, re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", m.group(1))))
        assert len(nums) == 9, f"{name} 解析数量不对: {len(nums)}"
        fx, _, cx, _, fy, cy, _, _, _ = nums
        return fx, fy, cx, cy

    fx0, fy0, cx0, cy0 = parse_cam("cam0")
    fx1, fy1, cx1, cy1 = parse_cam("cam1")

    def parse_scalar(key):
        m = re.search(rf"{key}\s*=\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)", txt)
        assert m, f"未找到 {key}"
        return float(m.group(1))

    doffs    = parse_scalar("doffs")      # disparity offset
    baseline = parse_scalar("baseline")   # 基线(多为毫米)

    return fx0, fy0, cx0, cy0, fx1, fy1, cx1, cy1, doffs, baseline

fx0, fy0, cx0, cy0, fx1, fy1, cx1, cy1, doffs, baseline = parse_calib(calib_path)
print(f"fx0={fx0:.3f}, fy0={fy0:.3f}, cx0={cx0:.3f}, cy0={cy0:.3f}")
print(f"doffs={doffs:.3f}, baseline={baseline:.3f} (单位由数据集定义, 常见为 mm)")

# ---------- 读取左右图 ----------
left  = cv2.imread(str(left_path), cv2.IMREAD_COLOR)
right = cv2.imread(str(right_path), cv2.IMREAD_COLOR)
assert left is not None and right is not None, "读取图片失败，请检查路径"

h, w = left.shape[:2]
left_gray  = cv2.cvtColor(left,  cv2.COLOR_BGR2GRAY)
right_gray = cv2.cvtColor(right, cv2.COLOR_BGR2GRAY)

# ---------- 计算视差 (SGBM) ----------
# 注: SGBM 输出的视差乘了 16，可用 /16.0 还原为“像素”单位
# 下面参数是常用的初始值，可按数据分辨率再微调
min_disp = 0
num_disp = 256   # 必须是16的倍数，覆盖可能的视差范围
block_size = 5

stereo = cv2.StereoSGBM_create(
    minDisparity=min_disp,
    numDisparities=num_disp,
    blockSize=block_size,
    P1=8 * 3 * block_size ** 2,
    P2=32 * 3 * block_size ** 2,
    mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY
)

disp = stereo.compute(left_gray, right_gray).astype(np.float32) / 16.0  # 像素
# 将无效区域置为 NaN，便于后续掩码
disp[disp <= 0] = np.nan

# ---------- 由视差计算深度 Z 并反投影到 3D ----------
# 采用 cam0 的 fx 作为 f，主点 (cx0, cy0)
f = fx0
B = baseline  # 注意单位！若 baseline 为 mm，则 Z 结果为 mm

# Middlebury 定义的 disparity 常带 doffs: disp = x_left - x_right + doffs
# SGBM 计算得到的是 x_left - x_right，因此这里使用 (disp + doffs)
disp_eff = disp + doffs

# 防止除零
valid = ~np.isnan(disp) & (disp_eff > 1e-6)

# 构建每个像素的坐标网格
u_coords, v_coords = np.meshgrid(np.arange(w), np.arange(h))

# 计算 Z（深度），X、Y（相机坐标系）
Z = np.full((h, w), np.nan, dtype=np.float32)
Z[valid] = (f * B) / disp_eff[valid]   # 单位与 B 相同（多为 mm）

X = np.full((h, w), np.nan, dtype=np.float32)
Y = np.full((h, w), np.nan, dtype=np.float32)
X[valid] = (u_coords[valid] - cx0) * Z[valid] / f
Y[valid] = (v_coords[valid] - cy0) * Z[valid] / f

# ---------- 组装点云并保存为 .ply ----------
# 颜色使用左图（BGR->RGB）
colors = cv2.cvtColor(left, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0

pts = np.stack([X, Y, Z], axis=-1).reshape(-1, 3)
col = colors.reshape(-1, 3)

mask = np.isfinite(pts).all(axis=1)
pts_valid = pts[mask]
col_valid = col[mask]

print(f"有效点数: {pts_valid.shape[0]} / {h*w}")

pcd = o3d.geometry.PointCloud()
pcd.points = o3d.utility.Vector3dVector(pts_valid.astype(np.float64))
pcd.colors = o3d.utility.Vector3dVector(col_valid.astype(np.float64))

o3d.io.write_point_cloud(str(out_ply), pcd, write_ascii=False)
print(f"已保存点云: {out_ply.resolve()}")

# 可视化（可选）
o3d.visualization.draw_geometries([pcd])
