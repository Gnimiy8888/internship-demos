#在公司可以用数智里的下载结果数据下载，直接粘贴到理想的空调国际标准制程临时表里

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from olap_tools import olap_query

with open('query_runable.sql','r',encoding = 'utf-8') as f:
    sql = f.read()
df = olap_query(sql)
print(df)

# 写入Excel
output_path = '空调国际标准制程.xlsx'   # 输出 Excel 文件名
sheet_name = '空调国际标准制程'         # Sheet名称

# 写入 Excel（含表头）
df.to_excel(output_path, sheet_name=sheet_name, index=False)

print("已成功导出到Excel:", output_path)