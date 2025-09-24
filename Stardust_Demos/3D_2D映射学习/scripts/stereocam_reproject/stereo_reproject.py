#用双目相机的方法完成2D到3D到点云重建
# 从 params.yaml 读内参 K、畸变 D。
# 读入左右图。
# 用 ORB 特征匹配 + cv2.findEssentialMat → cv2.recoverPose 恢复 R、t。
# 用 cv2.stereoRectify 做极线校正。
# 用 StereoSGBM 算视差图。
# 用 cv2.reprojectImageTo3D 转点云，并保存为 .ply。

import cv2
import numpy as np

# ========= 1. 读取相机参数 =========
fs = cv2.FileStorage("outputs/calib_out/params.yaml", cv2.FILE_STORAGE_READ)
K = fs.getNode("camera_matrix").mat()
D = fs.getNode("distortion_coefficients").mat()
fs.release()

print("K=\n", K)
print("D=\n", D)

# ========= 2. 读取左右图 =========
imgL = cv2.imread("data/stereocam_images/left.jpg")
imgR = cv2.imread("data/stereocam_images/right.jpg")

grayL = cv2.cvtColor(imgL, cv2.COLOR_BGR2GRAY)
grayR = cv2.cvtColor(imgR, cv2.COLOR_BGR2GRAY)

# ========= 3. 特征点匹配 + Essential矩阵 =========
orb = cv2.ORB_create(5000)
kp1, des1 = orb.detectAndCompute(grayL, None)
kp2, des2 = orb.detectAndCompute(grayR, None)

bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
matches = bf.match(des1, des2)
matches = sorted(matches, key=lambda x: x.distance)

pts1 = np.float32([kp1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
pts2 = np.float32([kp2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)

E, _ = cv2.findEssentialMat(pts1, pts2, K, method=cv2.RANSAC, prob=0.999, threshold=1.0)
_, R, t, _ = cv2.recoverPose(E, pts1, pts2, K)

# ========= 4. 缩放 t =========
B = 0.04  # baseline in meters
t = t * (B / np.linalg.norm(t))

print("Recovered R=\n", R)
print("Scaled t=\n", t.T)

# ========= 5. 立体校正 =========
h, w = grayL.shape
R1, R2, P1, P2, Q, roi1, roi2 = cv2.stereoRectify(
    K, D, K, D, (w, h), R, t, flags=0
)

map1x, map1y = cv2.initUndistortRectifyMap(K, D, R1, P1, (w, h), cv2.CV_32FC1)
map2x, map2y = cv2.initUndistortRectifyMap(K, D, R2, P2, (w, h), cv2.CV_32FC1)

rectL = cv2.remap(imgL, map1x, map1y, cv2.INTER_LINEAR)
rectR = cv2.remap(imgR, map2x, map2y, cv2.INTER_LINEAR)

# ========= 6. SGBM 视差 =========
stereo = cv2.StereoSGBM_create(
    minDisparity=0,
    numDisparities=16*8,
    blockSize=5,
    P1=8 * 3 * 5 ** 2,
    P2=32 * 3 * 5 ** 2,
    disp12MaxDiff=1,
    uniquenessRatio=10,
    speckleWindowSize=100,
    speckleRange=32
)

disp = stereo.compute(
    cv2.cvtColor(rectL, cv2.COLOR_BGR2GRAY),
    cv2.cvtColor(rectR, cv2.COLOR_BGR2GRAY)
).astype(np.float32) / 16.0

# 保存可视化
disp_vis = cv2.normalize(disp, None, 0, 255, cv2.NORM_MINMAX)
disp_vis = np.uint8(disp_vis)
cv2.imwrite("outputs/stereocam_out/disparity.png", disp_vis)
np.save("outputs/stereocam_out/disparity.npy", disp)

# ========= 7. 生成点云 =========
points_3D = cv2.reprojectImageTo3D(disp, Q)
mask = disp > 0
out_points = points_3D[mask]
colors = cv2.cvtColor(rectL, cv2.COLOR_BGR2RGB)
out_colors = colors[mask]

def write_ply(filename, verts, colors):
    verts = verts.reshape(-1, 3)
    colors = colors.reshape(-1, 3)
    verts = np.hstack([verts, colors])
    ply_header = '''ply
format ascii 1.0
element vertex %d
property float x
property float y
property float z
property uchar red
property uchar green
property uchar blue
end_header
''' % len(verts)
    with open(filename, 'w') as f:
        f.write(ply_header)
        np.savetxt(f, verts, '%f %f %f %d %d %d')

write_ply("outputs/stereocam_out/pointcloud.ply", out_points, out_colors)
print("✅ 点云保存到 outputs/stereocam_out/pointcloud.ply")
