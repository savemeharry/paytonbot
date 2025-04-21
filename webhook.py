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

# Глобальная переменная для хранения количества попыток инициализации
global init_attempts
init_attempts = 0

def ensure_dp_initialized():
    """Make sure dispatcher is initialized before handling requests"""
    global initialized_dp, loop_task
    
    if initialized_dp:
        return initialized_dp

    logger.info("Проверяем инициализацию диспетчера...")

    if loop_task.done():
        logger.info("Задача инициализации loop_task завершена.")
        try:
            # Проверяем, не было ли ошибки в самой задаче
            exception = loop_task.exception()
            if exception:
                logger.error(f"Ошибка в задаче инициализации on_startup: {exception}", exc_info=exception)
                logger.warning("Используем глобальный dp из-за ошибки инициализации.")
                initialized_dp = dp # Можно считать инициализацию проваленной
                return dp
            else:
                # Ошибки не было, получаем результат
                initialized_dp = loop_task.result()
                logger.info(f"Диспетчер успешно инициализирован (задача была завершена): {initialized_dp}")
                return initialized_dp
        except asyncio.InvalidStateError:
            logger.warning("Не удалось получить результат loop_task, хотя она помечена как done. Используем глобальный dp.")
            initialized_dp = dp
            return dp
        except Exception as e:
             logger.error(f"Неожиданная ошибка при проверке завершенной loop_task: {e}", exc_info=True)
             initialized_dp = dp
             return dp
    else:
        logger.info("Задача инициализации loop_task еще не завершена. Ожидаем...")
        # Создаем корутину, которая просто ждет исходную задачу
        async def _wait_for_task(task):
            return await task

        future = asyncio.run_coroutine_threadsafe(_wait_for_task(loop_task), loop)
        try:
            # Ждем завершения исходной задачи с таймаутом
            initialized_dp = future.result(timeout=10) 
            logger.info(f"Диспетчер успешно инициализирован через ожидание: {initialized_dp}")
            return initialized_dp
        except TimeoutError:
             logger.warning("Таймаут (10с) ожидания инициализации диспетчера. Используем глобальный dp.")
             # Не устанавливаем initialized_dp, чтобы пробовать снова при след. запросе
             return dp # Возвращаем пока глобальный
        except Exception as e:
             logger.error(f"Ошибка при ожидании инициализации через run_coroutine_threadsafe: {e}", exc_info=True)
             # Проверим, не завершилась ли сама задача с ошибкой за это время
             if loop_task.done() and loop_task.exception():
                 logger.error(f"Исходная задача инициализации loop_task завершилась с ошибкой: {loop_task.exception()}", exc_info=loop_task.exception())
             logger.warning("Используем глобальный dp из-за ошибки ожидания.")
             # Не устанавливаем initialized_dp
             return dp # Возвращаем пока глобальный

# Функция для синхронного вызова корутины
def run_sync(coroutine):
    """Synchronously run a coroutine in the event loop"""
    try:
        future = asyncio.run_coroutine_threadsafe(coroutine, loop)
        return future.result(timeout=10)  # 10 second timeout
    except Exception as e:
        logger.error(f"Ошибка при синхронном выполнении корутины: {e}", exc_info=True)
        return None

# Синхронные функции для обработки сообщений с помощью обработчиков
def process_start_command(user_id, message_obj):
    """Process /start command"""
    from app.handlers.base import cmd_start
    return run_sync(cmd_start(message_obj))

def process_help_command(user_id, message_obj):
    """Process /help command"""
    from app.handlers.base import cmd_help
    return run_sync(cmd_help(message_obj))

def process_mysubscriptions_command(user_id, message_obj):
    """Process /mysubscriptions command"""
    from app.handlers.base import cmd_my_subscriptions
    return run_sync(cmd_my_subscriptions(message_obj))

# Эндпоинт для вебхука
@app.route('/webhook/' + os.getenv("BOT_TOKEN"), methods=['POST'])
def webhook():
    dispatcher = ensure_dp_initialized()
    logger.info(f"Используем диспетчер: {dispatcher}")
    
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        
        try:
            import json
            # Правильно парсим JSON перед созданием объекта Update
            json_data = json.loads(json_string)
            logger.info(f"Получен webhook: {json_data.get('update_id')} - тип: {list(json_data.keys())}")

            # Создаем объект Update
            update = types.Update(**json_data)
            
            # Проверяем статус event loop (опционально, для отладки)
            logger.info(f"Статус event loop: работает={not loop.is_closed()}, "
                       f"количество задач={len(asyncio.all_tasks(loop) if hasattr(asyncio, 'all_tasks') else [])}")

            # Передаем ВСЕ обновления в диспетчер для асинхронной обработки
            # Не ждем результата future.result()
            try:
                future = asyncio.run_coroutine_threadsafe(
                    dispatcher.process_update(update),
                    loop
                )
                # future.result(timeout=10) # Убираем ожидание результата
                logger.info(f"Update {json_data.get('update_id')} передан в диспетчер.")
            except Exception as e:
                logger.error(f"Ошибка при передаче обновления {json_data.get('update_id')} в диспетчер: {e}", exc_info=True)
                # Можно добавить резервную отправку сообщения об ошибке, если необходимо
                # user_id = json_data.get('message', {}).get('from', {}).get('id') or \\
                #           json_data.get('callback_query', {}).get('from', {}).get('id')
                # if user_id:
                #     send_direct_message(user_id, "Произошла внутренняя ошибка при обработке вашего запроса.")
            
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