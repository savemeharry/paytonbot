from flask import Flask, request, Response
import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
import os
from dotenv import load_dotenv
import requests
import atexit
import time

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

# Shared objects
loop = asyncio.new_event_loop()
scheduler = None

# Настройка базы данных
async def init_db():
    # Получаем URL базы данных и убеждаемся, что драйвер асинхронный
    db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///bot_database.db")
    # Заменяем обычный SQLite на асинхронный SQLite, если нужно
    if db_url.startswith("sqlite:///"):
        db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
    
    engine = create_async_engine(
        db_url, 
        echo=False
    )
    
    async with engine.begin() as conn:
        # Create tables if they don't exist
        await conn.run_sync(Base.metadata.create_all)
    
    session_factory = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    return session_factory, engine

# Настраиваем приложение
async def on_startup():
    session_factory, engine = await init_db()
    
    # Устанавливаем сессию и токен платежей
    dp["session_factory"] = session_factory
    dp["payment_provider_token"] = os.getenv("PAYMENT_PROVIDER_TOKEN")
    dp["engine"] = engine
    
    # Регистрируем обработчики
    register_all_handlers(dp)
    
    # Настраиваем планировщик
    global scheduler
    scheduler = setup_scheduler(bot, session_factory)
    
    # Автоматически настраиваем webhook для Render
    try:
        # Получаем URL приложения из переменных окружения
        app_url = os.environ.get('RENDER_EXTERNAL_URL')
        if not app_url:
            app_url = os.environ.get('APP_URL', 'https://paytonbot.onrender.com')
            logger.warning(f"RENDER_EXTERNAL_URL not found, using fallback URL: {app_url}")
        
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
    
    return dp

# Cleanup function
async def on_shutdown():
    logger.info("Shutting down bot...")
    
    # Close storage
    await dp.storage.close()
    await dp.storage.wait_closed()
    
    # Close bot session
    await bot.session.close()
    
    # Stop scheduler if running
    if scheduler:
        scheduler.shutdown(wait=False)
    
    # Close database connection
    if "engine" in dp.data:
        await dp.data["engine"].dispose()
    
    logger.info("Bot shutdown complete")

# Register shutdown function
def shutdown_event():
    asyncio.run_coroutine_threadsafe(on_shutdown(), loop)
    loop.call_soon_threadsafe(loop.stop)

atexit.register(shutdown_event)

# Запуск фоновой задачи для event loop
def run_event_loop():
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()

# Инициализируем диспетчер в новом цикле событий
asyncio.set_event_loop(loop)
loop_task = loop.create_task(on_startup())
initialized_dp = None

# Запускаем фоновую задачу для event loop
import threading
threading.Thread(target=run_event_loop, daemon=True).start()

# Небольшая задержка для начала инициализации
time.sleep(1)

def ensure_dp_initialized():
    """Make sure dispatcher is initialized before handling requests"""
    global initialized_dp
    if initialized_dp is None:
        # Проверка, завершена ли задача
        if loop_task.done():
            # Если задача завершена с ошибкой, логируем и пробуем перезапустить
            if loop_task.exception():
                logger.error(f"Ошибка при инициализации бота: {loop_task.exception()}")
                # Перезапускаем задачу инициализации
                loop.create_task(on_startup())
                return dp
                
            # Если задача завершена успешно, получаем результат
            initialized_dp = loop_task.result()
        else:
            # Просто возвращаем глобальный диспетчер без ожидания
            # Это позволит быстрее отвечать на запросы
            return dp
    return initialized_dp

# Эндпоинт для вебхука
@app.route('/webhook/' + os.getenv("BOT_TOKEN"), methods=['POST'])
def webhook():
    dp = ensure_dp_initialized()
    
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        
        try:
            import json
            # Правильно парсим JSON перед созданием объекта Update
            json_data = json.loads(json_string)
            update = types.Update(**json_data)
            
            # Создаем задачу для обработки обновления
            # но не ждем ее завершения, чтобы не блокировать ответ
            future = asyncio.run_coroutine_threadsafe(
                dp.process_update(update),
                loop
            )
            
            # Не ждем выполнения будущего объекта
            # Это предотвратит таймауты в Gunicorn
            return Response(status=200)
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка декодирования JSON: {e}", exc_info=True)
            return Response(status=400)
        except Exception as e:
            # Log the error but still return 200 to Telegram
            logger.error(f"Error processing update: {e}", exc_info=True)
            return Response(status=200)
    else:
        return Response(status=403)

# Эндпоинт для проверки работы приложения
@app.route('/')
def index():
    # Ensure the bot is initialized, но без блокировки
    try:
        ensure_dp_initialized()
        return 'Бот работает! Webhook активен.'
    except Exception as e:
        logger.error(f"Ошибка при инициализации бота: {e}", exc_info=True)
        return 'Бот пытается запуститься. Проверьте логи.'

# Для запуска приложения
if __name__ == '__main__':
    # Получаем порт из переменной окружения для Render
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True) 