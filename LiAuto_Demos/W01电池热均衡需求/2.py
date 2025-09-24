import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from olap_tools import olap_query


#思路(如果无val_end_time)
#跟车辆画像表join，把所需统计时间和车型，和信号为RESSThermalBalSTs的信号筛出来，按时间排序
#给每个行设一个row number，跟这个表本身join，让前表的行n = 后表的行n+1,
  #筛出前信号1且后信号1的前信号val_start_time
  #筛出前信号1且后信号0的前信号val_start_time
#把所有的0-1和1-0的val_start_time按照间隔时间最短配对，要求1-0的发生时间必须大于0-1。算出两个val_start_time的间隔时间
#把间隔时长（RESSThermalBalSTs=1的时长）做分桶统计，算出频次

#思路（有val_end_time)
# 筛选关心的车型、时间范围和sig_name='RESSThermalBalSts'的数据。
# 只保留sig_val=1的行。
# 直接用val_end_time - val_start_time计算持续时长（单位为秒，除以60转分钟）。
# 将持续时长做CASE...WHEN分桶，统计频次分布。


sql = '''
 SELECT
  duration_range,
  COUNT(*) AS freq
FROM (
  SELECT
    w.vin,
    w.val_start_time,
    w.val_end_time,
    (w.val_end_time - w.val_start_time) / 60.0 AS duration_min,
    CASE
      WHEN (w.val_end_time - w.val_start_time) / 60.0 <= 2 THEN '(0,2]'
      WHEN (w.val_end_time - w.val_start_time) / 60.0 <= 4 THEN '(2,4]'
      WHEN (w.val_end_time - w.val_start_time) / 60.0 <= 6 THEN '(4,6]'
      WHEN (w.val_end_time - w.val_start_time) / 60.0 <= 8 THEN '(6,8]'
      WHEN (w.val_end_time - w.val_start_time) / 60.0 <= 10 THEN '(8,10]'
      WHEN (w.val_end_time - w.val_start_time) / 60.0 <= 12 THEN '(10,12]'
      WHEN (w.val_end_time - w.val_start_time) / 60.0 <= 14 THEN '(12,14]'
      WHEN (w.val_end_time - w.val_start_time) / 60.0 <= 16 THEN '(14,16]'
      WHEN (w.val_end_time - w.val_start_time) / 60.0 <= 18 THEN '(16,18]'
      ELSE '>18'
    END AS duration_range
  FROM
    table1 AS w
  JOIN
    table2 AS vom
  ON
    w.vin = vom.vin
    and w.dt = vom.dt
  WHERE
    w.sig_name = 'RESSThermalBalSts'
    AND w.sig_val = 1
    AND w.dt BETWEEN '2024-12-01' AND '2025-02-28'
    AND vom.veh_series_no = 'W01'
    AND w.val_end_time > w.val_start_time
) as t
GROUP BY duration_range
ORDER BY
  CASE duration_range
    WHEN '(0,2]' THEN 1
    WHEN '(2,4]' THEN 2
    WHEN '(4,6]' THEN 3
    WHEN '(6,8]' THEN 4
    WHEN '(8,10]' THEN 5
    WHEN '(10,12]' THEN 6
    WHEN '(12,14]' THEN 7
    WHEN '(14,16]' THEN 8
    WHEN '(16,18]' THEN 9
    WHEN '>18' THEN 10
    ELSE 99
  END;
'''

myresult = '''
duration_range  freq  
(0,2] 186395  
(2,4] 129529  
(4,6] 153700  
(6,8] 147717  
(8,10]  74164
(10,12] 34853
(12,14] 16851
(14,16] 8857  
(16,18] 4903  
>18 9388  
'''