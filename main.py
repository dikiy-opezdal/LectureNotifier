import asyncio
import datetime
import json
import logging
import humanize
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
    CallbackQueryHandler,
    ConversationHandler,
    PicklePersistence, MessageHandler, filters,
)
from telegram.constants import ParseMode
from markups import (
    menu_markup,
    timetable_markup, timetable_set_markup, timetable_delete_markup,
    notifications_markup, notifications_next_markup,

    timetable_IKB, notifications_IKB,
    timetable_show_IKB, timetable_set_IKB, timetable_set_cancel_IKB, timetable_delete_IKB, timetable_delete_confirm_IKB,
    timetable_delete_cancel_IKB,
    notifications_enable_IKB, notifications_disable_IKB, notifications_next_IKB, notifications_next_skip_IKB
)


# chat data
TIMETABLE_DATA, TIMETABLE_DATA_JSON = range(2)
# bot data
SUBSCRIBED_CHATS = 0
# conversation states
TIMETABLE_SET_STATE = 0


logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(text='Choose a command:', reply_markup=menu_markup)

async def menu_CallbackQueryHandler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    text = 'Something went wrong.'
    reply_markup = None

    button = int(query.data)
    if button == timetable_IKB:
        text = 'Choose an option:'
        reply_markup = timetable_markup
    elif button == notifications_IKB:
        text = 'Choose an option:'
        reply_markup = notifications_markup
    else:
        text = 'Invalid option.'

    await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)


async def timetable_CallbackQueryHandler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    timetable_data = context.chat_data.get(TIMETABLE_DATA_JSON, False)

    text = 'Timetable is not set\.'
    reply_markup = None
    state = ConversationHandler.END

    button = int(query.data)
    if button == timetable_show_IKB:
        if timetable_data:
            text = f'Current timetable:```json\n{timetable_data}\n```'
    elif button == timetable_set_IKB:
        if query.message.chat.id > 0:
            text = 'Send a new timetable\.'
        else:
            text = 'Send a new timetable as a reply to this message\.'
        reply_markup = timetable_set_markup
        state = TIMETABLE_SET_STATE
    elif button == timetable_set_cancel_IKB:
        text = 'Timetable setting cancelled\.'
        state = ConversationHandler.END
    elif button == timetable_delete_IKB:
        if timetable_data:
            text = 'Are you sure?'
            reply_markup = timetable_delete_markup
    elif button == timetable_delete_confirm_IKB:
        context.chat_data.pop(TIMETABLE_DATA_JSON)
        context.chat_data.pop(TIMETABLE_DATA)
        text = 'Timetable deleted\.'
    elif button == timetable_delete_cancel_IKB:
        text = 'Timetable deletion cancelled\.'
    else:
        text = 'Invalid option\.'

    await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2)
    return state


async def notifications_CallbackQueryHandler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat.id

    text = 'Something went wrong.'
    reply_markup = None

    button = int(query.data)
    if button == notifications_enable_IKB:
        if context.chat_data.get(TIMETABLE_DATA_JSON, False):
            if not chat_id in context.bot_data[SUBSCRIBED_CHATS]:
                context.bot_data[SUBSCRIBED_CHATS].append(chat_id)
                asyncio.get_event_loop().create_task(schedule_notify(context, chat_id))
            text = 'Notifications enabled.'
    elif button == notifications_disable_IKB:
        context.bot_data.get[SUBSCRIBED_CHATS].remove(chat_id)
        text = 'Notifications disabled.'
    elif button == notifications_next_IKB:
        text = 'No further lectures are scheduled for today.'
        timetable = context.chat_data.get(TIMETABLE_DATA, [])
        if len(timetable) > 0:
            day = timetable[datetime.datetime.now().weekday()]
            lecture, delay = find_next_lecture(day)
            if lecture >= 0:
                text = gen_notify_text(day[lecture])[0].replace(" is starting soon.", " is next lecture.")
                text = f'{text[:text.find(":")+3]}({humanize.naturaltime(delay, future=True)}){text[text.find(":")+3:]}'
                reply_markup = notifications_next_markup
    elif button == notifications_next_skip_IKB:
        text = 'In development.' # TODO
    else:
        text = 'Invalid option.'

    await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)


