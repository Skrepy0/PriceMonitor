import json

from config import PRICE_RATIO
from data.station_price import StationPriceData
from monitor.upstream import get_upstream_price

if __name__ == '__main__':
    data = StationPriceData(get_upstream_price()).formatted_station_price()
    for key in data.keys():
        data1 = data[key]
        for key1 in data1.keys():
            data[key][key1] = data[key][key1] * PRICE_RATIO
    with open('./data/price.json', 'w') as f:
        json.dump(data, f, indent=4)
