import requests
import logging
from time import sleep
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def get_keyword_rankings(access_token, gsc_sites):
    rows = []

    # GSC data lags about 2 days, so end the range there and go back 90 days
    end_date = datetime.now() - timedelta(days=2)
    start_date = end_date - timedelta(days=90)

    for site in gsc_sites:
        encoded_site = site['gsc_property'].replace('://', '%3A%2F%2F').replace('/', '%2F')

        for attempt in range(3):
            try:
                response = requests.post(
                    f'https://www.googleapis.com/webmasters/v3/sites/{encoded_site}/searchAnalytics/query',
                    headers={'Authorization': f'Bearer {access_token}'},
                    json={
                        'startDate': start_date.strftime('%Y-%m-%d'),
                        'endDate': end_date.strftime('%Y-%m-%d'),
                        'dimensions': ['query', 'date'],
                        'rowLimit': 25000
                    }
                )
                response.raise_for_status()
                data = response.json()

                for item in data.get('rows', []):
                    row = {
                        'site_key': site['key'][:500],
                        'site_url': site['site'][:500],
                        'query': item['keys'][0][:500],
                        'date': item['keys'][1],
                        'clicks': item['clicks'],
                        'impressions': item['impressions'],
                        'ctr': item['ctr'],
                        'position': item['position'],
                    }
                    rows.append(row)
                    if len(rows) > 100:
                        yield rows
                        rows = []

                logger.info(f"Fetched {len(data.get('rows', []))} keywords for {site['key']}")
                break

            except Exception as e:
                if attempt < 2:
                    logger.warning(f"Attempt {attempt + 1} failed for {site['key']}: {e}. Retrying...")
                    sleep(2)
                else:
                    logger.error(f"Failed to fetch {site['key']} after 3 attempts: {e}")
                    raise

        sleep(1)

    if rows:
        logger.info(f"Yielding final batch of {len(rows)}")
        yield rows
