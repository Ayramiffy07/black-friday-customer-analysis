-- Public demo: verified age x gender aggregates, no user-level records.
SELECT age, gender, user_count, record_count, total_purchase, average_purchase,
       1.0 * total_purchase / SUM(total_purchase) OVER () AS share_of_all_purchase
FROM customer_segments
ORDER BY total_purchase DESC, age, gender;
