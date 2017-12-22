# -*- coding: UTF-8 -*-

from fbchat import Client, log
from fbchat.models import *
import csv
import json
import datetime

STATIC = {
    "PL": {
        "HELP_MESSAGE_LIST": [
            "Witaj w pomocy!",
            "Dodawanie sprawdzianu: !add <przedmiot>; <dzień>; <miesiąc>; <temat (ew. zagadnienia)>",
            "Czyszczenia bazy danych: !clear - wyczyszczone zostaną wszystkie dane nie będące w miesiącach -1 do +2"
        ],
        "HELP_SUGGESTION": "Wpisz !help by otrzymać pomoc.",
        "ERROR_NOT_ENOUGH_PARAMS": "Wprowadzono za mało parametrów.",
        "ERROR_INVALID_DATE": "Wprowadzona data jest niepoprawna.",
        "TEST_ADD_SUCCESS": "Pomyślnie dodano test.",
        "TEST_CLEAR_2W_SUCCESS": "Testy wcześniejsze niż 14 dni temu zostały usunięte.",

    }
}

class BotExit(Exception):
    pass

class AdminBot(Client):
    def __init__(self, login, password, admin_threads, *, language="PL"):
        self.admin_threads = admin_threads
        Client.__init__(self, login, password)
        self.language = language
        self.last_sent_time = datetime.datetime.now() - datetime.timedelta(minutes=5)

    def onMessage(self, author_id, message, thread_id, thread_type, **kwargs):
        def send(string):
            return self.sendMessage(string, thread_id=thread_id, thread_type=thread_type)
        def send_static(name, *format_args, **format_kwargs):
            return send(STATIC[self.language][name].format(*format_args, **format_kwargs))
        def send_static_list(list_name, *format_args, **format_kwargs):
            for string in STATIC[self.language][name]:
                send(string.format(*format_args, **format_kwargs))
        kwargs.update({"helper_send_functions": [send, send_static, send_static_list]})
        now = datetime.datetime.now()
        if author_id == self.uid: #???
            return super().onMessage(author_id=author_id, message=message, thread_id=thread_id, thread_type=thread_type, **kwargs)
        elif message == '!help' and thread_id in self.admin_threads:
            return self.show_help(author_id, message, thread_id, thread_type, **kwargs)
        elif message.split()[0] == "!add" and thread_id in self.admin_threads:
            return self.add_test(author_id, message, thread_id, thread_type, **kwargs)
        elif message == '!clear' and thread_id in self.admin_threads:
            return self.clear_tests(author_id, message, thread_id, thread_type, **kwargs)
        elif message == '!killbot' and thread_id in self.admin_threads:
            raise BotExit("Killed: {}, \"{}\", {}, {}".format(author_id, message, thread_id, thread_type))
        elif "sprawdzian" in message:
            return self.test_inform(author_id, message, thread_id, thread_type, **kwargs)
        else:
            super().onMessage(author_id=author_id, message=message, thread_id=thread_id, thread_type=thread_type, **kwargs)

    def show_help(self, author_id, emssage, thread_id, thread_type, **kwargs):
        send, send_static, send_static_list = kwargs["helper_send_functions"]
        print("Demand for help from {} in {} (GROUP): !help".format(author_id, thread_id))
        send_static_list("HELP_MESSAGE_LIST")       

    def add_test(self, author_id, message, thread_id, thread_type, **kwargs):
        send, send_static, send_static_list = kwargs["helper_send_functions"]
        params = message.replace("!add ", "").replace(" ;", ";").replace("; ", ";")
        params = params.split(";")
        if len(params) < 4:
            send_static("ERROR_NOT_ENOUGH_PARAMS")
            send_static("HELP_SUGGESTION")
            print("Failed to add test by {} in {} (GROUP): {}".format(author_id, thread_id, message))
            return False
        params.insert(3, None)
        try:
            date = datetime.datetime.strptime('{} {}'.format(params[1], params[2]), "%d %m")
        except ValueError:
            send_static("ERROR_INVALID_DATE")
            print("Failed to add test by {} in {} (GROUP): {}".format(author_id, thread_id, message))
            return False
        if date < now:
            date = date.replace(year=now.year, hour=23, minute=59)
        if date < now:
            date = date.replace(year=now.year+1)
        #print(now, "<", date)
        params[1], params[2], params[3] = date.strftime("%d;%m;%Y").split(";")
        with open('data.csv', 'a', newline='') as file:
            writer = csv.writer(file, delimiter=';')
            writer.writerow(params)
        send_static("TEST_ADD_SUCCESS")
        print("Test added by {} in {} (GROUP): {}".format(author_id, thread_id, message))
        return True

    def clear_tests(self, author_id, message, thread_id, thread_type, **kwargs):
        send, send_static, send_static_list = kwargs["helper_send_functions"]
        data = []
        with open('data.csv', 'r', newline='') as file:
            reader = csv.reader(file, delimiter=';')
            for row in reader:
                if datetime.datetime.strptime("{} {} {}".format(row[1], row[2], row[3]), "%d %m %Y") > now - datetime.timedelta(days=14):
                    data.append(row)
        with open('data.csv', 'w', newline='') as file:
            writer = csv.writer(file, delimiter=';')
            for row in data:
                writer.writerow(row)
        send_static("TEST_CLEAR_2W_SUCCESS")
        print("Tests older than 14 days have been deleted")
        return True

    def test_inform(self, author_id, message, thread_id, thread_type, **kwargs):
        send, send_static, send_static_list = kwargs["helper_send_functions"]
        if self.last_sent_time > now - datetime.timedelta(minutes=5) and message != "!sprawdziany":
            print("Not informed {} about tests! (antispam is active)".format(thread_id))
            return False
        self.last_sent_time = now
        data = []
        with open('data.csv', 'r', newline='') as file:
            reader = csv.reader(file, delimiter=';')
            for row in reader:
                if datetime.datetime.strptime("{} {} {}".format(row[1], row[2], row[3]), "%d %m %Y") < now + datetime.timedelta(days=30):
                    data.append(row)
        data.sort(key=lambda row: datetime.datetime.strptime("{} {} {}".format(row[1], row[2], row[3]), "%d %m %Y"), reverse=False)
        data = ["• " + " • ".join(row[:3] + row[4:]) for row in data]
        data.insert(0, "--- Sprawdziany na 30 dni ---\nprzedmiot; dzień; miesiąc; temat\n")
        data = "\n".join(data)
        send(data)
        print("Informed {} about tests!".format(thread_id))
        #print(now, self.last_sent_time)
        return True

def main():
    with open("config.json", "r") as config_file:
        config = json.load(config_file)
    admin_threads = config['admin_threads']
    USERNAME = config['credentials']['username']
    PASSWORD = config['credentials']['password']
    config = None #????
    client = AdminBot(USERNAME, PASSWORD, admin_threads)
    print('Bot ID {} started working'.format(client.uid))
    client.listen()
    client.logout()

if __name__ == '__main__':
    main()
