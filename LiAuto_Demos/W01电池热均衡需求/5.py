import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from olap_tools import olap_query

#思路：
# （1）拉平信号
# 目的： 在每个数据时段，同步给出RESSThermalBalSts、CTM_Vlv1ModeAct、CTM_Vlv2ModeAct，可以直接对整行做筛选判断。
# 考虑多加一列“val_start_time”以便后续时刻定位

# （2）筛出三信号均满足条件的行，并提取时间
# 只需在“拉平后”大表查出满足条件（比如1,0,3组合）的行，记录下对应val_start_time

# （3）用这些时间点去查电池温与水温值
# 以第2步拿到的（vin, dt, val_start_time）作为键，从ods表中分别获取RESSMaxTempByComp 和 CTM_WtrSnsr1T
# 区间覆盖查找：在val_start_time ≤ val_start_time ≤ val_end_time的区间内查找

# （4）计算差值，分桶统计
# 做差值（T1-T2），用CASE WHEN分桶统计频次

sql = '''
-- 拉平信号并找出满足条件（1,0,3信号组合）的行，记录下对应val_start_time
with signal_flat as (
    SELECT
        t.dt,
        t.vin,
        t.val_start_time,
        t.RESSThermalBalSts,
        t.CTM_Vlv1ModeAct,
        t.CTM_Vlv2ModeAct
    FROM (
        SELECT
            dt,
            vin,
            val_start_time,
            MAX(IF(sig_name = 'RESSThermalBalSts', sig_val, NULL)) AS RESSThermalBalSts,
            MAX(IF(sig_name = 'CTM_Vlv1ModeAct', sig_val, NULL)) AS CTM_Vlv1ModeAct,
            MAX(IF(sig_name = 'CTM_Vlv2ModeAct', sig_val, NULL)) AS CTM_Vlv2ModeAct
        FROM (
            SELECT
                w.dt,
                w.vin,
                w.val_start_time,
                w.sig_name,
                w.sig_val
            FROM
                table1 as w
            join
                table2 AS vom
            on
                vom.vin = w.vin
            WHERE
                vom.veh_series_no = 'W01'
                and w.dt BETWEEN '2024-12-01' AND '2025-02-28'
                AND w.sig_name IN ('RESSThermalBalSts', 'CTM_Vlv1ModeAct', 'CTM_Vlv2ModeAct')
        ) raw
        GROUP BY dt, vin, val_start_time
) t
),
-- 填补缺失信号
signal_filled AS (
    SELECT
        dt,
        vin,
        val_start_time,
        LAST_VALUE(RESSThermalBalSts, true) OVER (PARTITION BY dt, vin ORDER BY val_start_time) AS RESSThermalBalSts_filled,
        LAST_VALUE(CTM_Vlv1ModeAct, true) OVER (PARTITION BY dt, vin ORDER BY val_start_time) AS CTM_Vlv1ModeAct_filled,
        LAST_VALUE(CTM_Vlv2ModeAct, true) OVER (PARTITION BY dt, vin ORDER BY val_start_time) AS CTM_Vlv2ModeAct_filled
    FROM signal_flat
),
-- 筛选补齐后满足条件的行
find_val_start_times as (
    SELECT
        dt, vin, val_start_time
    FROM signal_filled
    WHERE
        RESSThermalBalSts_filled = 1
        AND CTM_Vlv1ModeAct_filled = 0
        AND CTM_Vlv2ModeAct_filled = 3
),
-- 以上一步拿到的（vin, dt, val_start_time）作为键，从ods表中分别获取RESSMaxTempByComp 和 CTM_WtrSnsr1T
find_temps as (
    select
        t.val_start_time,
        battery.sig_val as battery_temp,
        water.sig_val as water_temp,
        (battery.sig_val - water.sig_val) as delta_temp
    from
        find_val_start_times as t
    left join
        table3 as battery
    on
        t.vin = battery.vin
        and battery.sig_name = 'RESSMaxTempByComp'
        and battery.val_start_time <= t.val_start_time
        and battery.val_end_time >= t.val_start_time
    left join
        table4 as water
    on
        t.vin = water.vin
        and water.sig_name = 'CTM_WtrSnsr1T'
        and water.val_start_time <= t.val_start_time
        and water.val_end_time >= t.val_start_time
    where
        battery.sig_val is not null
        and water.sig_val is not null
)
-- 分桶统计
SELECT
  T1_T2_range,
  COUNT(*) as frequency,
  ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) || '%' as percentage
FROM (
  SELECT
    delta_temp,
    CASE
      WHEN delta_temp < -10 THEN '<-10'
      WHEN delta_temp >= -10 AND delta_temp < -5 THEN '[-10,-5]'
      WHEN delta_temp >= -5 AND delta_temp < 0 THEN '[-5,0)'
      WHEN delta_temp >= 0 AND delta_temp < 5 THEN '[0,5)'
      WHEN delta_temp >= 5 AND delta_temp < 10 THEN '[5,10)'
      WHEN delta_temp >= 10 AND delta_temp < 15 THEN '[10,15)'
      WHEN delta_temp >= 15 AND delta_temp < 20 THEN '[15,20)'
      WHEN delta_temp >= 20 AND delta_temp < 25 THEN '[20,25)'
      WHEN delta_temp >= 25 AND delta_temp < 30 THEN '[25,30)'
      ELSE '>30'
    END as T1_T2_range
  FROM find_temps
  WHERE delta_temp IS NOT NULL
) as t
GROUP BY T1_T2_range
ORDER BY
  CASE
    WHEN T1_T2_range = '<-10' THEN 0
    WHEN T1_T2_range = '[-10,-5]' THEN 1
    WHEN T1_T2_range = '[-5,0)' THEN 2
    WHEN T1_T2_range = '[0,5)' THEN 3
    WHEN T1_T2_range = '[5,10)' THEN 4
    WHEN T1_T2_range = '[10,15)' THEN 5
    WHEN T1_T2_range = '[15,20)' THEN 6
    WHEN T1_T2_range = '[20,25)' THEN 7
    WHEN T1_T2_range = '[25,30)' THEN 8
    WHEN T1_T2_range = '>30' THEN 9
    ELSE 99
    END;
'''

'''
myResult:
#第一次结果
T1_T2_range frequency   percentage  
[0,5)   2   28.6%  
[10,15) 2   28.6%  
[15,20) 3   42.9%  
#数据这么少，主要问题是要求三个信号在完全一致的val_start_time有（1，0，3)的排列，要求太苛刻。
#解决方法是用LAST_VALUE窗口函数，将null值替换成前一个非null值
#第二次填补null数据后结果
T1_T2_range frequency   percentage  
<-10    13  0.0%    
[-10,-5]    393 0.1%    
[-5,0)  3790    0.9%    
[0,5)   65691   16.0%  
[5,10)  38121   9.3%    
[10,15) 54166   13.2%  
[15,20) 82214   20.1%  
[20,25) 93453   22.8%  
[25,30) 63037   15.4%  
>30 8765    2.1%    

'''