import os
import json
import pandas as pd
import unicodedata

# 基准目录：脚本所在目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

JSON_DIR   = os.path.join(BASE_DIR, "3554")                 # ✅ 相对 3554/
ORIG_XLSX  = os.path.join(BASE_DIR, "babytree原数据.xlsx")   # ✅ 相对 Excel
OUT_XLSX   = os.path.join(BASE_DIR, "sheet1.xlsx")          # ✅ 输出到项目根
SHEET_NAME = "Sheet1"
TARGET_COUNT = 20

# （可选）运行前做存在性检查，报更友好的错
for p, kind in [(JSON_DIR, "JSON 目录"), (ORIG_XLSX, "原始 Excel")]:
    if not os.path.exists(p):
        raise FileNotFoundError(f"{kind} 不存在：{p}")


def norm(s):
    """轻量归一化：None->'', 全角转半角，去首尾空白，连续空白压成1个空格。"""
    if s is None:
        return ""
    s = str(s)
    s = unicodedata.normalize("NFKC", s)      # 全角->半角/兼容规范化
    s = " ".join(s.split())                   # 标准化空白
    return s.strip()

def collect_json_questions(json_dir):
    """遍历 json，提取 result->annotations[1]->slotsChildren[0]->slot.text"""
    questions = []
    files = [f for f in os.listdir(json_dir) if f.lower().endswith(".json")]
    files.sort()
    for name in files:
        path = os.path.join(json_dir, name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                j = json.load(f)
            ann = (j.get("result") or {}).get("annotations") or []
            # 严格按要求取第2个元素（下标1），并从固定路径拿文本
            if len(ann) > 1:
                sc = (ann[1].get("slotsChildren") or [])
                if sc:
                    slot = (sc[0].get("slot") or {})
                    q = slot.get("text")
                    if q:
                        questions.append(norm(q))
        except Exception as e:
            # 安静跳过坏文件
            pass
    return questions

def main():
    # 1) 收集 JSON 中的“问题”集合（归一化）
    json_questions = collect_json_questions(JSON_DIR)
    json_q_set = set(json_questions)

    if not json_q_set:
        print("未从 JSON 中提取到任何问题。请检查 /3554/ 下的文件与路径。")
        return

    # 2) 读取原始 Excel（取第一列为“问题”）
    df = pd.read_excel(ORIG_XLSX, sheet_name=0)  # 默认第一个表
    if df.shape[1] == 0:
        print("原始 Excel 没有任何列。")
        return

    first_col_name = df.columns[0]
    # 归一化后另存一列用于匹配
    df["_q_norm_"] = df[first_col_name].map(norm)

    # 3) 过滤出匹配到 JSON 问题的行，保持原顺序
    filtered = df[df["_q_norm_"].isin(json_q_set)].copy()

    # 只取前 20 条
    filtered_20 = filtered.head(TARGET_COUNT).drop(columns=["_q_norm_"])

    # 4) 写出到 /sheet1.xlsx 的 Sheet1
    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as writer:
        filtered_20.to_excel(writer, sheet_name=SHEET_NAME, index=False)

    print(f"完成：从原始 {len(df)} 行中匹配出 {len(filtered)} 行，已写入前 {len(filtered_20)} 行到 {OUT_XLSX} 的 {SHEET_NAME}。")

if __name__ == "__main__":
    main()
