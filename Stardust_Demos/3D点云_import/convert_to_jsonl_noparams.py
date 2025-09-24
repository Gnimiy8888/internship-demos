# -*- coding: utf-8 -*-
"""
全量遍历：
- 扫描 rslidar/ 下全部 .pcd
- 在 BASE_PREFIX 下所有 img_* 目录里找同名 .jpg
- 若某帧没有任何匹配图片，直接跳过
- 每个点云一行 JSON，写 frames.jsonl

pip install oss2
"""
import os
import json
import uuid
from collections import defaultdict
import oss2

# ======== 基本配置 ========
ACCESS_KEY_ID = ""
ACCESS_KEY_SECRET = ""
ENDPOINT = ""
BUCKET_NAME = ""

BASE_PREFIX = ("")
LIDAR_PREFIX = BASE_PREFIX + ""     # 点云目录
OUTPUT_JSONL = "frames.jsonl"
# ========================================

def make_oss_url(key: str) -> str:
    return f"oss://{BUCKET_NAME}/{key}"

def list_all_objects(bucket, prefix: str):
    """列出 prefix 下所有对象 key（递归）。"""
    for obj in oss2.ObjectIterator(bucket, prefix=prefix):
        # 过滤“目录占位符”
        if obj.key.endswith('/'):
            continue
        yield obj.key

def build_image_index(bucket, base_prefix: str):
    """
    建立 frame_id -> [(folder_name, img_key), ...] 的索引。
    仅收集 base_prefix 下的 img_* 目录中的 .jpg。
    """
    idx = defaultdict(list)
    for key in list_all_objects(bucket, base_prefix):
        # 仅关心 img_*/*.jpg
        if not key.startswith(base_prefix):
            continue
        rest = key[len(base_prefix):]  # 例如 'img_front_120/1748....jpg' 或 'rslidar/xxx.pcd'
        if not rest.startswith("img_"):
            continue
        if not rest.lower().endswith(".jpg"):
            continue

        # 文件夹名：img_front_120
        parts = rest.split('/', 1)
        if len(parts) < 2:
            continue
        folder = parts[0]
        fname = os.path.basename(key)
        frame_id, _ = os.path.splitext(fname)  # 例如 '1748312709.075113'
        idx[frame_id].append((folder, key))
    return idx

def main():
    # 1) 初始化
    auth = oss2.Auth(ACCESS_KEY_ID, ACCESS_KEY_SECRET)
    bucket = oss2.Bucket(auth, ENDPOINT, BUCKET_NAME)

    # 2) 点云列表
    print("扫描点云 …")
    pcd_keys = [k for k in list_all_objects(bucket, LIDAR_PREFIX) if k.lower().endswith(".pcd")]
    pcd_keys.sort()
    print(f"点云数量: {len(pcd_keys)}")

    # 3) 建图像索引
    print("扫描图片并建索引 …")
    img_index = build_image_index(bucket, BASE_PREFIX)
    print(f"存在图片的帧数: {len(img_index)}")

    # 4) 逐帧写 JSONL（无图则跳过）
    n_written = 0
    with open(OUTPUT_JSONL, "w", encoding="utf-8") as fout:
        for pcd_key in pcd_keys:
            frame_id = os.path.splitext(os.path.basename(pcd_key))[0]

            # 匹配到的同名图片
            imgs = img_index.get(frame_id, [])

            # === 关键：无图直接跳过 ===
            if not imgs:
                continue

            image_sources = [
                {
                    "url": make_oss_url(img_key),
                    "name": folder,   # 使用 img_ 目录名作为相机标识
                    "height": None,
                    "width": None
                }
                for folder, img_key in imgs
            ]

            record = {
                "attachmentType": "POINTCLOUD_SEQUENCE",
                "attachment": [
                    {
                        "url": make_oss_url(pcd_key),
                        "imageSources": image_sources
                    }
                ],
                "metadata": {
                    "uniqueIdentifier": str(uuid.uuid4())
                }
            }

            fout.write(json.dumps(record, ensure_ascii=False) + "\n")
            n_written += 1

    print(f"✅ 完成：写入 {OUTPUT_JSONL}（{n_written} 行，只包含有配图的帧）")

if __name__ == "__main__":
    main()
