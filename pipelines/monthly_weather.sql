-- Lakeflow Declarative Pipeline (SQL version of monthly_weather.py):
-- monthly temperature stats per city.
-- ${source_table} comes from the pipeline configuration (resources/weather_pipeline_sql.yml).

CREATE OR REFRESH MATERIALIZED VIEW monthly_weather_per_city_sql
COMMENT 'Highest, lowest and average temperature per city and month (actuals only)'
AS SELECT
  city,
  trunc(date, 'MM') AS month,
  MAX(temperature_max_c) AS highest_temperature_c,
  MIN(temperature_min_c) AS lowest_temperature_c,
  ROUND(AVG((temperature_max_c + temperature_min_c) / 2), 1) AS average_temperature_c,
  COUNT(*) AS days
FROM ${source_table}
WHERE NOT is_forecast
GROUP BY city, trunc(date, 'MM');
