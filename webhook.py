from flask import Flask, request, Response
import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
import os
from dotenv import load_dotenv
import requests

from app.models.base import Base
from app.handlers import register_all_handlers
from app.services.scheduler import setup_scheduler
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаем Flask приложение
app = Flask(__name__)

# Инициализируем бота
bot = Bot(token=os.getenv("BOT_TOKEN"))
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Глобальный диспетчер для доступа из webhook обработчика
global_dp = None

# Настройка базы данных
async def init_db():
    engine = create_async_engine(
        os.getenv("DATABASE_URL", "sqlite+aiosqlite:///bot_database.db"), 
        echo=False
    )
    
    async with engine.begin() as conn:
        # Create tables if they don't exist
        await conn.run_sync(Base.metadata.create_all)
    
    session_factory = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    return session_factory

# Настраиваем приложение
async def on_startup():
    session_factory = await init_db()
    
    # Устанавливаем сессию и токен платежей
    dp["session_factory"] = session_factory
    dp["payment_provider_token"] = os.getenv("PAYMENT_PROVIDER_TOKEN")
    
    # Регистрируем обработчики
    register_all_handlers(dp)
    
    # Настраиваем планировщик
    setup_scheduler(bot, session_factory)
    
    # Автоматически настраиваем webhook для Render
    try:
        # Получаем URL приложения - сначала ищем Render URL, потом пробуем PythonAnywhere
        app_url = os.environ.get('RENDER_EXTERNAL_URL', 'https://paytonbot.onrender.com')
        bot_token = os.getenv("BOT_TOKEN")
        webhook_url = f"{app_url}/webhook/{bot_token}"
        
        logger.info(f"Настраиваем webhook на {webhook_url}")
        response = requests.get(f"https://api.telegram.org/bot{bot_token}/setWebhook?url={webhook_url}")
        result = response.json()
        if result.get("ok"):
            logger.info(f"Webhook успешно установлен на {webhook_url}")
        else:
            logger.error(f"Ошибка при установке webhook: {result}")
    except Exception as e:
        logger.error(f"Ошибка при установке webhook: {e}")
    
    logger.info("Bot started with webhook!")
    
    global global_dp
    global_dp = dp
    
    return dp

# Инициализируем диспетчер в новом цикле событий
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_until_complete(on_startup())

# Эндпоинт для вебхука
@app.route('/webhook/' + os.getenv("BOT_TOKEN"), methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = types.Update.to_object(json_string)
        
        # Обработка обновления в новом потоке
        asyncio.run_coroutine_threadsafe(
            global_dp.process_update(update),
            loop
        )
        
        return Response(status=200)
    else:
        return Response(status=403)

# Эндпоинт для проверки работы приложения
@app.route('/')
def index():
    return 'Бот работает! Webhook активен.'

# Для запуска приложения
if __name__ == '__main__':
    # Получаем порт из переменной окружения для Render
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port) 