import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import ServerReject, StatusNotOk

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TOKENS = ['PRACTICUM_TOKEN', 'TELEGRAM_CHAT_ID', 'TELEGRAM_TOKEN']

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

API_ERROR_KEYS = ['error', 'code']
VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}
VERDICT = 'Изменился статус проверки работы "{name}". {verdict}'
MESSAGE_SENT = 'Успешная отправка сообщения в Telegram: "{message}"'
MESSAGE_UNSENT = 'Сбой при отправке сообщения: "{message}", ошибка: {error}'
CONNECTION_ERROR = (
    'Ошибка при запросе к API: '
    'Текст ошибки: {error}, '
    'url = {url}, '
    'headers = {headers}, '
    'параметры = {params}, '
)
SERVER_REJECT = (
    'Отказ сервера: {error}, '
    'ключ ошибки: {key}, '
    'url = {url}, '
    'headers = {headers}, '
    'параметры = {params}, '
)
WRONG_STATUS_CODE = (
    'Код доступа отличен от 200, код: {status_code}, '
    'url = {url}, '
    'headers = {headers}, '
    'параметры = {params}, '
)
RESPONSE_TYPE_ERROR = 'В ответе сервера не словарь, а {type}'
RESPONSE_KEY_ERROR = 'Не найден ключ homework'
HOMEWORK_KEY_ERROR = 'Под ключом homework не список, а {type}'
UNKNOWN_STATUS = 'Неизвестный статус: {status}'
TOKEN_MISSING = (
    'Отсутствует(-ют) обязательная(-ые) переменная(-ые) окружения: {tokens}'
)
STATUS_UNCHANGED = 'Статус работы не изменился'
FAILURE = 'Сбой в работе программы: {error}'


def send_message(bot, message):
    """Функция отправляет сообщение в телеграмм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.info(MESSAGE_SENT.format(message=message))
        return True
    except Exception as error:
        logging.exception(MESSAGE_UNSENT.format(message=message, error=error))
        return False


def get_api_answer(current_timestamp):
    """
    Функция делает запрос к эндпоинту API.
    Проверяет доступность API.
    В случае успеха преобразует полученные данные
    из JSON в типы данных python
    """
    request_fields = dict(
        url=ENDPOINT,
        headers=HEADERS,
        params={'from_date': current_timestamp}
    )
    try:
        response = requests.get(**request_fields)
    except requests.exceptions.RequestException as error:
        raise ConnectionError(
            CONNECTION_ERROR.format(error=error, **request_fields)
        )
    reply = response.json()
    for error in API_ERROR_KEYS:
        if error in reply:
            raise ServerReject(
                SERVER_REJECT.format(
                    error=reply[error], key=error, **request_fields
                )
            )
    if response.status_code != HTTPStatus.OK:
        raise StatusNotOk(
            WRONG_STATUS_CODE.format(
                status_code=response.status_code, **request_fields
            )
        )
    return reply


def check_response(response):
    """
    Функция проверяет ответ API на корректность.
    В случае соответствия ожиданиям возвращает список работ.
    """
    if not isinstance(response, dict):
        raise TypeError(RESPONSE_TYPE_ERROR.format(type=type(response)))
    if 'homeworks' not in response:
        raise KeyError(RESPONSE_KEY_ERROR)
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(HOMEWORK_KEY_ERROR.format(type=type(homeworks)))
    return homeworks


def parse_status(homework):
    """
    Функция извлекает из полученной информации статус работы.
    Проверяет соответствие типов данных ключей.
    В случае успеха возвращает строку с вердиктом по работе.
    """
    name = homework['homework_name']
    status = homework['status']
    if status not in VERDICTS:
        raise ValueError(UNKNOWN_STATUS.format(status=status))
    return VERDICT.format(name=name, verdict=VERDICTS[status])


def check_tokens():
    """
    Проверяет доступность переменных окружения.
    Если отсутствует хотя бы одна переменная окружения — функция
    в False, иначе — True.
    """
    tokens = [name for name in TOKENS if globals()[name] is None]
    if tokens:
        logging.critical(TOKEN_MISSING.format(tokens=tokens))
    return not tokens


def main():
    """
    Основная логика работы бота.
    Делает запрос к API.
    Проверяет ответ.
    Получает статус работы и отправляет сообщение в Telegram.
    Цикл повторяется спустя заданное время
    """
    if not check_tokens():
        raise ValueError
    current_timestamp = int(time.time())
    old_message = ''
    error_message = ''
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            message = parse_status(homeworks)
            if old_message != message and send_message(bot, message):
                old_message = message
                current_timestamp = response.get(
                    'current_date', current_timestamp
                )
            else:
                logging.info(STATUS_UNCHANGED)

        except Exception as error:
            logging.error(FAILURE.format(error=error))
            message = FAILURE.format(error=error)
            if error_message != message and send_message(bot, message):
                error_message = message
        time.sleep(RETRY_TIME)


if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s [%(levelname)s] %(message)s',
        level=logging.INFO,
        handlers=(
            logging.FileHandler(filename=__file__ + '.log', mode='a'),
            logging.StreamHandler(sys.stdout))
    )
    main()
