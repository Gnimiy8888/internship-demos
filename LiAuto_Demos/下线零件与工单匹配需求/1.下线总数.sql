-- offline表里，时间在2024.12月，supplier_code = '7DG'的所有下线零件（用最新下线时间筛选）

select count(*)
FROM (
SELECT
    product_serial_num,
    product_offline_time,
    product_code,
    ROW_NUMBER() OVER (PARTITION BY product_serial_num ORDER BY product_offline_time DESC) AS rn
FROM table1
WHERE supplier_code = '7DG'
    AND dt >= '2024-12-01'
    AND dt < '2025-01-01'
) t
WHERE t.rn = 1

-- 结果：19636