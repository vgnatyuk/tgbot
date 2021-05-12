from peewee import Model, IntegerField, CharField, DateField, TimeField, SqliteDatabase, BooleanField


db = SqliteDatabase('people.db')


class Reminder(Model):
    class Meta:
        database = db


class MessagesToEdit(Reminder):
    sent_at_date = DateField()
    sent_at_time = TimeField()
    message_id = IntegerField()
    user_id = IntegerField()
    is_buttons_deleted = BooleanField(default=False)

    def __str__(self):
        return f'{self.sent_at_date} - {self.user_id} - {self.is_buttons_deleted}'


class Appointment(Reminder):
    name = CharField()
    phone = CharField()
    date = DateField()
    time = TimeField()
    telegram_user_id = IntegerField(null=True)
    is_confirm = CharField(null=True, default='No')

    def __str__(self):
        return f'{self.name} - {self.phone}'


db.create_tables([Appointment, MessagesToEdit])
