import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from olap_tools import olap_query

'''需求：（电脑gpt）
1. 找出每个“热均衡”周期的起点（即 RESSThermalBalSts 由0变1的时刻），并记录那一刻的时间、最高温、最低温（即 T1、T2）。
2. 找出每个“热均衡”周期的终点（即 RESSThermalBalSts 由1变0的时刻），并记录那一刻的时间、最高温、最低温（即 T3、T4）。
3. 将每个起点和对应的终点配对（同一个周期内的一对），将起/终数据合并到一行。
4. 计算每个周期的温度变化量：
最高温变化：T1 - T3
最低温变化：T2 - T4
5. 对 T1-T3 和 T2-T4 分别做桶分布统计（比如以1°C为桶，分布每个区间有多少条）。
6. 最终输出两个分布表（最高温变化、最低温变化）。
'''


sql= '''
WITH
-- 只筛选 W01 车型相关的 vin 热均衡周期
balance_events AS (
    SELECT
        t.vin,
        t.val_start_time AS start_time,
        t.val_end_time AS end_time,
        ROW_NUMBER() OVER (PARTITION BY t.vin ORDER BY t.val_start_time) AS rn
    FROM table1 as t
    INNER JOIN table2 as b
        ON t.vin = b.vin
    WHERE t.sig_name = 'RESSThermalBalSts'
      AND t.sig_val = 1
      AND b.veh_series_no = 'W01'
      AND t.dt BETWEEN '2024-12-01' AND '2025-02-28'
),

-- 起点温度 T1/T2
start_temps AS (
    SELECT
        e.vin,
        e.rn,
        MAX(CASE WHEN t.sig_name = 'RESSMaxTempByComp' THEN t.sig_val END) AS T1,
        MAX(CASE WHEN t.sig_name = 'RESSMinTempByComp' THEN t.sig_val END) AS T2
    FROM balance_events e
    LEFT JOIN table3 as t
      ON e.vin = t.vin
     AND t.collect_time_ms / 1000 = e.start_time
     AND t.sig_name IN ('RESSMaxTempByComp', 'RESSMinTempByComp')
    GROUP BY e.vin, e.rn
),

-- 终点温度 T3/T4
end_temps AS (
    SELECT
        e.vin,
        e.rn,
        MAX(CASE WHEN t.sig_name = 'RESSMaxTempByComp' THEN t.sig_val END) AS T3,
        MAX(CASE WHEN t.sig_name = 'RESSMinTempByComp' THEN t.sig_val END) AS T4
    FROM balance_events e
    LEFT JOIN table4 as t
      ON e.vin = t.vin
     AND t.collect_time_ms / 1000 = e.end_time
     AND t.sig_name IN ('RESSMaxTempByComp', 'RESSMinTempByComp')
    GROUP BY e.vin, e.rn
),

balance_temp_change AS (
    SELECT
        s.vin,
        s.rn,
        s.T1, s.T2,
        e.T3, e.T4,
        (s.T1 - e.T3) AS max_temp_delta,
        (s.T2 - e.T4) AS min_temp_delta
    FROM start_temps s
    JOIN end_temps e
      ON s.vin = e.vin AND s.rn = e.rn
)

-- 输出统计分布
SELECT
    'max_temp_delta' AS type,
    CASE
        WHEN max_temp_delta < -10 THEN '<-10'
        WHEN max_temp_delta >= -10 AND max_temp_delta <= -8 THEN '[-10,-8]'
        WHEN max_temp_delta > -8 AND max_temp_delta <= -6 THEN '(-8,-6]'
        WHEN max_temp_delta > -6 AND max_temp_delta <= -4 THEN '(-6,-4]'
        WHEN max_temp_delta > -4 AND max_temp_delta <= -2 THEN '(-4,-2]'
        WHEN max_temp_delta > -2 AND max_temp_delta <= 0 THEN '(-2,0]'
        WHEN max_temp_delta > 0 AND max_temp_delta <= 2 THEN '(0,2]'
        WHEN max_temp_delta > 2 AND max_temp_delta <= 4 THEN '(2,4]'
        WHEN max_temp_delta > 4 AND max_temp_delta <= 6 THEN '(4,6]'
        WHEN max_temp_delta > 6 AND max_temp_delta <= 8 THEN '(6,8]'
        WHEN max_temp_delta > 8 AND max_temp_delta <= 10 THEN '(8,10]'
        WHEN max_temp_delta > 10 AND max_temp_delta <= 12 THEN '(10,12]'
        WHEN max_temp_delta > 12 AND max_temp_delta <= 14 THEN '(12,14]'
        WHEN max_temp_delta > 14 AND max_temp_delta <= 16 THEN '(14,16]'
        WHEN max_temp_delta > 16 AND max_temp_delta <= 18 THEN '(16,18]'
        WHEN max_temp_delta > 18 AND max_temp_delta <= 20 THEN '(18,20]'
        WHEN max_temp_delta > 20 THEN '>20'
    END AS bucket,
    COUNT(*) AS cnt
FROM balance_temp_change
GROUP BY
    CASE
        WHEN max_temp_delta < -10 THEN '<-10'
        WHEN max_temp_delta >= -10 AND max_temp_delta <= -8 THEN '[-10,-8]'
        WHEN max_temp_delta > -8 AND max_temp_delta <= -6 THEN '(-8,-6]'
        WHEN max_temp_delta > -6 AND max_temp_delta <= -4 THEN '(-6,-4]'
        WHEN max_temp_delta > -4 AND max_temp_delta <= -2 THEN '(-4,-2]'
        WHEN max_temp_delta > -2 AND max_temp_delta <= 0 THEN '(-2,0]'
        WHEN max_temp_delta > 0 AND max_temp_delta <= 2 THEN '(0,2]'
        WHEN max_temp_delta > 2 AND max_temp_delta <= 4 THEN '(2,4]'
        WHEN max_temp_delta > 4 AND max_temp_delta <= 6 THEN '(4,6]'
        WHEN max_temp_delta > 6 AND max_temp_delta <= 8 THEN '(6,8]'
        WHEN max_temp_delta > 8 AND max_temp_delta <= 10 THEN '(8,10]'
        WHEN max_temp_delta > 10 AND max_temp_delta <= 12 THEN '(10,12]'
        WHEN max_temp_delta > 12 AND max_temp_delta <= 14 THEN '(12,14]'
        WHEN max_temp_delta > 14 AND max_temp_delta <= 16 THEN '(14,16]'
        WHEN max_temp_delta > 16 AND max_temp_delta <= 18 THEN '(16,18]'
        WHEN max_temp_delta > 18 AND max_temp_delta <= 20 THEN '(18,20]'
        WHEN max_temp_delta > 20 THEN '>20'
    END

UNION ALL

SELECT
    'min_temp_delta' AS type,
    CASE
        WHEN min_temp_delta < -10 THEN '<-10'
        WHEN min_temp_delta >= -10 AND min_temp_delta <= -8 THEN '[-10,-8]'
        WHEN min_temp_delta > -8 AND min_temp_delta <= -6 THEN '(-8,-6]'
        WHEN min_temp_delta > -6 AND min_temp_delta <= -4 THEN '(-6,-4]'
        WHEN min_temp_delta > -4 AND min_temp_delta <= -2 THEN '(-4,-2]'
        WHEN min_temp_delta > -2 AND min_temp_delta <= 0 THEN '(-2,0]'
        WHEN min_temp_delta > 0 AND min_temp_delta <= 2 THEN '(0,2]'
        WHEN min_temp_delta > 2 AND min_temp_delta <= 4 THEN '(2,4]'
        WHEN min_temp_delta > 4 AND min_temp_delta <= 6 THEN '(4,6]'
        WHEN min_temp_delta > 6 AND min_temp_delta <= 8 THEN '(6,8]'
        WHEN min_temp_delta > 8 AND min_temp_delta <= 10 THEN '(8,10]'
        WHEN min_temp_delta > 10 AND min_temp_delta <= 12 THEN '(10,12]'
        WHEN min_temp_delta > 12 AND min_temp_delta <= 14 THEN '(12,14]'
        WHEN min_temp_delta > 14 AND min_temp_delta <= 16 THEN '(14,16]'
        WHEN min_temp_delta > 16 AND min_temp_delta <= 18 THEN '(16,18]'
        WHEN min_temp_delta > 18 AND min_temp_delta <= 20 THEN '(18,20]'
        WHEN min_temp_delta > 20 THEN '>20'
    END AS bucket,
    COUNT(*) AS cnt
FROM balance_temp_change
GROUP BY
    CASE
        WHEN min_temp_delta < -10 THEN '<-10'
        WHEN min_temp_delta >= -10 AND min_temp_delta <= -8 THEN '[-10,-8]'
        WHEN min_temp_delta > -8 AND min_temp_delta <= -6 THEN '(-8,-6]'
        WHEN min_temp_delta > -6 AND min_temp_delta <= -4 THEN '(-6,-4]'
        WHEN min_temp_delta > -4 AND min_temp_delta <= -2 THEN '(-4,-2]'
        WHEN min_temp_delta > -2 AND min_temp_delta <= 0 THEN '(-2,0]'
        WHEN min_temp_delta > 0 AND min_temp_delta <= 2 THEN '(0,2]'
        WHEN min_temp_delta > 2 AND min_temp_delta <= 4 THEN '(2,4]'
        WHEN min_temp_delta > 4 AND min_temp_delta <= 6 THEN '(4,6]'
        WHEN min_temp_delta > 6 AND min_temp_delta <= 8 THEN '(6,8]'
        WHEN min_temp_delta > 8 AND min_temp_delta <= 10 THEN '(8,10]'
        WHEN min_temp_delta > 10 AND min_temp_delta <= 12 THEN '(10,12]'
        WHEN min_temp_delta > 12 AND min_temp_delta <= 14 THEN '(12,14]'
        WHEN min_temp_delta > 14 AND min_temp_delta <= 16 THEN '(14,16]'
        WHEN min_temp_delta > 16 AND min_temp_delta <= 18 THEN '(16,18]'
        WHEN min_temp_delta > 18 AND min_temp_delta <= 20 THEN '(18,20]'
        WHEN min_temp_delta > 20 THEN '>20'
    END
ORDER BY type, bucket;
'''