import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import ApiError, EmptyList

load_dotenv()
logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(message)s',
    level=logging.INFO)
logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler(sys.stdout))

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 5
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Функция отправляет сообщение в телеграмм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.info('Успешная отправка сообщения в Telegram')
    except Exception as error:
        logging.error(f'Сбой при отправке сообщения: {error}')


def get_api_answer(current_timestamp):
    """
    Функция делает запрос к эндпоинту API.
    Проверяет доступность API.
    В случае успеха преобразует полученные данные
    из JSON в типы данных python
    """
    timestamp = current_timestamp or int(time.time()) - 10000000
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException:
        logging.error('Ошибка при запросе к API')
        raise ApiError('Ошибка при запросе к Api')


def check_response(response):
    """
    Функция проверяет ответ API на корректность.
    В случае соответствия ожиданиям возвращает список работ.
    """
    if not isinstance(response, dict):
        logging.error('В ответе сервера не словарь')
        raise TypeError('В ответе сервера не словарь')
    homework = response['homeworks']
    if homework is None:
        logging.error('В ответе нет данных под ключом homework')
        raise NameError('В ответе нет данных под ключом homework')
    if not isinstance(homework, list):
        logging.error('Под ключом homework не список')
        raise TypeError('Под ключом homework не список')
    if len(homework) == 0:
        logging.error('Список домашних заданий пуст')
        raise EmptyList('Список домашних заданий пуст')
    return homework[0]


def parse_status(homework):
    """
    Функция извлекает из полученной информации статус работы.
    Проверяет соответствие типов данных ключей.
    В случае успеха возвращает строку с вердиктом по работе.
    """
    if 'homework_name' not in homework:
        logging.error('Не найден ключ homework_name')
        raise KeyError('Не найден ключ homework_name')
    if 'status' not in homework:
        raise KeyError('Не найден ключ status')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_STATUSES:
        logging.error(f'Неизвестный статус: {homework_status}')
        raise ValueError(f'Неизвестный статус: {homework_status}')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """
    Проверяет доступность переменных окружения.
    Если отсутствует хотя бы одна переменная окружения — функция
    в False, иначе — True.
    """
    values = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    for name, value in values.items():
        if value is None:
            logging.critical(
                f'Отсутствует обязательная переменная окружения: {name}'
                ' Задача остановлена.')
            return False
    return True


def main():
    """
    Основная логика работы бота.
    Делает запрос к API.
    Проверяет ответ.
    Получает статус работы и отправляет сообщение в Telegram.
    Цикл повторяется спустя заданное время
    """
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time()) - 10000000
    old_message = ''
    error_message = ''
    check_tokens()
    while check_tokens():
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            message = parse_status(homework)
            if old_message != message:
                send_message(bot, message)
                old_message = message
            else:
                logging.debug('Статус работы не изменился')
            current_timestamp = int(time.time()) - 10000000
            time.sleep(RETRY_TIME)

        except Exception as error:
            logging.error(f'Сбой в работе программы: {error}')
            message = f'Сбой в работе программы: {error}'
            if error_message != message:
                send_message(bot, message)
                error_message = message
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
