import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
PAYLOAD = {'from_date': 0}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='main.log',
    filemode='w',
    format='%(asctime)s, %(levelname)s, %(message)s'
)

logger = logging.getLogger(__name__)


def check_tokens():
    """Проверка доступности переменных окружения."""
    if (PRACTICUM_TOKEN or TELEGRAM_TOKEN or TELEGRAM_CHAT_ID) is None:
        logging.critical('Отсутствуют переменные окружения')
        sys.exit()


def send_message(bot, message):
    """Отправляем сообщение."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Сообщение отправленно успешно. Ура!')
    except Exception as error:
        logger.exception(error)


def get_api_answer(timestamp):
    """Обращаемся к API."""
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={
                'from_date': timestamp
            })
        if response.status_code != HTTPStatus.OK:
            response.raise_for_status()
    except requests.exceptions.RequestException:
        logging.error('Что-то пошло не так на сервере..')
    return response.json()


def check_response(response):
    """Проверка ответа API."""
    if not isinstance(response, dict):
        logging.error('Тип данных ответа не соответсвует ожидаемому - (dict)')
        raise TypeError
    elif 'homeworks' not in response.keys():
        logging.error('В ответе не содержится ключ: <homeworks>')
        raise KeyError
    elif not isinstance(response['homeworks'], list):
        logging.error(
            'Содержимое ответа не соответсвует ожидаемому типу - (list)')
        raise TypeError
    elif len(response.get('homeworks')) == 0:
        logging.debug('Обновлений домашки нет')
    else:
        return response.get('homeworks')[0]


def parse_status(homework):
    """Статус домашней работы."""
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS.keys():
        raise NameError('Это невалидный статус домашней работы!')
    try:
        homework_name = homework['homework_name']
    except Exception:
        logger.exception('Ключ <homework_name> не найден.')
    finally:
        verdict = HOMEWORK_VERDICTS[homework_status]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            check_tokens()
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if homework is not None:
                status = parse_status(homework)
                send_message(bot, status)
            timestamp = response.get('current_date')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
