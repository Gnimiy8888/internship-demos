-- 在result中被判定为异常（is_anomaly=1），但在工单表里没有找到对应零件的统计数量
-- （工单trace_code无法和异常零件product_serial_num关联上的数量）

-- 思路：先从 offline 表获得需要的 dt 范围
-- 通过和 offline 表的 product_serial_num 关联，对 result 表做限定；
-- 然后把 result 和工单 left join，查找 trace_code is null（即没有工单）

SELECT COUNT(DISTINCT r.product_serial_num)
FROM table1 as r
INNER JOIN table2 as o
  ON r.product_serial_num = o.product_serial_num
LEFT JOIN table3 as a
  ON r.product_serial_num = a.trace_code
WHERE
  o.supplier_code = '7DG'
  AND o.dt >= '2024-12-01' AND o.dt < '2025-01-01'
  AND r.is_anomaly = 1
  AND a.trace_code IS NULL

-- 结果：4903