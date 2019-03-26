# Telega

## Description
Python Telegram TDLib sync client
Python API for the [tdlib](https://github.com/tdlib/td) library.
It helps you build your own Telegram clients.

## Installation
pip install telega

## Example

```python
from telega import TelegramTDLibClient
from telega.client import ProxyTypes


telegram_client = TelegramTDLibClient(
    api_id=777,
    api_hash='abc',
    phone='911',
    database_encryption_key='NAd62byYz7em',
    # see all parameters in source code
)

telegram_client.set_proxy('111.111.111.111', 8080, ProxyTypes.proxyTypeHttp)
# telegram_client.check_proxy()  # ping if you need

if not telegram_client.is_authorized():
    password = input('2 factor auth password (if you have): ')
    telegram_client.auth_request()
    sms_code = input('sms_code: ')
    telegram_client.send_sms_code(sms_code, password)

print(telegram_client.get_all_chats())

```
## Logging
Just set config for 'telega' logger. 
Also you can set C++ logging level - TelegramTDLibClient(tdlib_log_level=3)

```python
import logging.config


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {'main': {'format': '[%(levelname)s] [%(asctime)s] [%(module)s:%(lineno)d] %(message)s',
                            'datefmt': '%d/%m/%Y %H:%M:%S'}},
    'handlers': {'console': {'level': 'DEBUG', 'class': 'logging.StreamHandler', 'formatter': 'main'}, },
    'loggers': {'telega': {'handlers': ['console'], 'propagate': False, 'level': 'INFO'}, }
}
logging.config.dictConfig(LOGGING)

```
