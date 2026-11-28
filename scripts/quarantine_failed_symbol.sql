-- Execute only after verified backup; preserve instrument and all historical bars.
BEGIN;
DO $$
DECLARE n integer;
BEGIN
  SELECT count(*) INTO n FROM instrument_identifiers
  WHERE provider='yahoo' AND symbol='KESKOBU0126.HE' AND currency='EUR' AND valid_to IS NULL;
  IF n <> 1 THEN RAISE EXCEPTION 'Expected exactly one active quarantined identifier, got %', n; END IF;
  UPDATE instrument_identifiers SET valid_to=clock_timestamp()
  WHERE provider='yahoo' AND symbol='KESKOBU0126.HE' AND currency='EUR' AND valid_to IS NULL;
  IF (SELECT count(*) FROM instrument_identifiers WHERE provider='yahoo' AND currency IN ('EUR','USD') AND valid_to IS NULL) <> 801 THEN
    RAISE EXCEPTION 'Unexpected remaining universe';
  END IF;
END $$;
COMMIT;
