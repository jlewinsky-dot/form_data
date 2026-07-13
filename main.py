import os
import json
import logging
import psycopg2
from concurrent.futures import ThreadPoolExecutor, as_completed
from extract_automation_entries import create_automation_dicts
from extract_all_entries import create_all_gf_dicts
from extract_calls import get_calls
from get_token import get_access_token
from get_search_console_performance import get_search_console_data
from get_non_automation_leads import get_non_automation_leads
from get_keyword_rankings import get_keyword_rankings
from supabase import create_client
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    load_dotenv()
    GF_SITES = json.loads(os.environ["GF_SITES_JSON"])
    CTM_SITES = json.loads(os.environ["CTM_SITES"])
    GSC_SITES = json.loads(os.environ["GSC_SITES_JSON"])
    ALL_GF_NON_AUTOMATION_SITES = json.loads(os.environ["ALL_GF_NON_AUTOMATION_SITES"])
    CLIENT_ID = os.getenv("CLIENT_ID")
    CLIENT_SECRET = os.getenv("CLIENT_SECRET")
    REFRESH_TOKEN = os.getenv("REFRESH_TOKEN")

    logger.info("Starting pipeline")
    sb = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )

    logger.info("Fetching access token")
    access_token = get_access_token(CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN) # Google API needs a fresh access token each run

    def run_non_automation_leads():
        logger.info("Fetching all leads from past month")
        for batch in get_non_automation_leads(ALL_GF_NON_AUTOMATION_SITES):
            logger.info(f"Upserting {len(batch)} leads")
            sb.table("all_past_month").upsert(
                batch,
                on_conflict="site_url, form_id, entry_id"
            ).execute()

    def run_search_console():
        logger.info("Fetching search console rows")
        for batch in get_search_console_data(access_token, GSC_SITES):
            logger.info(f"Upserting {len(batch)} search console rows")
            sb.table("search_console").upsert(
                batch,
                on_conflict="page_url"
            ).execute()

    def run_keyword_rankings():
        logger.info("Fetching keyword rankings")
        for batch in get_keyword_rankings(access_token, GSC_SITES):
            logger.info(f"Upserting {len(batch)} keyword rankings")
            sb.table("gsc_keyword_rankings").upsert(
                batch,
                on_conflict="site_key,query,date"
            ).execute()

    def run_automation_forms():
        logger.info("Fetching automation forms")
        for gf_rows in create_automation_dicts(GF_SITES):
            logger.info(f"Upserting {len(gf_rows)} automation entries")
            sb.table("gf_entries").upsert(
                gf_rows,
                on_conflict="site_key,form_id,entry_id",
            ).execute()

    def run_all_forms():
        logger.info("Fetching all forms")
        for all_gf_rows in create_all_gf_dicts(GF_SITES):
            logger.info(f"Upserting {len(all_gf_rows)} all form entries")
            sb.table("all_gf_entries").upsert(
                all_gf_rows,
                on_conflict="site_key, form_id, entry_id"
            ).execute()

    def run_ctm_calls():
        logger.info("Fetching CTM calls")
        for call_rows in get_calls(CTM_SITES):
            logger.info(f"Upserting {len(call_rows)} CTM calls")
            sb.table("ctm_calls").upsert(
                call_rows,
                on_conflict="site_key,entry_id"
            ).execute()

    # Non-GSC tasks run in parallel
    tasks = [
        run_non_automation_leads,
        run_automation_forms,
        run_all_forms,
        run_ctm_calls,
    ]

    with ThreadPoolExecutor() as executor:
        futures = {executor.submit(task): task.__name__ for task in tasks}
        for future in as_completed(futures):
            name = futures[future]
            try:
                future.result()
                logger.info(f"{name} completed successfully")
            except Exception as e:
                logger.error(f"{name} failed: {e}")

    # GSC tasks run sequentially to avoid Google API disconnects
    run_search_console()
    logger.info("run_search_console completed successfully")
    run_keyword_rankings()
    logger.info("run_keyword_rankings completed successfully")

    # Direct Postgres connection to bypass Supabase RPC timeout
    logger.info("Refreshing keyword position changes table")
    conn = psycopg2.connect(os.environ["SUPABASE_DB_URL"])
    try:
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SET statement_timeout = '300s';")
        cur.execute("SELECT refresh_keyword_changes();")
        cur.close()
        logger.info("Keyword position changes refreshed successfully")
    finally:
        conn.close()

    logger.info("Pipeline complete")

if __name__ == "__main__":
    main()
