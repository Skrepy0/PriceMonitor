import logging
import os
import re
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv()
logger = logging.getLogger(__name__)

APP_NAME = 'Price Monitor'
PRICE_DATA_SAVE_PATH = os.path.join(PROJECT_ROOT, 'data')
LOG_SAVE_PATH = os.path.join(PROJECT_ROOT, 'logs')

PRICE_RELATED_KEYS = [
    'model_ratio',  # 模型倍率
    'model_price',  # 模型价格（直接标价）
    'completion_ratio',  # 输出倍率
    'cache_ratio',  # 缓存折扣率
    'create_cache_ratio',  # 创建缓存倍率
    'billing_mode',  # 计费模式（如 tiered_expr）
    'billing_expr',  # 计费表达式
    'enable_groups',  # 可用分组（影响价格适用群体）
    'quota_type',  # 配额类型（0/1 等）
    'image_ratio',  # 图片相关倍率（如果有）
    'audio_ratio',  # 音频相关倍率
]
COMPARE_EXCLUDE_KEYS = ['enable_groups']
PERIOD = int(os.getenv('PERIOD', '86400'))
PRICE_RATIO = float(os.getenv('PRICE_RATIO', '1.14'))
MAX_RATIO = float(os.getenv('MAX_RATIO', '999999999'))
MAX_BASE_PRICE = float(os.getenv('MAX_BASE_PRICE', '0.8'))
GROUP_RATIO_RATIO = float(os.getenv('GROUP_RATIO_RATIO', '1'))
SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.qq.com')
if not SMTP_HOST:
    logger.error('SMTP_HOST 环境变量未设置')

SMTP_PORT = int(os.getenv('SMTP_PORT', '465'))
if not SMTP_PORT:
    logger.error('SMTP_PORT 环境变量未设置')

SMTP_USER = os.getenv('SMTP_USER', '')
if not SMTP_USER:
    logger.error('SMTP_USER 环境变量未设置')

SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
if not SMTP_PASSWORD:
    logger.error('SMTP_PASSWORD 环境变量未设置')

SMTP_FROM = os.getenv('SMTP_FROM', SMTP_USER)
if not SMTP_FROM:
    logger.error('SMTP_FROM 环境变量未设置')

UPSTREAM_URL = os.getenv('UPSTREAM_URL')
if not UPSTREAM_URL:
    logger.warning('UPSTREAM_URL 环境变量未设置')

UPSTREAM_TOKEN = os.getenv('UPSTREAM_TOKEN')
if not UPSTREAM_TOKEN:
    logger.warning('UPSTREAM_TOKEN 环境变量未设置')

STATION_URL = os.getenv('STATION_URL')
if not STATION_URL:
    logger.warning('STATION_URL 环境变量未设置')

STATION_TOKEN = os.getenv('STATION_TOKEN')
if not STATION_TOKEN:
    logger.warning('STATION_TOKEN 环境变量未设置')

WARNING_EMAIL_RAW = os.getenv('WARNING_EMAIL', '')
if not WARNING_EMAIL_RAW:
    logger.warning('WARNING_EMAIL 环境变量未设置，将不会发送邮件')
    WARNING_EMAIL_LIST = []
else:
    WARNING_EMAIL_LIST = [
        email.strip()
        for email in re.split(r'[,;]', WARNING_EMAIL_RAW)
        if email.strip()
    ]
    if not WARNING_EMAIL_LIST:
        logger.warning('WARNING_EMAIL 解析后为空，将不会发送邮件')
    else:
        logger.info(f'邮件接收人: {", ".join(WARNING_EMAIL_LIST)}')