async def timetable_set(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    prev_timetable_json = context.chat_data.get(TIMETABLE_DATA_JSON, None)

    try:
        context.chat_data[TIMETABLE_DATA_JSON] = update.message.text
        context.chat_data[TIMETABLE_DATA] = json.loads(update.message.text)
        result = check_timetable(context.chat_data.get(TIMETABLE_DATA))
        if result == 0:
            await update.message.reply_text('The new timetable was successfully set.')
        else:
            context.chat_data[TIMETABLE_DATA_JSON] = prev_timetable_json
            context.chat_data[TIMETABLE_DATA] = json.loads(prev_timetable_json)
            await update.message.reply_text(f'Timetable structure is invalid\.\n\nSee error for details:```\n{result}\n```',
                                            parse_mode=ParseMode.MARKDOWN_V2)
    except ValueError as e:
        context.chat_data[TIMETABLE_DATA_JSON] = prev_timetable_json
        await update.message.reply_text(f'JSON syntax is invalid\.\n\nSee error for details:```\n{str(e)}\n```',
                                        parse_mode=ParseMode.MARKDOWN_V2)

    return ConversationHandler.END


def check_timetable(timetable):
    if not isinstance(timetable, list):
        return 'expected type "array" for timetable, got "object" instead'
    else:
        for i in range(len(timetable)):
            if not isinstance(timetable[i], list):
                return f'day {i}: expected type "array" for day, got "object" instead'
            else:
                for j in range(len(timetable[i])):
                    if not isinstance(timetable[i][j], dict):
                        return f'day {i} lecture {j}: expected type "object" for lecture, got "array" instead'
                    elif 'link' in timetable[i][j] and not validators.url(timetable[i][j]['link']):
                        return f'day {i} lecture {j}: url "{timetable[i][j]["link"]}" is invalid'
                    elif not 'start' in timetable[i][j]:
                        return f'day {i} lecture {j}: missing required argument "start"'
                    else:
                        try:
                            datetime.datetime.strptime(timetable[i][j]['start'], '%H:%M')
                        except ValueError:
                            return f'day {i} lecture {j}: start time "{timetable[i][j]["start"]}" is invalid, expected "HH:MM" format'
                        if 'length' in timetable[i][j]:
                            try:
                                datetime.datetime.strptime(timetable[i][j]['length'], '%H:%M')
                            except ValueError:
                                return f'day {i} lecture {j}: lecture length time "{timetable[i][j]["length"]}" is invalid, expected "HH:MM" format'
    return 0


async def schedule_notify(context, chat_id):
    timetable = context.chat_data.get(TIMETABLE_DATA, False)
    weekday = datetime.datetime.now().weekday()
    if len(timetable) > weekday:
        day = timetable[weekday]
        lecture, delay = find_next_lecture(day)
        if lecture >= 0:
            text, markup = gen_notify_text(day[lecture])
            await asyncio.sleep(delay)

            if chat_id in context.bot_data[SUBSCRIBED_CHATS]:
                await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=markup, parse_mode=ParseMode.HTML)

                loop = asyncio.get_event_loop()
                loop.create_task(schedule_notify(context, chat_id))


def find_next_lecture(day):
    last_lecture = -1
    time_now = datetime.datetime.now()
    time_now = datetime.datetime(1900, 1, 1, time_now.hour, time_now.minute, time_now.second)
    last_delay = 128000

    if len(day) > 0:
        for lecture in range(len(day)):
            delay = (datetime.datetime.strptime(day[lecture]['start'], '%H:%M') - time_now).total_seconds()
            if 0 < delay < last_delay:
                last_lecture = lecture
                last_delay = delay

    return last_lecture, last_delay


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
        start = datetime.datetime.strptime(lecture['start'], '%H:%M')
        length = datetime.datetime.strptime(lecture['length'], '%H:%M')

        delta_length = datetime.timedelta(hours=length.hour, minutes=length.minute)

        end = f' – {datetime.datetime.strftime(start + delta_length, "%H:%M")}'
    if 'link' in lecture:
        link = lecture['link']

        join_markup = InlineKeyboardMarkup([[InlineKeyboardButton('Join', url=link)]])
    if 'note' in lecture:
        note = f'\n\n{lecture["note"]}'

    text = f'<b><a href="{link}">{title}</a></b>{lecturer} is starting soon.\n<b>{lecture["start"]}{end}</b><i>{note}</i>'

    return text, join_markup


def main() -> None:
    application = Application.builder().token(open('data/token.txt', 'r').read()).\
        persistence(persistence=PicklePersistence(filepath='data/database.pickle')).build()

    application.add_handler(CommandHandler('menu', menu_command))

    application.add_handler(CallbackQueryHandler(menu_CallbackQueryHandler, pattern=f'^({timetable_IKB}|{notifications_IKB})$'))
    application.add_handler(CallbackQueryHandler(timetable_CallbackQueryHandler, pattern=f'^({timetable_show_IKB}|{timetable_delete_IKB}|{timetable_delete_confirm_IKB}|{timetable_delete_cancel_IKB})$'))
    application.add_handler(CallbackQueryHandler(notifications_CallbackQueryHandler, pattern=f'^({notifications_enable_IKB}|{notifications_disable_IKB}|{notifications_next_IKB}|{notifications_next_skip_IKB})$'))

    application.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(timetable_CallbackQueryHandler, pattern=f'^({timetable_set_IKB})')],
        states={
            TIMETABLE_SET_STATE: [MessageHandler(filters.TEXT, timetable_set)],
        },
        fallbacks=[
            CallbackQueryHandler(timetable_CallbackQueryHandler, pattern=f'^({timetable_set_cancel_IKB})'),
        ],
        per_chat=True, per_user=True, per_message=False,
    ))

    if not SUBSCRIBED_CHATS in application.bot_data:
        application.bot_data[SUBSCRIBED_CHATS] = []

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
