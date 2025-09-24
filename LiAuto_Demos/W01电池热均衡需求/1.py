import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from olap_tools import olap_query #this is a Li Auto internal module

#针对W01系列
#找出所有CTMVlv2Posn非0的结束时刻(从1变成0),t1
#找出所有CTMVlv2Posn开始时刻(从0变成1),t2
    #给每条信号打一个顺序编号，按vin和时间排序，和下一条信息做对比，找出1-0 和 0-1的跳变点
    #拼接两个表（vin，t1，t2），只保留1-0 和0-1 图案的行
#统计的电池最高温RESSMaxTempByComp在t1和t2时的值
#计算温度下降量
#将这些下降量放入桶中，绘制柱形图



sql = '''
-- 找到所有车型为w01的CTM_Vlv2Posn信号
    with signal_change_points as (
        select
            w.vin,
            w.sig_val,
            w.val_start_time,
            w.val_end_time,
            row_number() over (partition by w.vin order by w.val_start_time) as rn
        from
            table1
        join
            table2 as vom
        on
            w.vin = vom.vin
            and w.dt = vom.dt
        where
            w.sig_name = 'CTM_Vlv2Posn'
            and vom.veh_series_no = 'W01'
            and w.dt >= '2024-12-01'
            and w.dt <= '2025-02-28'
),
-- 找到所有电池加热结束（sig_val从非0到0的时间）,把这些row提取出来
    signal_end_points as (
        select
            prev.vin,
            prev.sig_val as prev_val,
            nextsig.sig_val as next_val,
            prev.val_end_time as prev_end_time
        from
            signal_change_points prev
        join
            signal_change_points nextsig
        on
            prev.vin = nextsig.vin
            and nextsig.rn = prev.rn +1
        where
            prev.sig_val != 0 and nextsig.sig_val = 0
    ),

-- 找到所有电池加热开始（sig_val从0到非0的时间）,把这些row提取出来
    signal_start_points as (
        select
            prev.vin,
            prev.sig_val as prev_val,
            nextsig.sig_val as next_val,
            nextsig.val_start_time as next_start_time
            from
                signal_change_points prev
            join
                signal_change_points nextsig
            on
                prev.vin = nextsig.vin
                and nextsig.rn = prev.rn +1
            where
                prev.sig_val = 0 and nextsig.sig_val != 0
    ),
-- 把电池的加热和结束时间提取出来，让每个‘下次开始加热时间’跟离他最近的‘上次加热结束时间’配对
    signal_pairs as (
        select
            signal_end_points.vin,
            signal_end_points.prev_end_time,
            min(signal_start_points.next_start_time) as next_start_time
        from
            signal_end_points
        join
            signal_start_points
        on
          signal_end_points.vin = signal_start_points.vin
          and signal_start_points.next_start_time > signal_end_points.prev_end_time
        group by
            signal_end_points.vin,
            signal_end_points.prev_end_time
    ),
-- 用之前找到的‘下次开始加热时间’和‘上次加热结束时间’，找到他们相对应时间的电池最高温
    find_temperature as (
        select
            p.vin,
            p.prev_end_time,
            p.next_start_time,
            prev.sig_val as prev_end_temp,
            next.sig_val as next_start_temp,
            (prev.sig_val - next.sig_val) as delta_temp
        from
            signal_pairs as p
        left join
            table3  as prev
        on
            p.vin = prev.vin
            and prev.sig_name = 'RESSMaxTempByComp'
            and prev.val_start_time <= p.prev_end_time
            and prev.val_end_time >= p.prev_end_time
        left join
            table4  as next
        on
            p.vin = next.vin
            and next.sig_name = 'RESSMaxTempByComp'
            and next.val_start_time <= p.next_start_time
            and next.val_end_time >= p.next_start_time
        where
            prev.sig_val is not null
            and next.sig_val is not null
    )
-- 将结果分桶统计
select
    diff_range, -- 统计每个‘降了多少温’区间的频次
    count(*) as freq,
FROM (
    SELECT
        vin,
        delta_temp,
        CASE
            WHEN delta_temp <=  0 THEN '≤0'
            WHEN delta_temp <=  2 THEN '(0,2]'
            WHEN delta_temp <=  4 THEN '(2,4]'
            WHEN delta_temp <=  6 THEN '(4,6]'
            WHEN delta_temp <=  8 THEN '(6,8]'
            WHEN delta_temp <= 10 THEN '(8,10]'
            WHEN delta_temp <= 12 THEN '(10,12]'
            WHEN delta_temp <= 14 THEN '(12,14]'
            WHEN delta_temp <= 16 THEN '(14,16]'
            WHEN delta_temp <= 18 THEN '(16,18]'
            WHEN delta_temp <= 20 THEN '(18,20]'
            ELSE '>20'
        END AS diff_range
    FROM find_temperature
    WHERE delta_temp IS NOT NULL
) as t -- 此处是拉了一个子查询，找到每辆车的降温量delta_temp对应哪个区间。表头是vin,delta_temp 和 diff_range
GROUP BY diff_range -- 方便统计每个区间的频次
ORDER BY
    CASE diff_range
        WHEN '≤0' THEN 0
        WHEN '(0,2]' THEN 1
        WHEN '(2,4]' THEN 2
        WHEN '(4,6]' THEN 3
        WHEN '(6,8]' THEN 4
        WHEN '(8,10]' THEN 5
        WHEN '(10,12]' THEN 6
        WHEN '(12,14]' THEN 7
        WHEN '(14,16]' THEN 8
        WHEN '(16,18]' THEN 9
        WHEN '(18,20]' THEN 10
        ELSE 11
    END;
'''

#plotting bar chart:
# 数据(from myResut)
diff_range = ['≤0', '(0,2]', '(2,4]', '(4,6]', '(6,8]', '(8,10]', '(10,12]', '(12,14]', '(14,16]', '(16,18]']
freq = [258932, 67226, 45579, 35917, 32182, 29344, 24415, 23623, 24433, 26257]

# 绘图
plt.figure(figsize=(12, 6))
bars = plt.bar(diff_range, freq, color='cornflowerblue')

# 添加数值标签
for bar in bars:
    plt.text(bar.get_x() + bar.get_width()/2, bar.get_height(), f'{bar.get_height():,}',
             ha='center', va='bottom', fontsize=10, rotation=90)

plt.title('降温区间分布（freq）', fontsize=16)
plt.xlabel('区间 diff_range', fontsize=12)
plt.ylabel('频次 freq', fontsize=12)
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()

