from config import STATION_TOKEN, STATION_URL

BASE_URL = STATION_URL
HEADERS = {
    'Authorization': f'Bearer {STATION_TOKEN}',
    'Content-Type': 'application/json',
}
