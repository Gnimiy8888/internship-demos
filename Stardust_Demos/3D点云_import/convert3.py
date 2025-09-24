#解析pose（点云的coordiinate和egohead信息）以及yaml（imageSource里的参数）


# -*- coding: utf-8 -*-
"""
遍历 OSS：
- 扫描 rslidar/*.pcd
- 在 img_*/*.jpg 里找同名帧
- 在 pose/*.txt 找同名帧 → 解析为 coordinate.ego / egoHeading
- 找对应 yaml，解析相机参数写入 imageSources
- 仅当有点云 + 图片 + pose + 至少一个成功相机标定 → 写入 JSONL

pip install oss2 numpy pyyaml
"""
import os
import re
import json
import uuid
import math
import numpy as np
import yaml
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
CALIB_PREFIX = ("")
OUTPUT_JSONL = "frames_with_pose_and_calib.jsonl"
# ========================================

def make_oss_url(key: str) -> str:
    return f"oss://{BUCKET_NAME}/{key}"

def list_all_objects(bucket, prefix: str):
    for obj in oss2.ObjectIterator(bucket, prefix=prefix):
        if obj.key.endswith('/'):
            continue
        yield obj.key

# ========== Pose ==========
def rotmat_to_quat(R: np.ndarray):
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
    q = np.array([x,y,z,w])
    q /= np.linalg.norm(q)
    return dict(x=float(q[0]), y=float(q[1]), z=float(q[2]), w=float(q[3]))

def parse_pose_file(bucket, key: str):
    txt = bucket.get_object(key).read().decode("utf-8", errors="ignore")
    vals = [float(x) for x in re.split(r"[,\s]+", txt.strip()) if x]
    if len(vals) >= 17:
        vals = vals[1:17]
    else:
        vals = vals[:16]
    M = np.array(vals, dtype=float).reshape(4,4)
    t = M[:3,3]; R = M[:3,:3]
    return dict(x=float(t[0]), y=float(t[1]), z=float(t[2])), rotmat_to_quat(R)

def build_pose_index(bucket, prefix: str):
    idx = {}
    for key in list_all_objects(bucket, prefix):
        fid = os.path.splitext(os.path.basename(key))[0]
        try:
            ego, quat = parse_pose_file(bucket, key)
            idx[fid] = (ego, quat)
        except: pass
    return idx

# ========== 图片 ==========
def build_image_index(bucket, base_prefix: str):
    idx = defaultdict(list)
    for key in list_all_objects(bucket, base_prefix):
        rest = key[len(base_prefix):]
        if not rest.startswith("img_") or not rest.lower().endswith(".jpg"):
            continue
        parts = rest.split("/",1)
        if len(parts)<2: continue
        folder = parts[0]; fname = os.path.basename(key)
        fid,_ = os.path.splitext(fname)
        idx[fid].append((folder,key))
    return idx

# ========== 相机标定 ==========
def _clean_opencv_yaml(text: str) -> str:
    """去掉 OpenCV YAML 头和自定义 tag，方便 safe_load 解析。"""
    # 去掉文件头 %YAML:1.0 和 '---'
    text = re.sub(r'^\s*%YAML[:\s]*\d+(?:\.\d+)?\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*---\s*', '', text, flags=re.MULTILINE)
    # 去掉 OpenCV 自定义类型 !!opencv-matrix
    text = re.sub(r'!!opencv-matrix', '', text)
    return text

