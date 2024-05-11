from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# InlineKeyboardButton's
timetable_IKB, notifications_IKB,\
timetable_show_IKB, timetable_set_IKB, timetable_set_cancel_IKB, timetable_delete_IKB, timetable_delete_confirm_IKB,\
timetable_delete_cancel_IKB,\
notifications_enable_IKB, notifications_disable_IKB, notifications_next_IKB, notifications_next_skip_IKB = range(12)


menu_keyboard = \
[
    [
        InlineKeyboardButton('Timetable', callback_data=timetable_IKB),
        InlineKeyboardButton('Notifications', callback_data=notifications_IKB),
    ]
]
menu_markup = InlineKeyboardMarkup(menu_keyboard)

keyboard = [[InlineKeyboardButton('Click me!')]]
markup = InlineKeyboardMarkup(keyboard)


timetable_keyboard =\
[
    [
        InlineKeyboardButton('Set', callback_data=timetable_set_IKB),
        InlineKeyboardButton('Delete', callback_data=timetable_delete_IKB),
    ],
    [InlineKeyboardButton('Show', callback_data=timetable_show_IKB)],
]
timetable_markup = InlineKeyboardMarkup(timetable_keyboard)

timetable_set_keyboard =\
[
    [InlineKeyboardButton('Cancel', callback_data=timetable_set_cancel_IKB)],
]
timetable_set_markup = InlineKeyboardMarkup(timetable_set_keyboard)

timetable_delete_keyboard =\
[
    [InlineKeyboardButton('Yes', callback_data=timetable_delete_confirm_IKB)],
    [InlineKeyboardButton('No', callback_data=timetable_delete_cancel_IKB)],
]
timetable_delete_markup = InlineKeyboardMarkup(timetable_delete_keyboard)


notifications_keyboard =\
[
    [
        InlineKeyboardButton('Enable', callback_data=notifications_enable_IKB),
        InlineKeyboardButton('Disable', callback_data=notifications_disable_IKB),
    ],
    [InlineKeyboardButton('Next', callback_data=notifications_next_IKB)]
]
notifications_markup = InlineKeyboardMarkup(notifications_keyboard)

notifications_next_keyboard =\
[
    [InlineKeyboardButton('Skip', callback_data=notifications_next_skip_IKB)]
]
notifications_next_markup = InlineKeyboardMarkup(notifications_next_keyboard)