WITH cleaned_data AS (
    SELECT
        *,
        regexp_extract(product_bar_code, '(LAC-\\d+)', 1) AS product_code
    FROM table1
    WHERE
        dt >= '2025-07-01'
        AND supplier_code = '7CQ'
)

SELECT  distinct
    -- 有'前HVAC总成'和'后HVAC总成'
    trim(product_name) AS product_name,
   
    product_code AS product_code,

    '' AS product_num,
    '空调国际' AS supplier_short_name, -- 待确认
    '空调国际有限公司' AS factory_name, -- 待确认
    '上海工厂' AS base_name, -- 待确认

    -- factory_line只有w02
    factory_line AS line_name,

    '' AS para_line_name_list,
    '' AS part_line_name,

    -- 所有零件的所有测试项都同时进行
    1 AS is_part_first_test,
    1 AS is_part_final_test,
    '' AS sub_part_line_name,

    -- 有'EOL检测'和'气密性检测'
    key_process_code AS process_name,

    -- factory_tester只有w02
    factory_tester AS step_group_name,

    '' AS Para_step_group_name_list,

    -- group_name只有'暖通空调'
    group_name AS group_name,

    test_name AS test_name,
    test_unit AS test_unit,

    -- test_hilim 和 test_lolim 暂无数据
    test_hilim AS test_hilim,
    test_lolim AS test_lolim,
    test_rule AS test_rule,
    test_target AS test_target,

    -- 推断测试数据类型
    CASE
      WHEN test_hilim REGEXP '^[0-9]+$' OR test_lolim REGEXP '^[0-9]+$' THEN 'number'
      ELSE 'not_number'
    END AS test_datatype,

    -- 是否为数值型 SPC 控制规则
    CASE
      WHEN test_hilim REGEXP '^[0-9]+$' OR test_lolim REGEXP '^[0-9]+$' THEN 1
      ELSE 0
    END AS spc_rules,

    0 AS Spc_push_flag,
    1 AS is_final_test,
    '' AS parameter_push_flag,

    '2025-07-01 00:00:00' AS effective_time,
    '' AS expire_time,
    '' AS save_time,

    supplier_code AS supplier_code,

    -- Serial_number按key_process_code先后关系排序(所有key_process_code在同一时间发生,test_time一致)
    1 AS serial_number,

    1 AS is_normalized,
    1 AS is_spc_test,
    1 AS is_traceable_test,

    '' AS fault_tree_id,
    '' AS idtc_cause_id,
    '' AS standard_character_name

FROM cleaned_data

ORDER BY
    product_name, key_process_code
   