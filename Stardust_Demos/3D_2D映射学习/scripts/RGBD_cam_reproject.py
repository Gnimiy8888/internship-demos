#用 Open3D 内置数据集下载器，获取一组 TUM 数据集里的 RGB-D 样例（包含 color.jpg + depth.png）
#并反投影成点云，打开 Open3D 可视化窗口展示点

import open3d as o3d
import numpy as np

# 1) 读取 TUM 示例
#调用 Open3D 内置数据集下载器，获取一组 TUM 数据集里的 RGB-D 样例（包含 color.jpg + depth.png）
dataset = o3d.data.SampleTUMRGBDImage()
#分别读取彩色图像和深度图像
color = o3d.io.read_image(dataset.color_path)
depth = o3d.io.read_image(dataset.depth_path)

# 2) 正确的 RGBD 构造：关键是 depth_scale=5000.0
rgbd = o3d.geometry.RGBDImage.create_from_color_and_depth(
    color, depth,
    depth_scale=5000.0,       # TUM: 深度值需要 /5000 才是米
    depth_trunc=3.0,          # 大于 3 米的深度截断（可调）
    convert_rgb_to_intensity=False  # 保留彩色信息，而不是转灰度
)

# 3) 相机内参（用Open3D提供的PrimeSense默认内参，适配TUM示例）
# 如果是你自己的相机标定结果，这里就应该换成你标定得到的 fx, fy, cx, cy
intr = o3d.camera.PinholeCameraIntrinsic(
    o3d.camera.PinholeCameraIntrinsicParameters.PrimeSenseDefault
)

# 4) 反投影成点云
# 背后就是在跑公式:Pc​=Z*(K^−1)*p,对所有像素执行一遍，就得到整张图的点云
pcd = o3d.geometry.PointCloud.create_from_rgbd_image(rgbd, intr)

# 5) 视图坐标系转换（把 Open3D 的相机坐标系转成更直观的显示）
pcd.transform([[1,0,0,0],
               [0,-1,0,0],
               [0,0,-1,0],
               [0,0,0,1]])

# 打印点云是否有点，以及点的数量
print("Has points?", pcd.has_points(), " | #points =", np.asarray(pcd.points).shape[0])

# 打开 Open3D 可视化窗口，展示点云。你可以旋转/缩放观察场景。
o3d.visualization.draw_geometries([pcd], window_name="Open3D")
