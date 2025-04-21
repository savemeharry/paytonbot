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
    logger.info("ENTERING init_db")
    # Получаем URL базы данных и убеждаемся, что драйвер асинхронный
    db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///bot_database.db")
    logger.info(f"Using database URL (type: {type(db_url)}): {db_url[:db_url.find(':')] + '://...elided.../' + db_url.split('/')[-1] if db_url else 'None'}")
    # Заменяем обычный SQLite на асинхронный SQLite, если нужно
    if db_url and db_url.startswith("sqlite:///"):
        db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
        logger.info(f"Adjusted SQLite URL: {db_url}")
    
    if not db_url:
         logger.error("DATABASE_URL is not set!")
         raise ValueError("DATABASE_URL environment variable is not set.")

    logger.info("Creating async engine...")
    engine = create_async_engine(
        db_url, 
        echo=False, 
        pool_timeout=30
    )
    logger.info("Async engine created.")
    
    logger.info("Connecting to database and creating tables (if needed)...")
    async with engine.begin() as conn:
        logger.info("Connection established. Running create_all...")
        # Create tables if they don't exist
        await conn.run_sync(Base.metadata.create_all)
        logger.info("create_all finished.")
    
    logger.info("Creating session factory...")
    session_factory = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    logger.info("Session factory created.")
    
    logger.info("EXITING init_db")
    return session_factory, engine

# Настраиваем приложение
async def on_startup():
    logger.info("ENTERING on_startup")
    try:
        logger.info("Calling init_db...")
        session_factory, engine = await init_db()
        logger.info("init_db finished successfully.")
        
        # Устанавливаем сессию и токен платежей
        logger.info("Setting dp values (session_factory, payment_token, engine)...")
        dp["session_factory"] = session_factory
        dp["payment_provider_token"] = os.getenv("PAYMENT_PROVIDER_TOKEN")
        dp["engine"] = engine
        logger.info("dp values set.")
        
        # Регистрируем обработчики
        logger.info("Registering handlers...")
        register_all_handlers(dp)
        logger.info("Handlers registered.")
        
        # Настраиваем планировщик
        logger.info("Setting up scheduler...")
        global scheduler
        scheduler = setup_scheduler(bot, session_factory)
        logger.info("Scheduler set up.")
        
        # Автоматически настраиваем webhook для Render
        try:
            logger.info("Setting up webhook...")
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
            logger.info(f"Webhook setup attempt finished. Result: {result}")
        except Exception as e:
            logger.error(f"Ошибка при установке webhook: {e}", exc_info=True)
        
        logger.info("Bot startup process nearly complete.")
        
    except Exception as e:
        logger.error(f"CRITICAL ERROR during on_startup: {e}", exc_info=True)
        # Важно выбросить исключение, чтобы loop_task завершилась с ошибкой
        raise 
        
    logger.info("EXITING on_startup successfully")
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

# # Запуск фоновой задачи для event loop (УДАЛЕНО)
# def run_event_loop():
#     try:
#         loop.run_forever()
#     except KeyboardInterrupt:
#         pass
#     finally:
#         loop.run_until_complete(loop.shutdown_asyncgens())
#         loop.close()

# # Инициализируем диспетчер в новом цикле событий (УДАЛЕНО)
# asyncio.set_event_loop(loop)
# loop_task = loop.create_task(on_startup())

# # Запускаем фоновую задачу для event loop (УДАЛЕНО)
# import threading
# threading.Thread(target=run_event_loop, daemon=True).start()

# # Global flag instead of storing the result (УДАЛЕНО)
# is_dp_initialized_successfully = None # None: Unknown, True: Success, False: Failed

# def ensure_dp_initialized(): (УДАЛЕНО)
#     """Check initialization status without blocking excessively"""
#     # ... (весь код функции удален)

# --- Новая синхронная инициализация при старте воркера --- 
try:
    logger.info("Starting synchronous initialization via asyncio.run(on_startup())...")
    # Запускаем on_startup синхронно. Это заполнит глобальный dp.
    asyncio.run(on_startup())
    logger.info("Synchronous initialization finished successfully.")
except Exception as init_error:
    logger.critical(f"CRITICAL: Failed synchronous initialization: {init_error}", exc_info=True)
    # Если инициализация не удалась, приложение, вероятно, не сможет работать.
    # Можно либо выйти, либо оставить как есть, но бот не будет работать.
    # raise SystemExit("Bot initialization failed") # Раскомментируйте, чтобы остановить Gunicorn при ошибке
# ----------------------------------------------------------

