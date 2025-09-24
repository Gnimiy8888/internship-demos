import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from olap_tools import olap_query


#当'RESSThermalBalSts'信号从1变为0时（信号结束时间,val_end_time），
#找到两个水阀此刻的工作模式。字段是：
#sig_name = 'CTM_Vlv1ModeAct'
#sig_name = 'CTM_Vlv2ModeAct'
#需筛出特定车型W01

sql_heatBalance = '''
with thermal_event as (
    -- 找出每次热平衡开始和结束时间,以及对应的车vin
    select
        sig.vin
        sig.val_start_time as heatBalance_start_time
        sig.val_end_time as heatBalance_end_time
    from
        table1 as sig
    left join
        table2 as vom
    on
        sig.vin = vom.vin
        and sig.dt = vom.dt
    where
        sig.sig_name = 'RESSThermalBalSts'
        and sig.sig_val = 1
        and vom.veh_series_no = 'W01'
),

-- 从以上的表出发，找sig_name为两个阀名时相对应的开始和结束时间
-- 如果'RESSThermalBalSts'=1的heatBalance_end_time (一次热平衡的结束时间)落在阀一或阀二的开始和结束时间之内
-- 则可以获得该次热平衡结束时两个阀的状态
thermal_event_with_valves as (
    select
        te.vin,
        te.heatBalance_start_time,
        te.heatBalance_end_time,
        v1.sig_val as valve1_mode,
        v2.sig_val valve2_mode
    from
        thermal_event as te
    join
        table3 as v1
    on te.vin=v1.vin
        and v1.sig_name = 'CTM_Vlv1ModeAct'
        and te.heatBalance_end_time > v1.val_start_time
        and te.heatBalance_end_time < v1.val_end_time
    join
        table4 as v2
    on te.vin=v2.vin
        and v2.sig_name = 'CTM_Vlv2ModeAct'
        and te.heatBalance_end_time > v2.val_start_time
        and te.heatBalance_end_time < v2.val_end_time
)

-- 统计每个阀门状态的组合出现的频数
select
    CONCAT('CTM_Vlv1ModeAct=', valve1_mode, ' 且CTM_Vlv2ModeAct=', valve2_mode) AS valve_mode_combination,
    COUNT(*) AS freq
FROM thermal_event_with_valves limit
GROUP BY valve1_mode, valve2_mode
ORDER BY valve1_mode, valve2_mode;
'''

myResult = '''
valve_mode_combination  freq    
CTM_Vlv1ModeAct=0.0 且CTM_Vlv2ModeAct=0.0    17  
CTM_Vlv1ModeAct=0.0 且CTM_Vlv2ModeAct=2.0    13  
CTM_Vlv1ModeAct=0.0 且CTM_Vlv2ModeAct=3.0    35984  
CTM_Vlv1ModeAct=0.0 且CTM_Vlv2ModeAct=7.0    5  
CTM_Vlv1ModeAct=1.0 且CTM_Vlv2ModeAct=0.0    3  
CTM_Vlv1ModeAct=1.0 且CTM_Vlv2ModeAct=1.0    3  
CTM_Vlv1ModeAct=1.0 且CTM_Vlv2ModeAct=2.0    1  
CTM_Vlv1ModeAct=1.0 且CTM_Vlv2ModeAct=3.0    14675  
CTM_Vlv1ModeAct=1.0 且CTM_Vlv2ModeAct=7.0    45  
CTM_Vlv1ModeAct=2.0 且CTM_Vlv2ModeAct=0.0    9586    
'''
