"""Read-only EUR/USD coverage gate shared by trading applications."""
import argparse
import json
from sqlalchemy import create_engine, text

def audit(dsn):
    engine=create_engine(dsn)
    try:
        with engine.connect() as c:
            c.execute(text("SET TRANSACTION READ ONLY"))
            if c.execute(text("SELECT current_database()")).scalar_one()!="market_data_hub":
                raise ValueError("unexpected database")
            identifiers=[dict(r) for r in c.execute(text("""
                SELECT currency, count(*) AS identifiers, count(DISTINCT instrument_id) AS instruments
                FROM instrument_identifiers WHERE provider='yahoo'
                AND valid_from<=now() AND (valid_to IS NULL OR valid_to>now())
                GROUP BY currency ORDER BY currency
            """)).mappings()]
            bars=[dict(r) for r in c.execute(text("""
                SELECT currency,quality_status,count(*) AS bars,
                count(*) FILTER (WHERE published_at IS NULL OR first_available_at IS NULL) AS missing_provenance
                FROM eod_bars WHERE provider='yahoo' AND currency IN ('EUR','USD')
                GROUP BY currency,quality_status ORDER BY currency,quality_status
            """)).mappings()]
            c.rollback()
        return {"identifiers":identifiers,"bars":bars,"paper_authorized":False,
                "note":"Coverage alone cannot establish dated index membership or historical availability."}
    finally:
        engine.dispose()

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--dsn",required=True)
    a=p.parse_args()
    print(json.dumps(audit(a.dsn),indent=2))

if __name__=="__main__":
    main()
