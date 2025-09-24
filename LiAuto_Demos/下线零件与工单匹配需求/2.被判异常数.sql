-- 最新下线零件中在result表里被判为异常的数量

-- 思路：1和result表join，筛选出1的零件在result里被判为异常的零件数量

  SELECT
  count(distinct t.product_serial_num)
FROM
 (
    SELECT
      product_serial_num,
      ROW_NUMBER() OVER (
        PARTITION BY product_serial_num
        ORDER BY product_offline_time DESC
      ) AS rn
    FROM table1
    WHERE supplier_code = '7DG'
      AND dt >= '2024-12-01'
      AND dt < '2025-01-01'
 ) t
JOIN table2 as r
  ON t.product_serial_num = r.product_serial_num
WHERE t.rn = 1
  AND r.is_anomaly = 1

-- 结果：4907