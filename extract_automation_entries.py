import json
import requests
import logging
from time import sleep
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def create_automation_dicts(GF_SITES):
    all_leads = []
    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    for site in GF_SITES:
        try:
            url = site["site"].rstrip("/") + "/wp-json/gf/v2/entries"
            headers = { # mimic a browser request so the API doesn't block us
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                    "Version/18.0 Safari/605.1.15"
                ),
                "Accept": "application/json, text/javascript, */*; q=0.01",
            }
            for form_id in site["automation_forms"]:
                params = {
                    "form_ids": form_id,
                    "search": json.dumps({ # only entries from the last 7 days
                        "field_filters": [{
                            "key": "date_created",
                            "operator": ">",
                            "value": seven_days_ago
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
                            logger.warning(f"Attempt {attempt + 1} failed. Retrying...")
                            sleep(2)
                        else:
                            raise
                data = response.json()

                for lead in data.get("entries", []):
                    row = {
                        "site_key": site["key"],
                        "site_url": site["site"],
                        "form_id": str(lead.get("form_id", form_id)),
                        "entry_id": str(lead.get("id")),
                        "created_at": lead.get("date_created"),
                        "source_url": lead.get("source_url"),
                    }
                    all_leads.append(row)
                    if len(all_leads) > 100:
                        yield all_leads
                        all_leads = []
        except Exception as e:
            logger.error(f"Failed to fetch data for {site.get('key')}: {e}")
            continue

    if all_leads:
        logger.info(f"Yielding final batch of {len(all_leads)}")
        yield all_leads
