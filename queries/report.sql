--Hourly usage trend: requests/tokens/errors by hour
-------------------------------------------------------------------------------
SELECT
  strftime('%Y-%m-%dT%H:00:00Z', timestamp) AS hour,
  COUNT(*) AS requests,
  SUM(total_tokens) AS total_tokens,
  SUM(input_tokens) AS input_tokens,
  SUM(output_tokens) AS output_tokens,
  SUM(reasoning_tokens) AS reasoning_tokens,
  SUM(cached_tokens) AS cached_tokens,
  SUM(failed) AS failed_requests,
  ROUND(100.0 * SUM(failed) / NULLIF(COUNT(*), 0), 2) AS error_rate_pct,
  ROUND(AVG(latency_ms), 2) AS avg_latency_ms
FROM usage_events
GROUP BY hour
ORDER BY hour;

--Top users: consumption by user/team
-------------------------------------------------------------------------------
SELECT
  username,
  team,
  COUNT(*) AS requests,
  SUM(total_tokens) AS total_tokens,
  SUM(input_tokens) AS input_tokens,
  SUM(output_tokens) AS output_tokens,
  SUM(reasoning_tokens) AS reasoning_tokens,
  SUM(cached_tokens) AS cached_tokens,
  SUM(failed) AS failed_requests,
  ROUND(100.0 * SUM(failed) / NULLIF(COUNT(*), 0), 2) AS error_rate_pct,
  ROUND(AVG(latency_ms), 2) AS avg_latency_ms
FROM usage_events
GROUP BY username, team
ORDER BY total_tokens DESC
LIMIT 50;

--Anomaly candidates: users above hourly token threshold
-- Replace :token_threshold with a number, e.g. 1000000.
-------------------------------------------------------------------------------
SELECT
  strftime('%Y-%m-%dT%H:00:00Z', timestamp) AS hour,
  username,
  team,
  COUNT(*) AS requests,
  SUM(total_tokens) AS total_tokens
FROM usage_events
GROUP BY hour, username, team
HAVING SUM(total_tokens) >= 100000000
ORDER BY total_tokens DESC;