def parse_camera_yaml(bucket, cam_name: str, is_fisheye: bool):
    """
    从 OSS 读取并解析相机 yaml，返回 (camera_dict, width, height)
    * 支持 OpenCV YAML: camera_matrix/distortion_coefficients/r_mat/t_vec 等
    * 自动清理 !!opencv-matrix 和 %YAML:1.0 头
    """
    if is_fisheye:
        yml_key = CALIB_PREFIX + "fisheye/" + f"{cam_name}.yaml"
    else:
        yml_key = CALIB_PREFIX + f"{cam_name}.yaml"

    try:
        raw = bucket.get_object(yml_key).read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"[缺失] 相机 {cam_name} 未找到文件：{yml_key}")
        raise

    cleaned = _clean_opencv_yaml(raw)
    try:
        yml = yaml.safe_load(cleaned)
    except Exception as e:
        print(f"[解析失败] 相机 {cam_name} 文件 {yml_key}: {e}")
        raise

    # 必要字段
    try:
        width  = int(yml["image_width"])
        height = int(yml["image_height"])
        K = yml["camera_matrix"]["data"]
        fx, fy, cx, cy = float(K[0]), float(K[4]), float(K[2]), float(K[5])
        dist = [float(v) for v in yml["distortion_coefficients"]["data"]]
    except Exception as e:
        print(f"[缺字段] 相机 {cam_name} 基础参数缺失：{e}")
        raise

    # 类型/畸变
    if is_fisheye or str(yml.get("distortion_model","")).lower() == "fisheye":
        cam_type = "Fisheye"
        k1 = dist[0] if len(dist) > 0 else None
        k2 = dist[1] if len(dist) > 1 else None
        k3 = dist[2] if len(dist) > 2 else None
        k4 = dist[3] if len(dist) > 3 else None
        radial = dict(k1=k1, k2=k2, k3=k3, k4=k4, k5=0.0, k6=0.0)
        tangential = dict(p1=0.0, p2=0.0)
    else:
        cam_type = "PinHole"
        # OpenCV 标准： [k1, k2, p1, p2, k3]
        if len(dist) < 5:
            print(f"[缺字段] 相机 {cam_name} pinhole 畸变系数不足 5 个：{dist}")
            raise ValueError("pinhole distortion length < 5")
        radial = dict(k1=dist[0], k2=dist[1], k3=dist[4], k4=0.0, k5=0.0, k6=0.0)
        tangential = dict(p1=dist[2], p2=dist[3])

    # 外参：位置 + 姿态
    try:
        tv = [float(v) for v in yml["t_vec"]["data"][:3]]
        position = dict(x=tv[0], y=tv[1], z=tv[2])
    except Exception as e:
        print(f"[缺字段] 相机 {cam_name} t_vec 缺失：{e}")
        raise

    heading = None
    try:
        if "r_mat" in yml and "data" in yml["r_mat"]:
            rm = np.array([float(v) for v in yml["r_mat"]["data"][:9]], dtype=float).reshape(3,3)
            heading = rotmat_to_quat(rm)
        elif "r_vec" in yml and "data" in yml["r_vec"]:
            # 也可以用 Rodrigues→R 再转 quat；你已有 rodrigues_to_R 的话可引入使用
            rv = np.array([float(v) for v in yml["r_vec"]["data"][:3]], dtype=float)
            theta = np.linalg.norm(rv)
            if theta < 1e-12:
                R = np.eye(3)
            else:
                r = rv / theta
                K = np.array([[0,-r[2], r[1]],
                              [r[2], 0,-r[0]],
                              [-r[1],r[0], 0]], dtype=float)
                R = np.eye(3) + math.sin(theta)*K + (1-math.cos(theta))*(K@K)
            heading = rotmat_to_quat(R)
        else:
            print(f"[缺字段] 相机 {cam_name} 缺少 r_mat / r_vec")
            raise ValueError("missing rotation")
    except Exception as e:
        print(f"[解析失败] 相机 {cam_name} 旋转解析：{e}")
        raise

    camera = dict(
        type=cam_type,
        intrinsic=dict(fx=fx, fy=fy, cx=cx, cy=cy),
        radial=radial,
        tangential=tangential,
        skew=float(yml.get("skew", 0.0)),
        position=position,
        heading=heading
    )
    return camera, width, height

def normalize_cam_name(folder: str):
    return re.sub(r"^img_","",folder)

# ========== 主流程 ==========
def main():
    auth=oss2.Auth(ACCESS_KEY_ID,ACCESS_KEY_SECRET)
    bucket=oss2.Bucket(auth,ENDPOINT,BUCKET_NAME)

    pcd_keys=[k for k in list_all_objects(bucket,LIDAR_PREFIX) if k.lower().endswith(".pcd")]
    pcd_keys.sort()
    print("点云数量:",len(pcd_keys))

    img_index=build_image_index(bucket,BASE_PREFIX)
    print("图片帧数:",len(img_index))

    pose_index=build_pose_index(bucket,POSE_PREFIX)
    print("Pose帧数:",len(pose_index))

    n=0
    with open(OUTPUT_JSONL,"w",encoding="utf-8") as fout:
        for pcd in pcd_keys:
            fid=os.path.splitext(os.path.basename(pcd))[0]
            if fid not in img_index or fid not in pose_index: continue
            ego,quat=pose_index[fid]
            image_sources=[]
            for folder,img_key in img_index[fid]:
                cam_name=normalize_cam_name(folder)
                is_fisheye=cam_name.endswith("fisheye")
                try:
                    cam,width,height=parse_camera_yaml(bucket,cam_name,is_fisheye)
                except: continue
                image_sources.append({
                    "url": make_oss_url(img_key),
                    "name": cam_name,
                    "height": height,
                    "width": width,
                    "camera": cam
                })
            if not image_sources: continue
            record={
                "attachmentType":"POINTCLOUD_SEQUENCE",
                "attachment":[{
                    "url": make_oss_url(pcd),
                    "coordinate":{"ego":ego,"egoHeading":quat},
                    "imageSources": image_sources
                }],
                "metadata":{"uniqueIdentifier":str(uuid.uuid4())}
            }
            fout.write(json.dumps(record,ensure_ascii=False)+"\n"); n+=1
    print(f"✅ 完成：写入 {OUTPUT_JSONL}（{n} 行）")

if __name__=="__main__":
    main()
