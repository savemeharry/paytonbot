import logging
import json
from datetime import datetime
from aiogram import Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
from aiogram.utils.markdown import hbold

from app.utils.db import get_session
from app.services.user import get_or_create_user
from app.services.channel import get_channel_tariffs
from app.services.subscription import process_successful_payment

logger = logging.getLogger(__name__)

# Channel selection handler
async def callback_channel_select(callback_query: types.CallbackQuery):
    """Handle channel selection"""
    await callback_query.answer()
    
    # Extract channel_id from callback data
    _, channel_id = callback_query.data.split(":")
    channel_id = int(channel_id)
    
    session_factory = callback_query.bot.get("session_factory")
    
    async with get_session(session_factory) as session:
        # Get tariffs for the selected channel
        tariffs = await get_channel_tariffs(session, channel_id)
        
        if not tariffs:
            await callback_query.message.answer(
                "Извините, для данного канала не настроены тарифы. Выберите другой канал."
            )
            return
        
        # Create tariff selection message
        tariff_text = f"{hbold('Выберите тариф подписки:')}\n\n"
        
        # Create inline keyboard with tariffs
        keyboard = InlineKeyboardMarkup(row_width=1)
        
        for tariff in tariffs:
            keyboard.add(
                InlineKeyboardButton(
                    text=f"{tariff.name} - {tariff.price_stars} Stars",
                    callback_data=f"tariff:{channel_id}:{tariff.id}"
                )
            )
        
        # Add back button
        keyboard.add(
            InlineKeyboardButton(
                text="🔙 Назад",
                callback_data="back_to_start"
            )
        )
        
        # Send tariff selection message
        await callback_query.message.answer(
            tariff_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

# Tariff selection handler
async def callback_tariff_select(callback_query: types.CallbackQuery):
    """Handle tariff selection"""
    await callback_query.answer()
    
    # Extract channel_id and tariff_id from callback data
    _, channel_id, tariff_id = callback_query.data.split(":")
    channel_id = int(channel_id)
    tariff_id = int(tariff_id)
    
    user_id = callback_query.from_user.id
    session_factory = callback_query.bot.get("session_factory")
    payment_provider_token = callback_query.bot.get("payment_provider_token")
    
    if not payment_provider_token:
        logger.error("Payment provider token not set")
        await callback_query.message.answer(
            "Извините, платежи временно недоступны. Попробуйте позже."
        )
        return
    
    async with get_session(session_factory) as session:
        # Get tariff info
        tariffs = await get_channel_tariffs(session, channel_id)
        tariff = next((t for t in tariffs if t.id == tariff_id), None)
        
        if not tariff:
            await callback_query.message.answer(
                "Извините, выбранный тариф не найден. Попробуйте еще раз."
            )
            return
        
        # Create payment invoice
        title = f"Подписка на канал {tariff.channel.name}"
        description = f"Тариф: {tariff.name} ({tariff.duration_days} дней)"
        
        # Create payload with user_id, channel_id and tariff_id
        payload = f"{user_id}:{channel_id}:{tariff_id}"
        
        # Create price
        prices = [LabeledPrice(label=tariff.name, amount=tariff.price_stars * 100)]  # Amount in cents
        
        # Send invoice
        await callback_query.bot.send_invoice(
            chat_id=user_id,
            title=title,
            description=description,
            payload=payload,
            provider_token=payment_provider_token,
            currency="STARS",
            prices=prices,
            start_parameter="subscribe",
            need_name=False,
            need_phone_number=False,
            need_email=False,
            need_shipping_address=False,
            is_flexible=False
        )
        
        # Send additional message about payment
        await callback_query.message.answer(
            "Для завершения оформления подписки, оплатите счет выше.\n\n"
            "После успешной оплаты вы получите пригласительную ссылку."
        )

# Pre-checkout handler
async def process_pre_checkout_query(pre_checkout_query: types.PreCheckoutQuery):
    """Handle pre-checkout query"""
    # Always accept pre-checkout queries
    await pre_checkout_query.bot.answer_pre_checkout_query(
        pre_checkout_query.id, 
        ok=True
    )

# Successful payment handler
async def process_payment(message: types.Message):
    """Handle successful payment"""
    payment = message.successful_payment
    user_id = message.from_user.id
    session_factory = message.bot.get("session_factory")
    
    logger.info(f"Received payment from {user_id}: {payment.total_amount / 100} {payment.currency}")
    
    try:
        async with get_session(session_factory) as session:
            # Create user record if not exists
            await get_or_create_user(
                session, 
                user_id, 
                message.from_user.username,
                message.from_user.first_name,
                message.from_user.last_name
            )
            
            # Process payment
            payment_data = {
                "telegram_payment_charge_id": payment.telegram_payment_charge_id,
                "provider_payment_charge_id": payment.provider_payment_charge_id,
                "total_amount": payment.total_amount,
                "currency": payment.currency,
                "invoice_payload": payment.invoice_payload
            }
            
            result = await process_successful_payment(
                message.bot,
                session,
                user_id,
                payment_data
            )
            
            # Extract data from result
            channel = result["channel"]
            invite_link = result["invite_link"]
            end_date = result["end_date"]
            
            # Send confirmation and invite link
            await message.answer(
                f"✅ {hbold('Оплата успешно обработана!')}\n\n"
                f"Вы успешно оформили подписку на канал {hbold(channel.name)}.\n\n"
                f"📅 Срок действия: до {end_date.strftime('%d.%m.%Y %H:%M')}\n\n"
                f"👇 Используйте ссылку ниже, чтобы присоединиться к каналу:\n"
                f"{invite_link}\n\n"
                f"⚠️ Ссылка действительна в течение ограниченного времени. "
                f"Перейдите по ней как можно скорее.",
                parse_mode="HTML"
            )
            
            # Notify admins about successful payment
            admin_ids = [int(id.strip()) for id in message.bot.get("admin_ids", "").split(",") if id.strip()]
            for admin_id in admin_ids:
                try:
                    await message.bot.send_message(
                        admin_id,
                        f"💰 Новая подписка!\n\n"
                        f"Пользователь: {message.from_user.full_name} (@{message.from_user.username})\n"
                        f"Канал: {channel.name}\n"
                        f"Сумма: {payment.total_amount / 100} {payment.currency}\n"
                        f"Дата окончания: {end_date.strftime('%d.%m.%Y %H:%M')}"
                    )
                except Exception as e:
                    logger.error(f"Failed to notify admin {admin_id}: {e}")
    
    except Exception as e:
        logger.error(f"Error processing payment: {e}", exc_info=True)
        await message.answer(
            "❌ Произошла ошибка при обработке платежа. "
            "Пожалуйста, обратитесь к администратору бота."
        )

# Refresh subscriptions handler
async def callback_refresh_subscriptions(callback_query: types.CallbackQuery):
    """Handle refresh subscriptions button"""
    await callback_query.answer()
    
    # Emulate /mysubscriptions command
    from app.handlers.base import cmd_my_subscriptions
    await cmd_my_subscriptions(callback_query.message)

# Register subscription handlers
def register_subscription_handlers(dp: Dispatcher):
    """Register all subscription handlers"""
    # Register channel and tariff selection handlers
    dp.register_callback_query_handler(
        callback_channel_select, 
        lambda c: c.data.startswith("channel:")
    )
    dp.register_callback_query_handler(
        callback_tariff_select, 
        lambda c: c.data.startswith("tariff:")
    )
    dp.register_callback_query_handler(
        callback_refresh_subscriptions,
        lambda c: c.data == "refresh_subscriptions"
    )
    
    # Register payment handlers
    dp.register_pre_checkout_query_handler(process_pre_checkout_query)
    dp.register_message_handler(process_payment, content_types=types.ContentTypes.SUCCESSFUL_PAYMENT) 