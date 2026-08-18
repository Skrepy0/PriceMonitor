import asyncio
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.config import PERIOD
from src.monitor.upstream_price_monitor import monitor_upstream_price
from src.store.json import init

scheduler = AsyncIOScheduler()

scheduler.add_job(
    monitor_upstream_price,
    'interval',
    seconds=PERIOD,
    next_run_time=datetime.now() + timedelta(seconds=20),
)


async def main():
    scheduler.start()
    forever = asyncio.Future()
    try:
        await forever
    finally:
        scheduler.shutdown()


if __name__ == '__main__':
    init()
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('./logs/app.log', encoding='utf-8'),
        ],
    )
    asyncio.run(main())
