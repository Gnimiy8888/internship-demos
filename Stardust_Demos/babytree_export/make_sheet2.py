import os
import json
import pandas as pd
import unicodedata

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_DIR = os.path.join(BASE_DIR, "3554")
SHEET1_XLSX = os.path.join(BASE_DIR, "sheet1.xlsx")  # 根目录下的 sheet1.xlsx
SHEET2_XLSX = os.path.join(BASE_DIR, "sheet2.xlsx")  # 输出

MODEL_MAP = {
    "1": "gpt4",
    "2": "gpt35",
    "3": "ChatGLM_6b_base",
    "4": "ChatGLM2_6B_base",
    "5": "baichuan_13B_base",
    "6": "无最佳答案",
    "7": "7",
    "8": "8",
}

def norm(s):
    """轻量归一化：全角->半角、压空白、去首尾空白，None->''。"""
    if s is None:
        return ""
    s = str(s)
    s = unicodedata.normalize("NFKC", s)
    s = " ".join(s.split())
    return s.strip()

def safe_get(d, path, default=None):
    """按路径安全取值，path 形如 'a.b[1].c[0].d' """
    cur = d
    try:
        for part in path.replace("]", "").split("."):
            if "[" in part:
                key, idx = part.split("[")
                if key:
                    cur = cur.get(key, {})
                cur = cur[int(idx)]
            else:
                cur = cur.get(part)
                if cur is None:
                    return default
        return cur if cur is not None else default
    except Exception:
        return default

def load_json_questions(json_dir):
    """建立 {规范化问题: 对应json对象} 的字典（若重复，保留第一条）。"""
    mapping = {}
    files = [f for f in os.listdir(json_dir) if f.lower().endswith(".json")]
    files.sort()
    for name in files:
        path = os.path.join(json_dir, name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                j = json.load(f)
            q = safe_get(j, "result.annotations[1].slotsChildren[0].slot.text", "")
            qn = norm(q)
            if qn and qn not in mapping:
                mapping[qn] = j
        except Exception:
            pass
    return mapping

def col1_real_question_text(j):
    # 判断值：annotations[1].slotsChildren[0].children[0].input.value
    v = safe_get(j, "result.annotations[1].slotsChildren[0].children[0].input.value", "")
    v_norm = str(v).strip().lower()
    if v_norm == "car":
        # 取 slot.text
        return safe_get(j, "result.annotations[1].slotsChildren[0].slot.text", "")
    else:
        # 取 children[1].input.value
        return safe_get(j, "result.annotations[1].slotsChildren[0].children[1].input.value", "")

def col2_answer_error_text(j):
    # 判断值：annotations[2].slotsChildren[0].children[0].input.value
    v = safe_get(j, "result.annotations[2].slotsChildren[0].children[0].input.value", "")
    v_norm = str(v).strip().lower()
    if v_norm == "car":
        # 取 children[1].input.value
        return safe_get(j, "result.annotations[2].slotsChildren[0].children[1].input.value", "")
    else:
        # 取 slot.text
        return safe_get(j, "result.annotations[2].slotsChildren[0].slot.text", "")

def col3_best_model_and_answer(j):
    # 答案
    text = safe_get(j, "result.annotations[3].slotsChildren[0].slot.text", "")
    # 模型id
    mid = safe_get(j, "result.annotations[3].slotsChildren[0].children[0].input.value", "")
    mid_str = str(mid).strip()
    model = MODEL_MAP.get(mid_str, "错误")
    if not text:
        return ""
    return f"【{model}】：{text}"

def main():
    # 1) 读 sheet1（第一列问题）
    if not os.path.exists(SHEET1_XLSX):
        raise FileNotFoundError(f"未找到 {SHEET1_XLSX}")
    df1 = pd.read_excel(SHEET1_XLSX, sheet_name=0)
    if df1.shape[1] == 0:
        raise ValueError("sheet1.xlsx 没有任何列")
    q_col = df1.columns[0]
    df1["_q_norm_"] = df1[q_col].map(norm)

    # 2) 建立 JSON 问题 → JSON 对象 的映射
    if not os.path.isdir(JSON_DIR):
        raise FileNotFoundError(f"未找到 JSON 目录：{JSON_DIR}")
    q2json = load_json_questions(JSON_DIR)

    # 3) 逐行匹配并生成三列
    out_rows = []
    for _, row in df1.iterrows():
        qn = row["_q_norm_"]
        j = q2json.get(qn)
        if not j:
            # 找不到对应 json，就三列留空
            out_rows.append({"列1_是否真问题": "", "列2_回答是否错误": "", "列3_最佳模型及答案": ""})
            continue
        c1 = col1_real_question_text(j)
        c2 = col2_answer_error_text(j)
        c3 = col3_best_model_and_answer(j)
        out_rows.append({"列1_是否真问题": c1, "列2_回答是否错误": c2, "列3_最佳模型及答案": c3})

    sheet2 = pd.DataFrame(out_rows)

    # 4) 写出 sheet2.xlsx
    sheet2.to_excel(SHEET2_XLSX, sheet_name="Sheet1", index=False)
    print(f"完成：已生成 {SHEET2_XLSX}（{len(sheet2)} 行）")

if __name__ == "__main__":
    main()
