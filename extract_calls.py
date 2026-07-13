import os
import requests
import logging
from time import sleep
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def get_calls(CTM_SITES):
    all_calls = []
    seen = set()
    auth = (os.getenv("ACCESS_KEY"), os.getenv("SECRET_KEY"))
    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    for site in CTM_SITES:
        try:
            page = 1
            url = f"https://api.calltrackingmetrics.com/api/v1/accounts/{site['id']}/calls"
            tracking_number = str(site["tracking_number"])

            while True:
                params = {
                    "page": page,
                    "start_date": seven_days_ago
                }
                for attempt in range(3):
                    try:
                        data = requests.get(
                            url,
                            auth=auth,
                            params=params,
                            timeout=30,
                        ).json()
                        break
                    except Exception:
                        if attempt < 2:
                            logger.warning(f"Attempt {attempt + 1} failed. Retrying...")
                            sleep(2)
                        else:
                            raise

                calls = data.get("calls", [])
                if not calls:
                    break

                for call in calls:
                    # only want calls that came through the site's tracking number
                    if tracking_number not in str(call):
                        continue

                    secs = int(call.get("talk_time") or call.get("duration") or 0)
                    if secs < 30: # under 30 seconds is probably spam
                        continue

                    entry_id = str(call.get("id") or "")
                    k = (site.get("key"), entry_id)
                    if k in seen:
                        continue
                    seen.add(k)

                    row = {
                        "site_key": site.get("key"),
                        "site_url": site.get("site"),
                        "entry_id": entry_id,
                        "created_at": call.get("called_at") or call.get("@timestamp"),
                    }
                    all_calls.append(row)
                    if len(all_calls) > 100:
                        yield all_calls
                        all_calls = []

                page += 1

        except Exception as e:
            logger.error(f"Failed to fetch calls for {site.get('key')}: {e}")
            continue

    if all_calls:
        logger.info(f"Yielding final batch of {len(all_calls)}")
        yield all_calls
