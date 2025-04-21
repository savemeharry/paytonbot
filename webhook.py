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
        logger.info(f"Dispatcher object ID after registration: {id(dp)}")
        
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

# Запуск фоновой задачи для event loop (ВОЗВРАЩЕНО)
def run_event_loop():
    try:
        logger.info("Background event loop thread starting...")
        asyncio.set_event_loop(loop)
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("Background event loop stopping...")
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
        logger.info("Background event loop stopped.")

# Инициализируем диспетчер в новом цикле событий (ВОЗВРАЩЕНО)
loop_task = loop.create_task(on_startup())

# Запускаем фоновую задачу для event loop (ВОЗВРАЩЕНО)
import threading
loop_thread = threading.Thread(target=run_event_loop, daemon=True)
loop_thread.start()

# Добавляем небольшую паузу, чтобы цикл событий успел запуститься (ВОЗВРАЩЕНО И УВЕЛИЧЕНО)
import time
time.sleep(2)

# Global flag instead of storing the result (ВОЗВРАЩЕНО)
is_dp_initialized_successfully = None # None: Unknown, True: Success, False: Failed

# Функция проверки инициализации (ВОЗВРАЩЕНА)
def ensure_dp_initialized():
    """Check initialization status without blocking excessively"""
    global is_dp_initialized_successfully, loop_task, dp # Added dp here

    if is_dp_initialized_successfully is True:
        # logger.debug("Initialization previously succeeded.") # Optional: debug log
        return dp # Already confirmed success

    if is_dp_initialized_successfully is False:
        logger.warning("Initialization previously failed. Using potentially uninitialized global dp.")
        return dp # Already confirmed failure

    # State is still None (Unknown)
    # logger.info("Checking initialization status...") # Уменьшаем количество логов

    if loop_task.done():
        logger.info("Initialization task loop_task has finished.")
        try:
            exception = loop_task.exception()
            if exception:
                logger.error(f"Initialization task failed: {exception}", exc_info=exception)
                is_dp_initialized_successfully = False # Mark as failed
                return dp
            else:
                # Task finished without error
                logger.info("Initialization task completed successfully.")
                is_dp_initialized_successfully = True # Mark as success
                return dp
        except asyncio.CancelledError:
             logger.warning("Initialization task was cancelled.")
             is_dp_initialized_successfully = False # Treat as failure
             return dp
        except asyncio.InvalidStateError:
             logger.warning("Could not get exception status from loop_task even though it's done. Retrying check later.")
             return dp
        except Exception as e:
             logger.error(f"Unexpected error checking loop_task exception: {e}", exc_info=True)
             is_dp_initialized_successfully = False # Assume failure
             return dp
    else:
        logger.info("Initialization task loop_task is still running...")
        return dp

