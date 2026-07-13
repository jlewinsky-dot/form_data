import json
import requests
import logging
from time import sleep
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def get_non_automation_leads(ALL_GF_NON_AUTOMATION_SITES):
    all_leads = []
    last_month = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")

    for site in ALL_GF_NON_AUTOMATION_SITES:
        try:
            url = site["site"].rstrip("/") + "/wp-json/gf/v2/entries"
            current_page = 1

            headers = { # mimic a browser request so the API doesn't block us
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                    "Version/18.0 Safari/605.1.15"
                ),
                "Accept": "application/json, text/javascript, */*; q=0.01",
            }

            while True:
                params = {
                    "paging[page_size]": 100,
                    "paging[current_page]": current_page,
                    "search": json.dumps({
                        "mode": "all",
                        "field_filters": [{
                            "key": "date_created",
                            "operator": ">",
                            "value": last_month
                        }]
                    })
                }

                for attempt in range(3):
                    try:
                        response = requests.get(
                            url,
                            auth=(site["ck"], site["cs"]),
                            headers=headers,
                            params=params,
                            timeout=30,
                        )
                        break
                    except Exception:
                        if attempt < 2:
                            logger.warning(f"Attempt {attempt + 1} failed for {site['key']}. Retrying...")
                            sleep(2)
                        else:
                            raise

                data = response.json()
                entries = data.get("entries", [])
                total = int(data.get("total_count", 0))

                if not entries:
                    break

                for lead in entries:
                    row = {
                        "site_key": site["key"],
                        "site_url": site["site"],
                        "form_id": str(lead.get("form_id")),
                        "entry_id": str(lead.get("id")),
                        "created_at": lead.get("date_created"),
                        "source_url": lead.get("source_url"),
                        "automation": site["automation"]
                    }
                    all_leads.append(row)

                if len(all_leads) >= 100:
                    yield all_leads
                    all_leads = []

                if current_page * 100 >= total:
                    break

                current_page += 1

        except Exception as e:
            logger.error(f"{site.get('key')}: {e}")
            continue

    if all_leads:
        logger.info(f"Yielding final batch of {len(all_leads)}")
        yield all_leads
