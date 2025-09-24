import open3d as o3d
import numpy as np

# 1. 读取 ply 文件
pcd = o3d.io.read_point_cloud("/Users/stardust/Desktop/3D_2D映射学习/outputs/stereocam_out/pointcloud.ply")   # 换成你的文件路径
print(pcd)

# 2. 打印点云的基本信息
points = np.asarray(pcd.points)
colors = np.asarray(pcd.colors)

print("点数:", points.shape[0])
print("前 5 个点:\n", points[:5])
print("前 5 个颜色:\n", colors[:5])

# 3. 可视化点云
o3d.visualization.draw_geometries([pcd])
