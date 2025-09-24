-- 工单表里被存在offline表里的零件在result表里被判定成异常的数量

-- 思路：“工单中trace_code在offline12月7DG范围内的零件”，这些零件去result看is_anomaly=1能匹配上多少

SELECT COUNT(DISTINCT o.product_serial_num) AS anomaly_part_cnt
FROM table1 as a
JOIN table2 as o
  ON a.trace_code = o.product_serial_num      
JOIN table3 as r
  ON o.product_serial_num = r.product_serial_num    
WHERE o.supplier_code = '7DG'
  AND o.dt >= '2024-12-01'
  AND o.dt < '2025-01-01'
  AND r.is_anomaly = 1

  -- 结果：4