import requests

from config import STATION_URL, STATION_TOKEN
from store.json import save_json

base_url = STATION_URL if STATION_URL.endswith('/') else STATION_URL + '/'
token = STATION_TOKEN
headers = {'Authorization': f'Bearer {token}'}


def get_station_price():
    response = requests.get(f'{base_url}api/pricing', headers=headers)
    if response.status_code == 200:
        save_json(response.json(), 'station_price')
        return response.json()
    return None


if __name__ == '__main__':
    price_json = get_station_price()
