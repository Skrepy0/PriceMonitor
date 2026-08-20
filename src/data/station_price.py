import logging
from enum import Enum

logger = logging.getLogger(__name__)


class StationPriceOption(str, Enum):
    MODEL_PRICE = 'ModelPrice'
    MODEL_RATIO = 'ModelRatio'
    CACHE_RATIO = 'CacheRatio'
    COMPLETION_RATIO = 'CompletionRatio'
    CREATE_CACHE_RATIO = 'CreateCacheRatio'
    AUDIO_RATION = 'AudioRatio'
    AUDIO_COMPLETION_RATIO = 'AudioCompletionRatio'
    IMAGE_RATIO = 'ImageRatio'


class StationPriceType(str, Enum):
    MODEL_PRICE = 'model_price'
    MODEL_RATIO = 'model_ratio'
    CACHE_RATIO = 'cache_ratio'
    COMPLETION_RATIO = 'completion_ratio'
    CREATE_CACHE_RATIO = 'create_cache_ratio'
    AUDIO_RATION = 'audio_ratio'
    AUDIO_COMPLETION_RATIO = 'audio_completion_ratio'
    IMAGE_RATIO = 'image_ratio'

    @property
    def option(self) -> StationPriceOption:
        mapping = {
            StationPriceType.MODEL_PRICE: StationPriceOption.MODEL_PRICE,
            StationPriceType.MODEL_RATIO: StationPriceOption.MODEL_RATIO,
            StationPriceType.CACHE_RATIO: StationPriceOption.CACHE_RATIO,
            StationPriceType.COMPLETION_RATIO: StationPriceOption.COMPLETION_RATIO,
            StationPriceType.CREATE_CACHE_RATIO: StationPriceOption.CREATE_CACHE_RATIO,
            StationPriceType.AUDIO_RATION: StationPriceOption.AUDIO_RATION,
            StationPriceType.AUDIO_COMPLETION_RATIO: StationPriceOption.AUDIO_COMPLETION_RATIO,
            StationPriceType.IMAGE_RATIO: StationPriceOption.IMAGE_RATIO,
        }
        return mapping[self]


PRICE_TYPES = [
    StationPriceType.MODEL_PRICE,
    StationPriceType.MODEL_RATIO,
    StationPriceType.CACHE_RATIO,
    StationPriceType.COMPLETION_RATIO,
    StationPriceType.CREATE_CACHE_RATIO,
    StationPriceType.AUDIO_RATION,
    StationPriceType.AUDIO_COMPLETION_RATIO,
    StationPriceType.IMAGE_RATIO,
]


def get_station_price_type_from_str(key: str) -> StationPriceType | None:
    try:
        res = StationPriceType(key)
        return res
    except ValueError:
        return None


class StationPriceData:
    def __init__(self, station_price: dict):
        self.price = station_price
        self.is_available = False
        if self.price:
            self.is_available = True
        self.station_model_data = self.price.get('data')
        self.model_price = {}
        self.model_ratio = {}
        self.cache_ratio = {}
        self.completion_ratio = {}
        self.create_cache_ratio = {}
        self.audio_ratio = {}
        self.audio_completion_ratio = {}
        self.image_ratio = {}
        if self.is_available:
            for model in self.station_model_data:
                name = model['model_name']
                for key, value in model.items():
                    if key == StationPriceType.MODEL_PRICE and value != 0:
                        self.model_price[name] = value
                    elif key == StationPriceType.MODEL_RATIO:
                        self.model_ratio[name] = value
                    elif key == StationPriceType.CACHE_RATIO:
                        self.cache_ratio[name] = value
                    elif key == StationPriceType.COMPLETION_RATIO:
                        self.completion_ratio[name] = value
                    elif key == StationPriceType.CREATE_CACHE_RATIO:
                        self.create_cache_ratio[name] = value
                    elif key == StationPriceType.AUDIO_RATION:
                        self.audio_ratio[name] = value
                    elif key == StationPriceType.AUDIO_COMPLETION_RATIO:
                        self.audio_completion_ratio[name] = value
                    elif key == StationPriceType.IMAGE_RATIO:
                        self.image_ratio[name] = value

    def get_price(self):
        return self.price

    def get_model_price(self):
        return self.model_price

    def change_model_price(self, model: str, value: float):
        self.model_price[model] = value

    def get_model_ratio(self):
        return self.model_ratio

    def change_model_ratio(self, model: str, value: float):
        self.model_ratio[model] = value

    def get_cache_ratio(self):
        return self.cache_ratio

    def change_cache_ratio(self, model: str, value: float):
        self.cache_ratio[model] = value

    def get_completion_ratio(self):
        return self.completion_ratio

    def change_completion_ratio(self, model: str, value: float):
        self.completion_ratio[model] = value

    def get_create_cache_ratio(self):
        return self.create_cache_ratio

    def change_create_cache_ratio(self, model: str, value: float):
        self.create_cache_ratio[model] = value

    def get_audio_ratio(self):
        return self.audio_ratio

    def change_audio_ratio(self, model: str, value: float):
        self.audio_ratio[model] = value

    def get_audio_completion_ratio(self):
        return self.audio_completion_ratio

    def change_audio_completion_ratio(self, model: str, value: float):
        self.audio_completion_ratio[model] = value

    def get_image_ratio(self):
        return self.image_ratio

    def change_image_ratio(self, model: str, value: float):
        self.image_ratio[model] = value

    def change_value(self, key: StationPriceType, model: str, value: float):
        if key == StationPriceType.MODEL_PRICE:
            self.change_model_price(model, value)
        elif key == StationPriceType.MODEL_RATIO:
            self.change_model_ratio(model, value)
        elif key == StationPriceType.CACHE_RATIO:
            self.change_cache_ratio(model, value)
        elif key == StationPriceType.COMPLETION_RATIO:
            self.change_completion_ratio(model, value)
        elif key == StationPriceType.CREATE_CACHE_RATIO:
            self.change_create_cache_ratio(model, value)
        elif key == StationPriceType.AUDIO_RATION:
            self.change_audio_ratio(model, value)
        elif key == StationPriceType.AUDIO_COMPLETION_RATIO:
            self.change_audio_completion_ratio(model, value)
        elif key == StationPriceType.IMAGE_RATIO:
            self.change_image_ratio(model, value)

    def formatted_station_price(self):
        return {
            StationPriceType.MODEL_PRICE: self.model_price,
            StationPriceType.MODEL_RATIO: self.model_ratio,
            StationPriceType.CACHE_RATIO: self.cache_ratio,
            StationPriceType.COMPLETION_RATIO: self.completion_ratio,
            StationPriceType.CREATE_CACHE_RATIO: self.create_cache_ratio,
            StationPriceType.AUDIO_RATION: self.audio_ratio,
            StationPriceType.AUDIO_COMPLETION_RATIO: self.audio_completion_ratio,
            StationPriceType.IMAGE_RATIO: self.image_ratio,
        }
