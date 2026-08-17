import logging
from email.message import EmailMessage

import aiosmtplib

from config import (
    WARNING_EMAIL_LIST,
    SMTP_PASSWORD,
    SMTP_FROM,
    APP_NAME,
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USER,
)

logger = logging.getLogger(__name__)


async def send_email(body: str) -> bool:
    if not WARNING_EMAIL_LIST:
        logger.warning('邮件接收人列表为空，跳过发送')
        return False

    if not SMTP_PASSWORD:
        logger.warning('SMTP_PASSWORD 未配置，无法发送邮件')
        return False

    msg = EmailMessage()
    msg['From'] = SMTP_FROM
    msg['To'] = ', '.join(WARNING_EMAIL_LIST)
    msg['Subject'] = f'{APP_NAME} 提醒'
    msg.set_content(body.strip())

    try:
        await aiosmtplib.send(
            msg,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            username=SMTP_USER,
            password=SMTP_PASSWORD,
            use_tls=True if SMTP_PORT == 465 else False,
            start_tls=True if SMTP_PORT == 587 else False,
        )
        logger.info(f'✅ 邮件已发送至 {", ".join(WARNING_EMAIL_LIST)}')
        return True
    except Exception as e:
        logger.error(f'❌ 邮件发送失败: {e}')
        return False
