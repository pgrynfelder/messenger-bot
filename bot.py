# -*- coding: UTF-8 -*-

from fbchat import Client, logging
# from fbchat.models import *
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
        "TEST_INFORM": "--- Sprawdziany na 30 dni ---\n\n{data}",
        "MARKOV_RESULT": "{user}: {result}",
        "KILLED": "Bot został wyłączony."
    }
}


class BotExit(Exception):
    pass


class AdminBot(Client):

    def __init__(self, *, login="", password="", credentials_f="", language="PL", logging_level=logging.INFO):
        if login and password and credentials_f:
            if input("Do you want to remember your credentials? (y / n)") == "y":
                with open(credentials_f, "w+", encoding="utf-8") as f:
                    json.dump({"username": login, "password": password}, f)
        elif credentials_f:
            try:
                with open(credentials_f, "r", encoding="utf-8") as f:
                    credentials = json.load(f)
                    login, password = credentials['username'], credentials['password']
            except FileNotFoundError:
                print("Credentials file ({}) doesn't exit. Creating new one.".format(
                    credentials_f))
                if not login:
                    login = input("Input login: ")
                if not password:
                    password = input("Input password: ")
                with open(credentials_f, "w+", encoding="utf-8") as f:
                    json.dump({"username": login, "password": password}, f)
        if not login:
            login = input("Input login: ")
        if not password:
            password = input("Input password: ")

        super().__init__(login, password, logging_level=logging_level)
        self.language = language
        self.last_sent_time = datetime.datetime.now() - datetime.timedelta(minutes=5)
        self.permissions = {}
        self.load_permissions("permissions.json")

    def load_permissions(self, filename):
        self.permissions.clear()
        try:
            with open(filename, "r", encoding="utf-8") as f:
                permission_data = json.load(f)
        except FileNotFoundError:
            with open(filename, "w+", encoding="utf-8") as f:
                permission_data = {
                    "users": {
                        input("Input the headadmin's UID: "): {
                            "role": "admin",
                            "extended_permissions": ["*"]
                        }
                    },
                    "roles": {
                        "admin": {
                            "permissions": ["exam.*", "help"]
                        }
                    }
                }
                json.dump(permission_data, f)
        for user, values in permission_data["users"].items():
            self.permissions[user] = set(values["extended_permissions"])
            self.permissions[user] |= set(
                permission_data["roles"][values["role"]])

    def onMessage(self, author_id, message, thread_id, thread_type, **kwargs):
        def send(string):
            return self.sendMessage(string, thread_id=thread_id, thread_type=thread_type)

        def send_static(name, *format_args, **format_kwargs):
            return send(STATIC[self.language][name].format(*format_args, **format_kwargs))

        def send_static_list(list_name, *format_args, **format_kwargs):
            for string in STATIC[self.language][list_name]:
                send(string.format(*format_args, **format_kwargs))

        def has_permission(author_id, permission):
            required = permission.split(".")
            for saved in self.permissions[author_id]:
                saved = saved.split(".")
                for x, y in zip(required, saved):
                    if y == "*":
                        return True
                    elif x == y:
                        matches = True
                    else:
                        matches = False
                        break
                if matches:
                    return True
            return False

        kwargs_c = kwargs.copy()
        kwargs.update({"helper_send_functions": [
                      send, send_static, send_static_list]})
        comargs = (author_id, message, thread_id, thread_type)
        if author_id != self.uid:
            if message.startswith("!markov") and has_permission(author_id, 'markov'):
                return self.run_markov(*comargs, **kwargs)
            elif message == '!help' and has_permission(author_id, 'help'):
                return self.show_help(*comargs, **kwargs)
            elif message.startswith("!add") and has_permission(author_id, 'exam.add'):
                return self.add_exam(*comargs, **kwargs)
            elif message.startswith("!delete") and has_permission(author_id, 'exam.delete'):
                return self.add_exam(*comargs, **kwargs)
            elif message == '!clear' and has_permission(author_id, 'db'):
                return self.clear_db(*comargs, **kwargs)
            elif message == '!killbot' and has_permission(author_id, 'help'):
                send_static("KILLED")
                self.logout()
                raise BotExit("Killed by {}, message: \"{}\" in {} ({})".format(
                    author_id, message, thread_id, thread_type))

            elif "sprawdzian" in message:
                return self.test_inform(*comargs, **kwargs)

        return super().onMessage(author_id=author_id, message=message, thread_id=thread_id, thread_type=thread_type, **kwargs_c)

    def show_help(self, author_id, emssage, thread_id, thread_type, **kwargs):
        send, send_static, send_static_list = kwargs["helper_send_functions"]
        print("Demand for help from {} in {} ({}): !help".format(
            author_id, thread_type, thread_id))
        send_static_list("HELP_MESSAGE_LIST")
        return True

    def add_exam(self, author_id, message, thread_id, thread_type, **kwargs):
        send, send_static, send_static_list = kwargs["helper_send_functions"]
        params = [p.strip() for p in message[4:].split(";")]
        if len(params) < 4:
            send_static("ERROR_NOT_ENOUGH_PARAMS")
            send_static("HELP_SUGGESTION")
            print("Failed to add test by {} in {} ({}): {}".format(
                author_id, thread_id, thread_type, message))
            return False
        params.insert(3, None)
        try:
            date = datetime.datetime.strptime(
                '{} {}'.format(params[1], params[2]), "%d %m")
        except ValueError:
            send_static("ERROR_INVALID_DATE")
            print("Failed to add test by {} in {} (GROUP): {}".format(
                author_id, thread_id, message))
            return False
        if date < datetime.datetime.now():
            date = date.replace(
                year=datetime.datetime.now().year, hour=23, minute=59)
        if date < datetime.datetime.now():
            date = date.replace(year=datetime.datetime.now().year + 1)
        params[1], params[2], params[3] = date.strftime("%d;%m;%Y").split(";")
        with open('data.csv', 'a', newline='') as file:
            writer = csv.writer(file, delimiter=';')
            writer.writerow(params)
        send_static("TEST_ADD_SUCCESS")
        print("Test added by {} in {} (GROUP): {}".format(
            author_id, thread_id, message))
        return True

    def clear_db(self, author_id, message, thread_id, thread_type, **kwargs):
        send, send_static, send_static_list = kwargs["helper_send_functions"]
        data = []
        with open('data.csv', 'r', newline='') as file:
            reader = csv.reader(file, delimiter=';')
            for row in reader:
                if datetime.datetime.strptime("{} {} {}".format(row[1], row[2], row[3]), "%d %m %Y") > datetime.datetime.now() - datetime.timedelta(days=14):
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
                if datetime.datetime.strptime("{} {} {}".format(row[1], row[2], row[3]), "%d %m %Y") < datetime.datetime.now() + datetime.timedelta(days=30) and datetime.datetime.strptime("{} {} {}".format(row[1], row[2], row[3]), "%d %m %Y") > datetime.datetime.now():
                    data.append(row)
        data.sort(key=lambda row: datetime.datetime.strptime(
            "{} {} {}".format(row[1], row[2], row[3]), "%d %m %Y"), reverse=False)
        data = ["• " + " • ".join(row[:3] + row[4:]) for row in data]
        print(data)
        data = "\n".join(data)
        print(data)
        send_static("TEST_INFORM", data=data)
        print("Informed {} about tests!".format(thread_id))
        return True

    def run_markov(self, author_id, message, thread_id, thread_type, **kwargs):
        # send, send_static, send_static_list = kwargs["helper_send_functions"]
        # target = message[len("!markov"):].strip()
        # result = ""
        # send_static(MARKOV_RESULT, target, result)
        return True


def main():
    client = AdminBot(credentials_f="credentials.json")
    print('Bot ID {} started working'.format(client.uid))
    client.listen()


if __name__ == '__main__':
    main()
