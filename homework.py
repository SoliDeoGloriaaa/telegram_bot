import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import NotHTTPResponseOK

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
    return all([PRACTICUM_TOKEN or TELEGRAM_TOKEN or TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправляем сообщение."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Сообщение отправленно успешно. Ура!')
    except telegram.TelegramError:
        logger.error('Сообщение не отправилось =(')


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
        logger.error('Что-то пошло не так на сервере..')
        raise NotHTTPResponseOK('Ошибка от API')
    try:
        json_response = response.json()
    except requests.JSONDecodeError:
        logger.exception('Ошибка, ответ не преобразован в json формат!')
    return json_response


def check_response(response):
    """Проверка ответа API."""
    if not isinstance(response, dict):
        logger.error('Тип данных ответа не соответсвует ожидаемому - (dict)')
        raise TypeError(
            'Тип данных ответа не соответсвует ожидаемому - (dict)')
    elif 'homeworks' not in response:
        logger.error('В ответе не содержится ключ: <homeworks>')
        raise KeyError('В ответе не содержится ключ: <homeworks>')
    elif 'current_date' not in response:
        logger.error('В ответе не содержится ключ: <current_date>')
        raise KeyError('В ответе не содержится ключ: <current_date>')
    elif not isinstance(response['homeworks'], list):
        logger.error(
            'Содержимое ответа не соответсвует ожидаемому типу - (list)')
        raise TypeError(
            'Содержимое ответа не соответсвует ожидаемому типу - (list)')
    elif len(response.get('homeworks')) == 0:
        logger.debug('Обновлений домашки нет')
    else:
        return response.get('homeworks')[0]


def parse_status(homework):
    """Статус домашней работы."""
    try:
        homework_status = homework['status']
    except KeyError:
        logger.exception('Ключь <status> не был найден!')
    if homework_status not in HOMEWORK_VERDICTS:
        raise NameError('Это невалидный статус домашней работы!')
    try:
        homework_name = homework['homework_name']
    except KeyError:
        logger.exception('Ключ <homework_name> не найден.')
    finally:
        verdict = HOMEWORK_VERDICTS[homework_status]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_status_homework = ''
    while True:
        try:
            if not check_tokens():
                logger.critical(
                    'Отсутствуют переменные окружения')
                sys.exit(
                    'Завершение работы. Отсутствуют переменные окружения!'
                )
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if homework is not None:
                status = parse_status(homework)
                if status != last_status_homework:
                    send_message(bot, status)
                    logger.debug('Новый статус отправлен =)')
                    last_status_homework = status
                else:
                    logger.debug('Статус остался прежним =(')
            timestamp = response.get('current_date')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
