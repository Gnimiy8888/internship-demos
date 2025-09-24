# -*- coding: utf-8 -*-
"""
遍历 OSS：
- 扫描 rslidar/*.pcd
- 在 img_*/*.jpg 里找同名帧
- 在 pose/*.txt 找同名帧 → 解析为 coordinate.ego / egoHeading
- 仅当有点云 + 图片 + pose 才写入 JSONL

pip install oss2 numpy
"""
import os
import re
import json
import uuid
import math
import numpy as np
from collections import defaultdict
import oss2

# ======== 基本配置 ========
ACCESS_KEY_ID = ""
ACCESS_KEY_SECRET = ""
ENDPOINT = ""
BUCKET_NAME = ""

BASE_PREFIX = ("")
LIDAR_PREFIX = BASE_PREFIX + ""
POSE_PREFIX = BASE_PREFIX + ""
OUTPUT_JSONL = "frames_with_pose.jsonl"
# ========================================

def make_oss_url(key: str) -> str:
    return f"oss://{BUCKET_NAME}/{key}"

def list_all_objects(bucket, prefix: str):
    """列出 prefix 下所有对象 key（递归）。"""
    for obj in oss2.ObjectIterator(bucket, prefix=prefix):
        if obj.key.endswith('/'):
            continue
        yield obj.key

# ========== Pose 解析 ==========
def rotmat_to_quat(R: np.ndarray):
    """旋转矩阵转四元数 (x,y,z,w)"""
    m = R
    t = np.trace(m)
    if t > 0:
        S = math.sqrt(t + 1.0) * 2
        w = 0.25 * S
        x = (m[2,1] - m[1,2]) / S
        y = (m[0,2] - m[2,0]) / S
        z = (m[1,0] - m[0,1]) / S
    else:
        if m[0,0] > m[1,1] and m[0,0] > m[2,2]:
            S = math.sqrt(1.0 + m[0,0] - m[1,1] - m[2,2]) * 2
            w = (m[2,1] - m[1,2]) / S
            x = 0.25 * S
            y = (m[0,1] + m[1,0]) / S
            z = (m[0,2] + m[2,0]) / S
        elif m[1,1] > m[2,2]:
            S = math.sqrt(1.0 + m[1,1] - m[0,0] - m[2,2]) * 2
            w = (m[0,2] - m[2,0]) / S
            x = (m[0,1] + m[1,0]) / S
            y = 0.25 * S
            z = (m[1,2] + m[2,1]) / S
        else:
            S = math.sqrt(1.0 + m[2,2] - m[0,0] - m[1,1]) * 2
            w = (m[1,0] - m[0,1]) / S
            x = (m[0,2] + m[2,0]) / S
            y = (m[1,2] + m[2,1]) / S
            z = 0.25 * S
    q = np.array([x, y, z, w])
    q /= np.linalg.norm(q)
    return dict(x=float(q[0]), y=float(q[1]), z=float(q[2]), w=float(q[3]))

def parse_pose_file(bucket, key: str):
    """读取 pose 文件并解析为 ego, egoHeading"""
    txt = bucket.get_object(key).read().decode("utf-8", errors="ignore")
    tokens = [t for t in re.split(r"[,\s]+", txt.strip()) if t]
    vals = [float(x) for x in tokens]
    if len(vals) >= 17:  # 有时间戳 → 跳过第一个
        vals = vals[1:17]
    else:
        vals = vals[:16]
    M = np.array(vals, dtype=float).reshape(4, 4)
    t = M[:3, 3]
    R = M[:3, :3]
    return dict(x=float(t[0]), y=float(t[1]), z=float(t[2])), rotmat_to_quat(R)

def build_pose_index(bucket, prefix: str):
    """建立 frame_id -> (ego, egoHeading) 索引"""
    idx = {}
    for key in list_all_objects(bucket, prefix):
        frame_id = os.path.splitext(os.path.basename(key))[0]
        try:
            ego, quat = parse_pose_file(bucket, key)
            idx[frame_id] = (ego, quat)
        except Exception:
            pass
    return idx

# ========== 图片索引 ==========
def build_image_index(bucket, base_prefix: str):
    idx = defaultdict(list)
    for key in list_all_objects(bucket, base_prefix):
        rest = key[len(base_prefix):]
        if not rest.startswith("img_") or not rest.lower().endswith(".jpg"):
            continue
        parts = rest.split("/", 1)
        if len(parts) < 2:
            continue
        folder = parts[0]
        fname = os.path.basename(key)
        frame_id, _ = os.path.splitext(fname)
        idx[frame_id].append((folder, key))
    return idx

# ========== 主流程 ==========
def main():
    auth = oss2.Auth(ACCESS_KEY_ID, ACCESS_KEY_SECRET)
    bucket = oss2.Bucket(auth, ENDPOINT, BUCKET_NAME)

    # 点云
    pcd_keys = [k for k in list_all_objects(bucket, LIDAR_PREFIX) if k.lower().endswith(".pcd")]
    pcd_keys.sort()
    print(f"点云数量: {len(pcd_keys)}")

    # 图片
    img_index = build_image_index(bucket, BASE_PREFIX)
    print(f"存在图片的帧数: {len(img_index)}")

    # pose
    pose_index = build_pose_index(bucket, POSE_PREFIX)
    print(f"存在 pose 的帧数: {len(pose_index)}")

    # 输出
    n_written = 0
    with open(OUTPUT_JSONL, "w", encoding="utf-8") as fout:
        for pcd_key in pcd_keys:
            frame_id = os.path.splitext(os.path.basename(pcd_key))[0]
            imgs = img_index.get(frame_id, [])
            if not imgs or frame_id not in pose_index:
                continue

            ego, quat = pose_index[frame_id]

            image_sources = [
                {"url": make_oss_url(img_key), "name": folder, "height": None, "width": None}
                for folder, img_key in imgs
            ]

            record = {
                "attachmentType": "POINTCLOUD_SEQUENCE",
                "attachment": [
                    {
                        "url": make_oss_url(pcd_key),
                        "coordinate": {"ego": ego, "egoHeading": quat},
                        "imageSources": image_sources
                    }
                ],
                "metadata": {"uniqueIdentifier": str(uuid.uuid4())}
            }
            fout.write(json.dumps(record, ensure_ascii=False) + "\n")
            n_written += 1

    print(f"✅ 完成：写入 {OUTPUT_JSONL}（{n_written} 行，均为“有图 + 有 pose”的帧）")

if __name__ == "__main__":
    main()
