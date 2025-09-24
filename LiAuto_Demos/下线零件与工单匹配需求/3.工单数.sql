-- 工单表里有多少零件被存在了offline表里的dt2024.12月里

-- 思路：join offline表和工单表，统计工单表里有多少distinct零件存在了offline表里
-- 用工单表的trace_code = offline表里的product_serial_num做匹配

SELECT COUNT(DISTINCT a.trace_code) AS num_matched_parts
FROM table1 as a
JOIN table2 as o
  ON a.trace_code = o.product_serial_num    
WHERE o.supplier_code = '7DG'
  and o.dt >= '2024-12-01'
  AND o.dt < '2025-01-01'

-- 结果：4
