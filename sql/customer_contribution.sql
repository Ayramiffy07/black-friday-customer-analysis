-- Approved metric query: age x gender contribution.
-- Purchase uses the source unit; record_count is NOT order count.
WITH segment AS (
    SELECT Age AS age, Gender AS gender,
           COUNT(DISTINCT User_ID) AS user_count,
           COUNT(*) AS record_count,
           SUM(Purchase) AS total_purchase,
           AVG(Purchase) AS average_purchase
    FROM purchases
    GROUP BY Age, Gender
)
SELECT *,
       1.0 * total_purchase / SUM(total_purchase) OVER () AS share_of_all_purchase
FROM segment
ORDER BY total_purchase DESC, age, gender;
