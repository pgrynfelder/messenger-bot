# -*- coding: UTF-8 -*-

from fbchat import Client, logging
from fbchat.models import *
import csv
import json
import datetime

STATIC = {
    "PL": {
        "HELP_MESSAGE_LIST": [
            "Witaj w pomocy!",
            "Dodawanie sprawdzianu: !add <przedmiot>; <dzień>; <miesiąc>; <temat (ew. zagadnienia)>",
            "Czyszczenia bazy danych: !clear - wyczyszczone zostaną wszystkie dane starsze niż 14 dni"
        ],
        "HELP_SUGGESTION": "Wpisz !help by otrzymać pomoc.",
        "ERROR_NOT_ENOUGH_PARAMS": "Wprowadzono za mało parametrów.",
        "ERROR_INVALID_DATE": "Wprowadzona data jest niepoprawna.",
        "TEST_ADD_SUCCESS": "Pomyślnie dodano test.",
        "TEST_CLEAR_2W_SUCCESS": "Testy wcześniejsze niż 14 dni temu zostały usunięte.",
        "MARKOV_RESULT": "{user}: {result}"
    }
}

class BotExit(Exception):
    pass

class AdminBot(Client):

    def __init__(self, login, password, admin_threads, *, language="PL", logging_level=logging.INFO):
        self.admin_threads = admin_threads
        super().__init__(login, password, logging_level=logging_level)
        self.language = language
        self.last_sent_time = datetime.datetime.now() - datetime.timedelta(minutes=5)

    def onMessage(self, author_id, message, thread_id, thread_type, **kwargs):
        def send(string):
            return self.sendMessage(string, thread_id=thread_id, thread_type=thread_type)
        def send_static(name, *format_args, **format_kwargs):
            return send(STATIC[self.language][name].format(*format_args, **format_kwargs))
        def send_static_list(list_name, *format_args, **format_kwargs):
            for string in STATIC[self.language][list_name]:
                send(string.format(*format_args, **format_kwargs))
        def has_admin_permissions(self, author_id, message, thread_id, thread_type, **kwargs):
            return thread_id in self.admin_threads
        kwargs_c = kwargs.copy()
        kwargs.update({"helper_send_functions": [send, send_static, send_static_list]})
        now = datetime.datetime.now()
        comargs = (author_id, message, thread_id, thread_type)
        if author_id != self.uid:
            if "sprawdzian" in message:
                return self.test_inform(*comargs, **kwargs)
            elif message.startswith("!markov"):
                return self.run_markov(*comargs, **kwargs)
            elif has_admin_permissions(*comargs, **kwargs):
                if message == '!help':
                    return self.show_help(*comargs, **kwargs)
                elif message.startswith("!add"):
                    return self.add_test(*comargs, **kwargs)
                elif message == '!clear':
                    return self.clear_tests(*comargs, **kwargs)
                elif message == '!killbot':
                    self.logout()
                    raise BotExit("Killed: {}, \"{}\", {}, {}".format(author_id, message, thread_id, thread_type))
        return super().onMessage(author_id=author_id, message=message, thread_id=thread_id, thread_type=thread_type, **kwargs_c)

    def show_help(self, author_id, emssage, thread_id, thread_type, **kwargs):
        send, send_static, send_static_list = kwargs["helper_send_functions"]
        print("Demand for help from {} in {} (GROUP): !help".format(author_id, thread_id))
        send_static_list("HELP_MESSAGE_LIST")
        return True

    def add_test(self, author_id, message, thread_id, thread_type, **kwargs):
        send, send_static, send_static_list = kwargs["helper_send_functions"]
        params = [p.strip() for p in message.split(";")[1:]]
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
        if self.last_sent_time > datetime.datetime.now() - datetime.timedelta(minutes=5) and message != "!sprawdziany":
            print("Not informed {} about tests! (antispam is active)".format(thread_id))
            return False
        self.last_sent_time = datetime.datetime.now()
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
        return True

    def run_markov(self, author_id, message, thread_id, thread_type, **kwargs):
        send, send_static, send_static_list = kwargs["helper_send_functions"]
        target = message[len("!markov"):].strip()
        result = ""
        send_static(MARKOV_RESULT, target, result)
        return True

def main():
    with open("config.json", "r") as config_file:
        config = json.load(config_file)
    admin_threads = config['admin_threads']
    USERNAME = config['credentials']['username']
    PASSWORD = config['credentials']['password']
    client = AdminBot(USERNAME, PASSWORD, admin_threads, logging_level=logging.DEBUG)
    print('Bot ID {} started working'.format(client.uid))
    client.listen()
    client.logout()

if __name__ == '__main__':
    main()
