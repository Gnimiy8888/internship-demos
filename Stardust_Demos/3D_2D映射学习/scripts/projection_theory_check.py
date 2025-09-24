# 目的：验证“世界点 →（外参）→ 相机坐标 →（投影+内参）→ 像素点”的整条链路是清楚可用的。
# 做法：准备一组已知的 3D 世界点 Pw、给一个近似的内参 K 和外参 (rvec,tvec)，调用 cv2.projectPoints() 得到像素坐标 (u,v)。

# 注意点：
# 单位一致：rvec和tvec 的单位和Pw的单位必须一致（上面都用“米”），内参的单位都是像素。
# 坐标朝向：OpenCV 默认相机前方是 +Z；要保证你的tvec, rvec让世界点落在 Zc>0 否则投影会乱。
# 主点不等于几何中心：真实相机里u0,v0往往偏离中心几十像素，后续用真实照片时这会带来明显偏移

import cv2, numpy as np

# --- 内参 K ---
W, H = 1920, 1080   # 假设成像的图像宽高，单位像素
fx = fy = 1200.0    # 假设焦距，单位像素
u0, v0 = W/2, H/2   # 假设光心在图像中心
K = np.array([[fx, 0,  u0],     #3D转2D的内参矩阵，归一化平面到像素平面
              [ 0, fy, v0],
              [ 0,  0,  1]], dtype=np.float64)
dist = np.zeros(5)  # 先不考虑畸变

# --- 世界点 Pw（单位：米）---
Pw = np.array([[0.0, 0.0, 0.0],     #给一个 10cm×10cm的正方形（单位 m）
               [0.1, 0.0, 0.0],
               [0.1, 0.1, 0.0],
               [0.0, 0.1, 0.0]], dtype=np.float64)

# --- 外参（世界→相机）---
rvec = np.array([0.0, 0.0, 0.0], dtype=np.float64)          # 无旋转
tvec = np.array([[0.0], [0.0], [0.5]], dtype=np.float64)    # 物体在前方0.5m，单位和Pw一致

# --- 投影 ---
uv, _ = cv2.projectPoints(Pw, rvec, tvec, K, dist)  
#返回的第一个是imagePoints（像素坐标），形状通常是 (N, 1, 2)，所以在后面print的时候用reshape(-1, 2) 变成更好用的 (N, 2)。
# 第二个是 jacobian（雅可比矩阵），一般用不到，所以用 _ 接住。

# print(uv)
print(uv.reshape(-1, 2))
