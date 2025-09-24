import oss2
import json
import uuid
import os

# ==== 配置信息 ====
ACCESS_KEY_ID = ""
ACCESS_KEY_SECRET = ""
ENDPOINT = ""
BUCKET_NAME = ""

# 基础路径
BASE_PREFIX = ""
LIDAR_PREFIX = BASE_PREFIX + ""
IMG_PREFIX = BASE_PREFIX   # 各个 img_xxx 文件夹都在这里

# ==== 初始化 bucket ====
auth = oss2.Auth(ACCESS_KEY_ID, ACCESS_KEY_SECRET)
bucket = oss2.Bucket(auth, ENDPOINT, BUCKET_NAME)

# ==== 取一个点云文件（测试用）====
pcd_file = None
for obj in oss2.ObjectIterator(bucket, prefix=LIDAR_PREFIX):
    if obj.key.endswith(".pcd"):
        pcd_file = obj.key
        break

if not pcd_file:
    raise FileNotFoundError("未找到点云文件")

pcd_name = os.path.splitext(os.path.basename(pcd_file))[0]   # 去掉后缀，得到帧名

# ==== 匹配同名 JPG 文件 ====
image_sources = []
for obj in oss2.ObjectIterator(bucket, prefix=IMG_PREFIX):
    if obj.key.endswith(".jpg") and pcd_name in os.path.basename(obj.key):
        image_sources.append({
            "url": f"oss://{BUCKET_NAME}/{obj.key}",
            "name": os.path.basename(os.path.dirname(obj.key)),  # 用文件夹名 img_xxx 作为相机标识
            "height": None,   # 先不解析分辨率
            "width": None
        })

# ==== 构造 JSON ====
data = {
    "attachmentType": "POINTCLOUD_SEQUENCE",
    "attachment": [
        {
            "url": f"oss://{BUCKET_NAME}/{pcd_file}",
            "imageSources": image_sources
        }
    ],
    "metadata": {
        "uniqueIdentifier": str(uuid.uuid4())
    }
}

# ==== 保存到文件 ====
with open("one_frame.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("已生成 one_frame.json")
