-- Bind :age and :gender; keep denominators outside the segment filter.
SELECT :age AS age, :gender AS gender,
       COUNT(DISTINCT User_ID) AS user_count, COUNT(*) AS record_count,
       SUM(Purchase) AS total_purchase, AVG(Purchase) AS average_purchase,
       1.0 * SUM(Purchase) / (SELECT SUM(Purchase) FROM purchases) AS share_of_all_purchase,
       1.0 * SUM(Purchase) / (SELECT SUM(Purchase) FROM purchases WHERE Age = :age) AS share_of_age_purchase
FROM purchases
WHERE Age = :age AND Gender = :gender;
