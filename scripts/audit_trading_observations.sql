BEGIN TRANSACTION READ ONLY;
WITH active AS (
 SELECT instrument_id,currency,symbol FROM instrument_identifiers
 WHERE provider='yahoo' AND currency IN ('EUR','USD') AND valid_from<=now() AND (valid_to IS NULL OR valid_to>now())
), latest AS (
 SELECT DISTINCT ON (instrument_id,session_date) *
 FROM eod_bars WHERE provider='yahoo'
 ORDER BY instrument_id,session_date,revision DESC
), checked AS (
 SELECT a.symbol,a.currency,b.session_date,b.quality_status,
 CASE WHEN b.instrument_id IS NULL THEN 'missing'
 WHEN b.currency<>a.currency OR b.open<=0 OR b.close<=0 OR b.low<=0 OR b.high<greatest(b.open,b.close,b.low) OR b.low>least(b.open,b.close,b.high) OR b.volume<0 THEN 'invalid'
 WHEN b.first_available_at IS NULL OR b.published_at IS NULL THEN 'legacy_no_provenance'
 WHEN b.first_available_at<b.published_at OR b.first_available_at>now() OR b.session_date>b.published_at::date THEN 'invalid_chronology'
 ELSE 'observed_not_certified' END AS audit_status
 FROM active a LEFT JOIN latest b ON a.instrument_id=b.instrument_id AND b.session_date=DATE '2026-11-27'
)
SELECT currency,audit_status,count(*) FROM checked GROUP BY currency,audit_status ORDER BY currency,audit_status;
SELECT i.symbol,i.mic,i.currency,max(b.session_date) AS latest_session
FROM instrument_identifiers i LEFT JOIN eod_bars b ON b.instrument_id=i.instrument_id AND b.provider='yahoo'
WHERE i.provider='yahoo' AND i.currency IN ('EUR','USD') AND i.valid_to IS NULL
GROUP BY i.id,i.symbol,i.mic,i.currency
HAVING max(b.session_date) IS NULL OR max(b.session_date)<DATE '2026-11-27';
SELECT quality_status,currency,count(*),count(DISTINCT instrument_id) FROM eod_bars WHERE provider='yahoo' AND currency IN ('EUR','USD') GROUP BY quality_status,currency;
ROLLBACK;
