import requests
import logging
from time import sleep

logger = logging.getLogger(__name__)

def get_access_token(CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN):
    for attempt in range(3):
        try:
            response = requests.post('https://oauth2.googleapis.com/token', data={
                'client_id': CLIENT_ID,
                'client_secret': CLIENT_SECRET,
                'refresh_token': REFRESH_TOKEN,
                'grant_type': 'refresh_token'
            })
            response.raise_for_status()

            response_data = response.json()

            if 'access_token' not in response_data:
                raise KeyError(f"No access_token in response: {response_data}")

            return response_data['access_token']

        except Exception as retry_err:
            if attempt < 2:
                logger.warning(f"Attempt {attempt + 1} failed: {retry_err}. Retrying...")
                sleep(2)
            else:
                raise
