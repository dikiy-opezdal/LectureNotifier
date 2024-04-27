import json
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


TOKEN = open('data\\token.txt', 'r').read()


schedule_keyboard = [
    [
        InlineKeyboardButton('Enable', callback_data='schedule_enable'),
        InlineKeyboardButton('Disable', callback_data='schedule_disable'),
    ],
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
SCHEDULE_DATA_JSON = 1
SUBSCRIBED_CHATS = 0
ACCESSED_KEYBOARDS = 0 # FIXME: access to keyboard due to identical message IDs in different chats(do dict in chat_data user:{accessed_keyboards}


def load(context):
    context.bot_data = json.loads(open('data\\bot_data.json', 'r').read())
    context.chat_data = json.loads(open('data\\chat_data.json', 'r').read())
    context.user_data = json.loads(open('data\\user_data.json', 'r').read())


def save(context):
    open('data\\bot_data.json', 'w').write(json.dumps(context.bot_data))

    chat_data = {}
    for element in context.chat_data:
        chat_data[element] = context.chat_data[element]
    open('data\\chat_data.json', 'w').write(json.dumps(chat_data))

    user_data = {}
    for element in context.user_data:
        user_data[element] = context.user_data[element]
    open('data\\user_data.json', 'w').write(json.dumps(user_data))


async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not ACCESSED_KEYBOARDS in context.user_data:
        context.user_data[ACCESSED_KEYBOARDS] = []
    context.user_data.get(ACCESSED_KEYBOARDS).append(update.message.id + 1)

    await update.message.reply_text('Choose an action.', reply_markup=schedule_markup)


async def schedule_set_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    temp_json = context.chat_data.get(SCHEDULE_DATA_JSON, [])
    temp = context.chat_data.get(SCHEDULE_DATA, [])

    try:
        context.chat_data[SCHEDULE_DATA_JSON] = update.message.text
        context.chat_data[SCHEDULE_DATA] = json.loads(update.message.text)

        await update.message.reply_text('The new schedule was successfully set.')
    except ValueError as e:
        context.chat_data[SCHEDULE_DATA_JSON] = temp_json
        context.chat_data[SCHEDULE_DATA] = temp

        await update.message.reply_text('JSON syntax is invalid.\n\nSee error for details:\n' + str(e))

    return ConversationHandler.END


async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text('Canceled.')
    return ConversationHandler.END


async def inline_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat.id
    message_id = query.message.message_id
    schedule_data = context.chat_data.get(SCHEDULE_DATA_JSON, False)

    message = 'Schedule is not set.'
    reply_markup = None
    parse_mode = None
    state = ConversationHandler.END

    if not message_id in context.user_data.get(ACCESSED_KEYBOARDS, []):
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
            context.chat_data.pop(SCHEDULE_DATA_JSON)
            context.chat_data.pop(SCHEDULE_DATA)
            message = 'Schedule deleted.'
    elif query.data == 'schedule_delete_cancel':
        message = 'Schedule deletion cancelled.'
    elif query.data == 'schedule_enable':
        if schedule_data:
            if not SUBSCRIBED_CHATS in context.bot_data:
                context.bot_data[SUBSCRIBED_CHATS] = [chat_id]
            elif not chat_id in context.bot_data.get(SUBSCRIBED_CHATS, []):
                context.bot_data[SUBSCRIBED_CHATS].append(chat_id)
            message = 'Schedule enabled.'
    elif query.data == 'schedule_disable':
        if chat_id in context.bot_data.get(SUBSCRIBED_CHATS, []):
            context.bot_data[SUBSCRIBED_CHATS].remove(chat_id)
        message = 'Schedule disabled.'
    else:
        message = 'Invalid command.'

    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode=parse_mode)
    return state


def main() -> None:
    application = Application.builder().token(TOKEN).build()

    schedule_handler = CommandHandler('schedule', schedule_command)
    schedule_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(inline_button_handler)],
        states={SCHEDULE_TEXT_STATE:
                    [MessageHandler(filters.TEXT, schedule_set_command), CallbackQueryHandler(inline_button_handler)]},
        fallbacks=[CommandHandler('cancel', cancel_handler)],
    )

    application.add_handler(schedule_handler)
    application.add_handler(schedule_conv_handler)

    load(application)

    application.run_polling(allowed_updates=Update.ALL_TYPES)

    save(application)


if __name__ == '__main__':
    main()
