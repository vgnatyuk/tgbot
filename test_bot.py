import csv
from threading import Thread
from time import sleep
from datetime import datetime, timedelta
import schedule

from telebot import TeleBot, types

from settings import TOKEN
from create_db import MessagesToEdit, Appointment


bot = TeleBot(TOKEN)


def schedule_checker():
    while True:
        schedule.run_pending()
        sleep(30)


class RemindBot:

    def reminder(self):
        today = datetime.today().date()
        now = datetime.now().time()
        tomorrow = today + timedelta(days=1)
        messages = []
        for user in Appointment.select().where(Appointment.date == tomorrow,
                                               Appointment.telegram_user_id != None):
            response = self.remind_to_user(user)
            message_id = response.message_id
            messages.append({'sent_at_date': today, 'sent_at_time': now,
                             'user_id': user.telegram_user_id, 'message_id': message_id})

        MessagesToEdit.insert_many(messages).execute()

    @staticmethod
    def remind_to_user(user):
        id = user.id
        telegram_user_id = user.telegram_user_id
        name = user.name
        date = user.date
        time = user.time

        message = f'Hello, {name}! You have book {date} at {time}.' \
                  f' Do you confirm your book?'

        keyboard = types.InlineKeyboardMarkup(row_width=2)
        yes_button = types.InlineKeyboardButton(text='Yes', callback_data=f'yes {id}')
        no_button = types.InlineKeyboardButton(text='No', callback_data=f'no {id}')
        keyboard.add(yes_button, no_button)

        return bot.send_message(chat_id=telegram_user_id, text=message, reply_markup=keyboard)

    @staticmethod
    @bot.callback_query_handler(func=lambda call: True)
    def callback_inline(call):
        answer, id = call.data.split(' ')
        # tg_user_id
        # id = 1

        keyboard = types.InlineKeyboardMarkup(row_width=1)
        if answer == 'yes':
            bot.send_message(chat_id=call.message.chat.id, text="You have pressed 'Yes'. Will be wait for you.")
            bot.send_message(chat_id=call.message.chat.id, text='Press "No" to cancel your book.')
            no_button = types.InlineKeyboardButton(text='No', callback_data=f'no {id}')
            keyboard.add(no_button)

            Appointment.set_by_id(key=id, value={"is_confirm": "Yes"})
        elif answer == 'no':
            bot.send_message(chat_id=call.message.chat.id, text="You have pressed 'No'. Your book has been canceled.")
            bot.send_message(chat_id=call.message.chat.id, text="To book a new time call to us.")

            Appointment.set_by_id(key=id, value={"is_confirm": "Cancelled"})
        bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.id, reply_markup=keyboard)

    @staticmethod
    def mr_proper():
        yesterday = datetime.today() - timedelta(days=1)
        for message in MessagesToEdit.select().where(MessagesToEdit.sent_at_date == yesterday,
                                                     MessagesToEdit.is_buttons_deleted == 0):
            chat_id = message.user_id
            message_id = message.message_id

            bot.edit_message_text(text='Time is over. We will call you to confirm your book.',
                                  chat_id=chat_id, message_id=message_id)
            MessagesToEdit.set_by_id(key=message.id, value={"is_buttons_deleted": True})
        print('end')

    @staticmethod
    @bot.message_handler(commands=['start'])
    def welcome(message):
        text = 'Привет! Я буду напоминать тебе о твоей записи в CompanyName за 1 день, чтобы подтвердить или отменить' \
               ' запись, просто нажми соответствующую кнопку. Для продолжения введите свой номер телефона, который вы' \
               ' использовали для записи в CompanyName'

        keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
        phone_request_button = types.KeyboardButton(text='Отправить свой номер', request_contact=True)
        keyboard.add(phone_request_button)

        bot.send_message(chat_id=message.chat.id, text=text, reply_markup=keyboard)
        bot.register_next_step_handler(message, RemindBot.get_phone_step)

    @staticmethod
    def get_phone_step(message):
        phone = message.contact.phone_number
        result = Appointment.update(telegram_user_id=message.from_user.id).where(Appointment.phone == phone).execute()

        if result:
            bot.send_message(text='Теперь мы будем уведомлять вас здесь.', chat_id=message.from_user.id,
                             reply_markup=types.ReplyKeyboardRemove())
        else:
            bot.send_message(text='У нас нет записей для вашего номера телефона, введите его вручную в формате'
                                  ' "+79XXXXXXXX" или свяжитесь с нами по телефону "phone_number"',
                             chat_id=message.from_user.id, reply_markup=types.ReplyKeyboardRemove())
            bot.register_next_step_handler(message, RemindBot.custom_phone_step)

    @staticmethod
    def custom_phone_step(message):
        phone = message.text
        result = Appointment.update(telegram_user_id=message.from_user.id).where(Appointment.phone == phone).execute()
        if result:
            bot.send_message(text='Теперь мы будем уведомлять вас здесь.', chat_id=message.from_user.id)
        else:
            bot.send_message(text='Возникли проблемы, свяжитесь с нами, мы вам обязательно поможем. "phone_number"',
                             chat_id=message.from_user.id)

    @staticmethod
    def get_not_answered_persons():
        yesterday = datetime.today().date() - timedelta(days=1)
        persons = [person for person in
                   Appointment.select().where(Appointment.is_confirm == 'No',
                                              Appointment.date == yesterday).order_by(Appointment.phone)]
        with open('not_answered.csv', mode='w') as file:
            writer = csv.writer(file, delimiter=',')
            writer.writerow(['name', 'phone', 'date', 'time'])
            for person in persons:
                writer.writerow([person.name, person.phone, person.date, person.time])


if __name__ == "__main__":
    remind_bot = RemindBot()
    schedule.every().day.at('09:00').do(remind_bot.reminder)
    schedule.every().day.at('09:00').do(remind_bot.mr_proper)
    schedule.every().day.at('09:00').do(remind_bot.get_not_answered_persons)

    Thread(target=schedule_checker).start()
    Thread(target=bot.polling(none_stop=True, interval=1)).start()