# Эндпоинт для вебхука
@app.route('/webhook/' + os.getenv("BOT_TOKEN"), methods=['POST'])
def webhook():
    # Проверяем статус инициализации (ВОЗВРАЩЕНО)
    dispatcher = ensure_dp_initialized()
    if not dispatcher:
        logger.error("Dispatcher is None after ensure_dp_initialized, returning 500")
        return Response("Bot initialization error", status=500)
    
    logger.info(f"Using dispatcher object ID in webhook: {id(dispatcher)}")
    
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        
        try:
            import json
            json_data = json.loads(json_string)
            update = types.Update(**json_data)
            
            # Log important update info for debugging
            update_type = None
            if update.message:
                update_type = f"message from {update.message.from_user.id}"
                if update.message.text:
                    update_type += f" with text: {update.message.text}"
            elif update.callback_query:
                update_type = f"callback_query with data: {update.callback_query.data}"
            
            logger.info(f"Processing update {update.update_id} of type: {update_type}")
            
            # Передаем ВСЕ обновления в диспетчер для асинхронной обработки
            try:
                # Используем глобальный loop из фонового потока
                future = asyncio.run_coroutine_threadsafe(
                    dispatcher.process_update(update),  # Process directly instead of using wrapper
                    loop  # Используем глобальный loop
                )
                
                # Try to get result with a short timeout for better error reporting
                try:
                    future.result(0.1)  # Don't block too long in case of issues
                    logger.info(f"Update {update.update_id} successfully processed")
                except asyncio.TimeoutError:
                    # This is expected, we don't need to wait for complete processing
                    logger.info(f"Update {update.update_id} processing continues in background")
                except Exception as e:
                    logger.error(f"Error in update {update.update_id} processing: {e}", exc_info=True)
                    
            except RuntimeError as e:
                if "cannot schedule new futures after shutdown" in str(e):
                    logger.warning(f"Event loop seems to be shutting down. Could not process update {update.update_id}.")
                else:
                    logger.error(f"RuntimeError submitting update {update.update_id} to dispatcher: {e}", exc_info=True)
                
                # Fallback: Try direct message sending for commands
                if update.message and update.message.text and update.message.text.startswith('/'):
                    chat_id = update.message.chat.id
                    send_direct_message(chat_id, "Извините, бот перезагружается. Попробуйте позже.")
                    logger.info(f"Sent fallback message to {chat_id}")
                    
            except Exception as e:
                logger.error(f"Error submitting update {update.update_id} to dispatcher: {e}", exc_info=True)
            
            return Response(status=200)  # Отвечаем Telegram сразу

        except json.JSONDecodeError as e:
            logger.error(f"Ошибка декодирования JSON: {e}", exc_info=True)
            return Response(status=400)
        except Exception as e:
            logger.error(f"Error processing update: {e}", exc_info=True)
            return Response(status=200) 
    else:
        return Response(status=403)

# Эндпоинт для проверки работы приложения
@app.route('/')
def index():
    # Проверяем статус инициализации
    if is_dp_initialized_successfully is True:
        return 'Бот инициализирован и работает! Webhook активен.'
    elif is_dp_initialized_successfully is False:
         return 'Ошибка инициализации бота. Проверьте логи.'
    else:
         return 'Бот инициализируется... Пожалуйста, подождите.'

# Добавляем отладочный эндпоинт для прямой отправки сообщений
@app.route('/send_test/<string:chat_id>')
def send_test_message(chat_id):
    try:
        result = send_direct_message(chat_id, "Тестовое сообщение через прямой API вызов")
        return f"Сообщение отправлено: {result}"
    except Exception as e:
        logger.error(f"Error in test endpoint: {e}", exc_info=True)
        return f"Ошибка: {str(e)}"

# Эндпоинт для проверки статуса бота
@app.route('/status')
def status():
    try:
        dp_status = "Инициализирован" if is_dp_initialized_successfully else "Не инициализирован"
        loop_status = "Работает" if loop and loop.is_running() else "Не работает"
        handlers_count = len(dp.message_handlers.handlers) if dp and hasattr(dp, 'message_handlers') else 0
        
        status_info = {
            "bot_name": bot.username if hasattr(bot, 'username') else "Unknown",
            "dp_initialized": is_dp_initialized_successfully,
            "loop_running": loop and loop.is_running(),
            "handlers_registered": handlers_count,
            "dp_data_keys": list(dp.data.keys()) if dp and hasattr(dp, 'data') else [],
            "webhook_url": f"{os.environ.get('RENDER_EXTERNAL_URL', 'Unknown')}/webhook/{os.getenv('BOT_TOKEN')}"
        }
        
        import json
        return Response(json.dumps(status_info, indent=2), mimetype='application/json')
    except Exception as e:
        logger.error(f"Error in status endpoint: {e}", exc_info=True)
        return f"Error getting status: {str(e)}"

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

# Для запуска приложения
if __name__ == '__main__':
    # Получаем порт из переменной окружения для Render
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True) 