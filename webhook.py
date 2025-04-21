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
import json

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
    # Проверяем статус инициализации
    dispatcher = ensure_dp_initialized()
    if not dispatcher:
        logger.error("Dispatcher is None after ensure_dp_initialized, returning 500")
        return Response("Bot initialization error", status=500)
    
    logger.info(f"Using dispatcher object ID in webhook: {id(dispatcher)}")
    
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        
        try:
            json_data = json.loads(json_string)
            
            # Log the raw update for debugging
            logger.info(f"[DEBUG] Raw update: {json_string[:200]}...")
            
            # Create the Update object
            update = types.Update(**json_data)
            
            # Log important update info for debugging
            update_type = "unknown"
            chat_id = None
            
            if update.message:
                update_type = "message"
                chat_id = update.message.chat.id
                if update.message.text:
                    update_type += f" with text: {update.message.text}"
            elif update.callback_query:
                update_type = f"callback_query with data: {update.callback_query.data}"
                chat_id = update.callback_query.message.chat.id if update.callback_query.message else None
            
            logger.info(f"[DEBUG] Processing update {update.update_id} of type: {update_type}, chat_id: {chat_id}")
            
            # Store references to the necessary objects for the thread
            dispatcher_ref = dispatcher
            bot_ref = bot
            
            # Use a background task to process the update
            def process_update_task():
                try:
                    # Create a new event loop for this thread
                    task_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(task_loop)
                    
                    # Set the bot as current in this thread context - THIS IS THE CRITICAL FIX
                    bot_ref.set_current(bot_ref)
                    
                    # Make sure dispatcher has the bot reference
                    if hasattr(dispatcher_ref, '_bot'):
                        # Override the bot reference to ensure it's correct
                        dispatcher_ref._bot = bot_ref
                    
                    # Process the update in this dedicated event loop
                    task_loop.run_until_complete(dispatcher_ref.process_update(update))
                    logger.info(f"[DEBUG] Update {update.update_id} processed successfully in dedicated task")
                    
                    # Close the event loop when done
                    task_loop.close()
                except Exception as e:
                    logger.error(f"[DEBUG] Error processing update {update.update_id} in task: {e}", exc_info=True)
                    
                    # Fallback: Try direct message sending for failed commands
                    if chat_id and update.message and update.message.text and update.message.text.startswith('/'):
                        try:
                            fallback_text = "Извините, произошла ошибка при обработке команды. Попробуйте позже."
                            send_direct_message(chat_id, fallback_text)
                            logger.info(f"[DEBUG] Sent fallback message to {chat_id}")
                        except Exception as fallback_error:
                            logger.error(f"[DEBUG] Fallback message failed: {fallback_error}", exc_info=True)
            
            # Start a thread to process the update
            import threading
            update_thread = threading.Thread(target=process_update_task)
            update_thread.daemon = True
            update_thread.start()
            
            logger.info(f"[DEBUG] Started background thread for update {update.update_id}")
            
            # Return immediately to acknowledge receipt
            return Response(status=200)
            
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
        
        return Response(json.dumps(status_info, indent=2), mimetype='application/json')
    except Exception as e:
        logger.error(f"Error in status endpoint: {e}", exc_info=True)
        return f"Error getting status: {str(e)}"

# Функция для отправки сообщений напрямую через API (на случай сбоев)
def send_direct_message(chat_id, text, parse_mode='HTML', reply_markup=None):
    """Send message directly via Telegram API"""
    try:
        logger.info(f"[DEBUG] Attempting to send direct message to chat_id: {chat_id}")
        bot_token = os.getenv("BOT_TOKEN")
        if not bot_token:
            logger.error("[DEBUG] BOT_TOKEN environment variable is not set!")
            return {"error": "BOT_TOKEN not set"}
            
        send_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        payload = {
            'chat_id': chat_id,
            'text': text
        }
        
        # Only add parse_mode if it's HTML or Markdown to avoid API errors
        if parse_mode in ['HTML', 'Markdown', 'MarkdownV2']:
            payload['parse_mode'] = parse_mode
        
        if reply_markup:
            payload['reply_markup'] = reply_markup
            
        # Log the request we're about to make
        logger.info(f"[DEBUG] Sending request to {send_url} with payload: {payload}")
        
        response = requests.post(send_url, json=payload, timeout=10)
        
        # Log both status code and response content
        logger.info(f"[DEBUG] Direct message API response: Status {response.status_code}, Content: {response.text[:200]}")
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"[DEBUG] Direct message sent successfully: {result}")
            return result
        else:
            logger.error(f"[DEBUG] Direct message API error: Status {response.status_code}, Response: {response.text}")
            return {"error": f"API returned status {response.status_code}"}
            
    except Exception as e:
        error_msg = f"Error sending direct message: {str(e)}"
        logger.error(f"[DEBUG] {error_msg}", exc_info=True)
        return {"error": error_msg}

# Эндпоинт для проверки бота через прямую отправку команды
@app.route('/test_bot_command')
def test_bot_command():
    try:
        # Create a test update that simulates a /start command
        bot_token = os.getenv("BOT_TOKEN")
        
        # Get bot info to extract bot user id
        response = requests.get(f"https://api.telegram.org/bot{bot_token}/getMe")
        bot_info = response.json()
        
        if not bot_info.get('ok'):
            return f"Error getting bot info: {bot_info}"
        
        bot_user = bot_info['result']
        
        # Get optional test_chat_id parameter or use default
        test_chat_id = request.args.get('chat_id', '300181690')  # Default to your user ID
        
        # Log what we're about to do
        logger.info(f"[DEBUG] Testing bot with direct command to chat_id {test_chat_id}")
        
        # Use the direct message API to send a message
        result = send_direct_message(
            test_chat_id, 
            "🤖 Тестовое сообщение напрямую через API.\n\nБот @" + bot_user['username'] + " работает!"
        )
        
        # Return results as JSON
        return Response(
            json.dumps({"sent_message": result, "bot_info": bot_user}, indent=2, ensure_ascii=False),
            mimetype='application/json'
        )
        
    except Exception as e:
        logger.error(f"[DEBUG] Error in test_bot_command: {e}", exc_info=True)
        return f"Error: {str(e)}"

# Для запуска приложения
if __name__ == '__main__':
    # Получаем порт из переменной окружения для Render
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True) 