# Этот файл должен быть скопирован в WSGI конфигурацию вашего PythonAnywhere приложения
# Обычно он находится в: /var/www/yourusername_pythonanywhere_com_wsgi.py

import sys
import os

# Добавляем путь к папке проекта
path = '/home/yourusername/Paybot/paytonbot'  # Замените на ваш путь
if path not in sys.path:
    sys.path.append(path)

# Загружаем переменные окружения
from dotenv import load_dotenv
load_dotenv(os.path.join(path, '.env'))

# Импортируем Flask приложение
from webhook import app as application 