#!/usr/bin/env python
import requests
import os
from dotenv import load_dotenv
import sys
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Загружаем переменные окружения
load_dotenv()

def set_webhook():
    """Устанавливает вебхук для Telegram бота"""
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    # Определяем URL хостинга (Render или PythonAnywhere)
    if os.environ.get('RENDER_EXTERNAL_URL'):
        # Если запущено на Render
        WEBHOOK_URL = f"{os.environ.get('RENDER_EXTERNAL_URL')}/webhook/{BOT_TOKEN}"
    else:
        # Пытаемся определить из переменной окружения или по умолчанию для Render
        WEBHOOK_URL = f"https://paytonbot.onrender.com/webhook/{BOT_TOKEN}"
    
    # Устанавливаем вебхук
    logger.info(f"Устанавливаем webhook на {WEBHOOK_URL}")
    response = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={WEBHOOK_URL}")
    result = response.json()
    
    if result.get("ok"):
        logger.info("Webhook успешно установлен!")
        logger.info(f"Описание: {result.get('description')}")
    else:
        logger.error(f"Ошибка при установке webhook: {result}")
    
    return result

def get_webhook_info():
    """Получает информацию о текущем вебхуке"""
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    logger.info("Получаем информацию о webhook")
    response = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo")
    result = response.json()
    
    if result.get("ok"):
        logger.info("Информация о webhook получена:")
        webhook_info = result.get("result", {})
        logger.info(f"URL: {webhook_info.get('url')}")
        logger.info(f"Ожидает обновлений: {webhook_info.get('pending_update_count')}")
        logger.info(f"Последняя ошибка: {webhook_info.get('last_error_message', 'Нет ошибок')}")
    else:
        logger.error(f"Ошибка при получении информации о webhook: {result}")
    
    return result

def delete_webhook():
    """Удаляет вебхук"""
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    logger.info("Удаляем webhook")
    response = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook")
    result = response.json()
    
    if result.get("ok"):
        logger.info("Webhook успешно удален!")
    else:
        logger.error(f"Ошибка при удалении webhook: {result}")
    
    return result

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Управление webhook для Telegram бота')
    parser.add_argument('action', choices=['set', 'get', 'delete'], 
                        help='Действие: set - установить, get - получить информацию, delete - удалить')
    
    args = parser.parse_args()
    
    if args.action == 'set':
        set_webhook()
    elif args.action == 'get':
        get_webhook_info()
    elif args.action == 'delete':
        delete_webhook() 