SELECT age, gender, user_count, record_count, total_purchase, average_purchase,
       1.0 * total_purchase / (SELECT SUM(total_purchase) FROM customer_segments) AS share_of_all_purchase,
       1.0 * total_purchase / (SELECT SUM(total_purchase) FROM customer_segments WHERE age = :age) AS share_of_age_purchase
FROM customer_segments
WHERE age = :age AND gender = :gender;
