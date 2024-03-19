import logging

import telegram.constants
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)


logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)


schedule_keyboard = [
    [
        InlineKeyboardButton('Set', callback_data='schedule_set'),
        InlineKeyboardButton('Delete', callback_data='schedule_delete'),
    ],
    [InlineKeyboardButton('Show', callback_data='schedule_show')],
]
schedule_markup = InlineKeyboardMarkup(schedule_keyboard)

schedule_set_keyboard = [
    [InlineKeyboardButton('Cancel', callback_data='schedule_set_cancel')],
]
schedule_set_markup = InlineKeyboardMarkup(schedule_set_keyboard)

schedule_delete_keyboard = [
    [InlineKeyboardButton('Yes', callback_data='schedule_delete_confirm')],
    [InlineKeyboardButton('No', callback_data='schedule_delete_cancel')],
]
schedule_delete_markup = InlineKeyboardMarkup(schedule_delete_keyboard)

SCHEDULE_TEXT_STATE = 0
SCHEDULE_DATA = 0
KEYBOARDS_LIST = 0


async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.user_data.__contains__(KEYBOARDS_LIST):
        context.user_data[KEYBOARDS_LIST] = []
    context.user_data[KEYBOARDS_LIST].append(update.message.message_id + 1)

    await update.message.reply_text('Choose an action.', reply_markup=schedule_markup)


async def schedule_set_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.chat_data[SCHEDULE_DATA] = update.message.text

    await update.message.reply_text('The new schedule was successfully set.')
    return ConversationHandler.END


async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text('Canceled.')
    return ConversationHandler.END


async def inline_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    chat_id = query._get_message().chat_id
    schedule_data = context.chat_data.get(SCHEDULE_DATA, False)

    message = 'Schedule is not set.'
    reply_markup = None
    parse_mode = None
    state = ConversationHandler.END

    if not context.user_data.get(KEYBOARDS_LIST, []).__contains__(query._get_message().message_id):
        return state

    if query.data == 'schedule_show':
        if schedule_data:
            message = f'Current schedule:\n<code>{schedule_data}</code>'
            parse_mode = telegram.constants.ParseMode.HTML
    elif query.data == 'schedule_set':
        if chat_id > 0:
            message = 'Send a new schedule.'
            reply_markup = schedule_set_markup
        else:
            message = 'Send a new schedule as a reply to this message.'
            reply_markup = schedule_set_markup
        state = SCHEDULE_TEXT_STATE
    elif query.data == 'schedule_set_cancel':
        message = 'Schedule setting cancelled.'
    elif query.data == 'schedule_delete':
        if schedule_data:
            message = 'Are you sure?'
            reply_markup = schedule_delete_markup
    elif query.data == 'schedule_delete_confirm':
        if schedule_data:
            del context.drop_chat_data[SCHEDULE_DATA]
        message = 'Schedule deleted.'
    elif query.data == 'schedule_delete_cancel':
        message = 'Schedule deletion cancelled.'
    else:
        message = 'Invalid command.'

    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode=parse_mode)
    return state


def main() -> None:
    application = Application.builder().token('TOKEN').build()

    schedule_handler = CommandHandler('schedule', schedule_command)
    schedule_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(inline_button_handler)],
        states={SCHEDULE_TEXT_STATE:
                    [MessageHandler(filters.TEXT, schedule_set_command), CallbackQueryHandler(inline_button_handler)]},
        fallbacks=[CommandHandler('cancel', cancel_handler)],
    )

    application.add_handler(schedule_handler)
    application.add_handler(schedule_conv_handler)

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
