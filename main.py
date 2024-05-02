import asyncio
import datetime
import json
import logging

import validators
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
    filters, PicklePersistence,
)


logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)


TOKEN = open('data/token.txt', 'r').read()


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


def gen_notify_text(lecture):
    text = ''
    title = 'Lecture'
    lecturer = ''
    end = ''
    link = ''
    note = ''
    join_markup = None

    if 'title' in lecture:
        title = lecture['title']
    if 'lecturer' in lecture:
        lecturer = f', {lecture["lecturer"]},'
    if 'length' in lecture:
        try:
            start = datetime.datetime.strptime(lecture['start'], '%H:%M')
            length = datetime.datetime.strptime(lecture['length'], '%H:%M')

            delta_length = datetime.timedelta(hours=length.hour, minutes=length.minute)

            end = f' – {datetime.datetime.strftime(start + delta_length, "%H:%M")}'
        except ValueError:
            end = ''
    if 'link' in lecture and validators.url(lecture['link']):
        link = lecture['link']

        join_markup = InlineKeyboardMarkup([[InlineKeyboardButton('Join', url=link)]])
    if 'note' in lecture:
        note = f'\n\n{lecture["note"]}'

    text = f'<b><a href="{link}">{title}</a></b>{lecturer} is starting soon.\n<b>{lecture["start"]}{end}</b><i>{note}</i>'

    return text, join_markup


def find_closest_lecture(day):
    last_lecture = -1
    time_now = datetime.datetime.now()
    time_now = datetime.datetime(1900, 1, 1, time_now.hour, time_now.minute, time_now.second)
    last_delay = 128000

    if len(day) > 0:
        for lecture in range(len(day)):
            if 'start' in day[lecture]:
                delay = (datetime.datetime.strptime(day[lecture]['start'], '%H:%M') - time_now).total_seconds()
                if 0 < delay < last_delay:
                    last_lecture = lecture
                    last_delay = delay

    return last_lecture, last_delay


async def schedule_notify(context, chat_id):
    try:
        schedule = context.chat_data.get(SCHEDULE_DATA, False)
        if isinstance(schedule, list):
            weekday = datetime.datetime.now().weekday()
            if len(schedule) > weekday:
                day = schedule[weekday]
                if isinstance(day, list):
                    lecture, delay = find_closest_lecture(day)
                    if lecture >= 0:
                        text, markup = gen_notify_text(day[lecture])
                        await asyncio.sleep(delay)
                        await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=markup,
                                                       parse_mode=telegram.constants.ParseMode.HTML)
                        
                        loop = asyncio.get_event_loop()
                        loop.create_task(schedule_notify(context, chat_id))
    except IndexError:
        await context.bot.send_message(chat_id=chat_id, text='An error occurred during schedule processing. '
                                                             'Please, check if the schedule is correct.')


async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not ACCESSED_KEYBOARDS in context.user_data:
        context.user_data[ACCESSED_KEYBOARDS] = []
    context.user_data.get(ACCESSED_KEYBOARDS, []).append(update.message.id + 1)

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
    context.user_data[ACCESSED_KEYBOARDS] = [message_id]

    if query.data == 'schedule_show':
        if schedule_data:
            message = f'Current schedule:\n<code>{schedule_data}</code>'
            parse_mode = telegram.constants.ParseMode.HTML
    elif query.data == 'schedule_set':
        if chat_id > 0:
            message = 'Send a new schedule as a JSON string.'
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

            loop = asyncio.get_event_loop()
            loop.create_task(schedule_notify(context, chat_id))


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
    persistence = PicklePersistence(filepath='data/database.pickle')
    application = Application.builder().token(TOKEN).persistence(persistence=persistence).build()

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