# Функция для синхронного вызова корутины (НЕ ИСПОЛЬЗУЕТСЯ БОЛЬШЕ, можно удалить позже)
# def run_sync(coroutine):
#     """Synchronously run a coroutine in the event loop"""
#     try:
#         # Используем текущий event loop
#         current_loop = asyncio.get_event_loop()
#         future = asyncio.run_coroutine_threadsafe(coroutine, current_loop)
#         return future.result(timeout=10)  # 10 second timeout
#     except Exception as e:
#         logger.error(f"Ошибка при синхронном выполнении корутины: {e}", exc_info=True)
#         return None

# # Синхронные функции для обработки сообщений (НЕ ИСПОЛЬЗУЮТСЯ БОЛЬШЕ, можно удалить позже)
# def process_start_command(user_id, message_obj):
# ...

# Эндпоинт для вебхука
@app.route('/webhook/' + os.getenv("BOT_TOKEN"), methods=['POST'])
def webhook():
    # Используем напрямую глобальный dp, который должен быть инициализирован
    # logger.info(f"Using dispatcher: {dp}") # Можно раскомментировать для отладки
    
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        
        try:
            import json
            json_data = json.loads(json_string)
            # logger.info(f"Received webhook: {json_data.get('update_id')} - type: {list(json_data.keys())}") # Отладочный лог
            
            update = types.Update(**json_data)
            
            # logger.info(f"Event loop status: running={asyncio.get_event_loop().is_running()}") # Отладочный лог

            # Передаем ВСЕ обновления в диспетчер для асинхронной обработки
            try:
                # Получаем текущий event loop для run_coroutine_threadsafe
                current_loop = asyncio.get_event_loop()
                if not current_loop.is_running():
                    logger.error("CRITICAL: Event loop obtained by get_event_loop() is not running!")
                    # Попытка запустить основной цикл, если еще не запущен (экспериментально)
                    # Это может не работать корректно с Gunicorn
                    # threading.Thread(target=current_loop.run_forever, daemon=True).start()
                    # logger.info("Attempted to start the obtained event loop in a new thread.")
                    # return Response(status=500) # Возвращаем ошибку, т.к. обработка невозможна
                    
                future = asyncio.run_coroutine_threadsafe(
                    dp.process_update(update),
                    current_loop
                )
                # Не ждем результата future.result()
                # logger.info(f"Update {json_data.get('update_id')} passed to dispatcher.") # Отладочный лог
            except RuntimeError as e:
                 if "cannot schedule new futures after shutdown" in str(e):
                      logger.warning(f"Event loop seems to be shutting down. Could not process update {json_data.get('update_id')}.")
                 elif "no running event loop" in str(e):
                      logger.error("CRITICAL: No running event loop found to schedule update processing!")
                 else:
                      logger.error(f"RuntimeError submitting update {json_data.get('update_id')} to dispatcher: {e}", exc_info=True)
            except Exception as e:
                logger.error(f"Error submitting update {json_data.get('update_id')} to dispatcher: {e}", exc_info=True)
            
            return Response(status=200) # Отвечаем Telegram сразу

        except json.JSONDecodeError as e:
            logger.error(f"Ошибка декодирования JSON: {e}", exc_info=True)
            return Response(status=400)
        except Exception as e:
            # Log the error but still return 200 to Telegram
            logger.error(f"Error processing update: {e}", exc_info=True)
            # Всегда отвечаем 200, чтобы Telegram не повторял отправку
            return Response(status=200) 
    else:
        return Response(status=403)

# Функция для отправки сообщений напрямую через API (на случай сбоев)
def send_direct_message(chat_id, text, parse_mode='HTML', reply_markup=None):
    """Send message directly via Telegram API"""
    try:
        bot_token = os.getenv("BOT_TOKEN")
        send_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        payload = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': parse_mode
        }
        
        if reply_markup:
            payload['reply_markup'] = reply_markup
            
        response = requests.post(send_url, json=payload)
        logger.info(f"Прямой ответ отправлен: {response.json()}")
        return response.json()
    except Exception as e:
        logger.error(f"Ошибка при отправке прямого сообщения: {e}", exc_info=True)
        return None

# Эндпоинт для проверки работы приложения
@app.route('/')
def index():
    # Просто возвращаем статус, т.к. инициализация должна была пройти при старте
    # Проверять dp здесь не очень надежно
    return 'Бот запущен. Проверьте его работоспособность командой /start.'

# Для запуска приложения
if __name__ == '__main__':
    # Получаем порт из переменной окружения для Render
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True) 