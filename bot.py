from fbchat import Client, logging
import json
import datetime

STATIC = {
    "PL": {
        "HELP_MESSAGE_LIST": [
            "Witaj w pomocy!",
            "Dodawanie sprawdzianu: !add <dd.mm>; <przedmiot>; <temat (ew. zagadnienia)>",
            "Czyszczenia bazy danych: !clear <dni>; <potwierdzenie: sure>- wyczyszczone zostaną wszystkie dane starsze niż dana ilość dni",
            "https://github.com/pitek1/messenger-bot/"
        ],
        "HELP_SUGGESTION": "Wpisz !help by otrzymać pomoc.",
        "ERROR_PARAMS_COUNT": "Wprowadzono złą ilość parametrów.",
        "ERROR_INVALID_DATE": "Wprowadzona data jest niepoprawna.",
        "EXAM_ADD_SUCCESS": "Pomyślnie dodano test.",
        "EXAM_INFORM_NONE": "• Sprawdziany na 30 dni\n\nYaaay, w najbliższym czasie nie ma żadnych sprawdzianów!",
        "EXAM_INFORM": "• Sprawdziany na 30 dni\n\n{data}",
        "DB_CLEAR_SUCCESS": "Testy wcześniejsze niż {days} dni temu zostały usunięte.",
        "MARKOV_RESULT": "{user}: {result}",
        "KILLED": "Bot został wyłączony.",
        "PERMISSIONS_USERS_ADD": "Pomyślnie dodano użytkownika {user} do grupy {group} (dodatkowe permisje: {additional})",
        "PERMISSIONS_USERS_LIST": "• Użytkownicy\n\n{data}"
    }
}


class BotExit(Exception):
    pass


class AdminBot(Client):

    def __init__(self, *, login="", password="", credentials_f="", language="PL", logging_level=logging.WARNING):
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
        self.load_permissions()

    def load_permissions(self):
        filename = "permissions.json"
        self.permissions.clear()
        try:
            with open(filename, "r", encoding="utf-8") as f:
                permission_data = json.load(f)
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            with open(filename, "w+", encoding="utf-8") as f:
                permission_data = {
                    "users": {
                        input("Input the headadmin's UID: "): {
                            "role": "admin",
                            "extended_permissions": ["*"],
                            "username":"headadmin"
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

    def permissions_users_add(self, author_id, message_object, thread_id, thread_type, **kwargs):
        send, send_static, send_static_list = kwargs["helper_send_functions"]
        try:
            username, role, extended_permissions = [
                p.strip() for p in (message_object.text[len("!users add "):] + ";").split(";")]
            username = username[1:]
            extended_permissions = extended_permissions.strip(
                "[").strip("]").split(",").replace("\"", "").replace("'", "")
            if extended_permissions == ["None"] or ['']:
                extended_permissions == []
        except ValueError as e:
            send_static("ERROR_PARAMS_COUNT")
            send_static("HELP_SUGGESTION")
            print("Failed to add user's permission by {} in {} ({}): {}".format(
                author_id, thread_id, thread_type, message_object.text))
            raise e
        if len(message_object.mentions) == 1:
            uid = message_object.mentions[0].thread_id
        else:
            send_static("ERROR_PARAMS_COUNT")
            send_static("HELP_SUGGESTION")
            print("Failed to add user's permission by {} in {} ({}): {}".format(
                author_id, thread_id, thread_type, message_object.text))
            raise ValueError("Bad count of mentions")

        with open("permissions.json", "r", encoding="utf-8") as f:
            permission_data = json.load(f)
        permission_data["users"][uid] = {
            "username": username, "extended_permissions": extended_permissions, "role": role}
        with open("permissions.json", "w", encoding="utf-8") as f:
            json.dump(permission_data, f)
        self.load_permissions()
        send_static("PERMISSIONS_USERS_ADD", user=username,
                    group=role, additional=", ".join[extended_permissions])
        print("User {} added as {}.".format(username, role))
        return True

    def permissions_users_list(self, author_id, message_object, thread_id, thread_type, **kwargs):
        send, send_static, send_static_list = kwargs["helper_send_functions"]
        with open("permissions.json", "r", encoding="utf-8") as f:
            permission_data = json.load(f)
        users = permission_data["users"]
        print(users)
        data = [(uid, users[uid]["username"], users[uid]["role"], ", ".join(users[uid]["extended_permissions"])) for uid in users]
        data = sorted(data, key=lambda user: user[1])
        data = "\n".join(["• {} • {} • {} • {}".format(*user) for user in data])
        send_static("PERMISSIONS_USERS_LIST", data=data)
        print("Listed users in {}".format(thread_id))
        return True

    def onMessage(self, author_id, message_object, thread_id, thread_type, **kwargs):
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
        comargs = (author_id, message_object, thread_id, thread_type)
        if author_id != self.uid and message_object.text:
            if message_object.text.startswith("!markov ") and has_permission(author_id, 'markov'):
                return self.run_markov(*comargs, **kwargs)
            elif message_object.text == '!help' and has_permission(author_id, 'help'):
                return self.show_help(*comargs, **kwargs)
            elif message_object.text.startswith("!add ") and has_permission(author_id, 'exam.add'):
                return self.add_exam(*comargs, **kwargs)
            elif message_object.text.startswith("!delete ") and has_permission(author_id, 'exam.delete'):
                pass
                # return self.add_exam(*comargs, **kwargs)
            elif message_object.text == '!clear' and has_permission(author_id, 'db.clear'):
                return self.clear_db(*comargs, **kwargs)
            elif message_object.text == '!killbot' and has_permission(author_id, 'bot.kill'):
                send_static("KILLED")
                self.logout()
                raise BotExit("Killed by {}, message_object.text: \"{}\" in {} ({})".format(
                    author_id, message_object.text, thread_id, thread_type))
            elif message_object.text == "!permissions reload" and has_permission(author_id, 'permissions.reload'):
                return self.load_permissions()
            elif message_object.text.startswith("!users add ") and has_permission(author_id, 'permissions.users.add'):
                return self.permissions_users_add(*comargs, **kwargs)
            elif message_object.text.startswith("!users list") and has_permission(author_id, 'permissions.users.list'):
                return self.permissions_users_list(*comargs, **kwargs)
            elif message_object.text.startswith("!users delete ") and has_permission(author_id, 'permissions.users.delete'):
                return self.permissions_users_delete(*comargs, **kwargs)
            elif "sprawdzian" in message_object.text:
                return self.EXAM_INFORM(*comargs, **kwargs)

        # return super().onMessage(author_id=author_id, message_object=message_object, thread_id=thread_id, thread_type=thread_type, **kwargs_c)

    def show_help(self, author_id, message_object, thread_id, thread_type, **kwargs):
        send, send_static, send_static_list = kwargs["helper_send_functions"]
        print("Demand for help from {} in {} ({}): !help".format(
            author_id, thread_type, thread_id))
        send_static_list("HELP_MESSAGE_LIST")
        return True

    def add_exam(self, author_id, message_object, thread_id, thread_type, **kwargs):
        send, send_static, send_static_list = kwargs["helper_send_functions"]
        try:
            date, subject, topic = [p.strip()
                                    for p in message_object.text.text[len("!add "):].split(";")]
        except ValueError as e:
            send_static("ERROR_PARAMS_COUNT")
            send_static("HELP_SUGGESTION")
            print("Failed to add test by {} in {} ({}): {}".format(
                author_id, thread_id, thread_type, message_object.text))
            raise e

        try:
            date = datetime.datetime.strptime(date, "%d.%m")
        except ValueError as e:
            send_static("ERROR_INVALID_DATE")
            print("Failed to add test by {} in {} ({}): {}".format(
                author_id, thread_id, thread_type, message_object.text))
            raise e
        if date < datetime.datetime.now():
            date = date.replace(
                year=datetime.datetime.now().year, hour=23, minute=59)
        if date < datetime.datetime.now():
            date = date.replace(year=date.year + 1)
        date = date.strftime("%d.%m.%Y")
        try:
            with open('data.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            data = []
        data.append({"date": date, "subject": subject, "topic": topic})
        with open('data.json', 'w+', encoding='utf-8') as f:
            json.dump(data, f)
        send_static("EXAM_ADD_SUCCESS")
        print("Test added by {} in {} ({}): {}".format(
            author_id, thread_id, thread_type, message_object.text))
        return True

    def clear_db(self, author_id, message_object, thread_id, thread_type, **kwargs):
        send, send_static, send_static_list = kwargs["helper_send_functions"]
        try:
            days, confirmation = [p.strip()
                                  for p in message_object.text[len("!clear "):].split(";")]
            days = int(days)
            if confirmation != "sure":
                print("Failed to clear database by {} in {} ({}): {}".format(
                    author_id, thread_id, thread_type, message_object.text))
                return False
        except ValueError as e:
            send_static("ERROR_PARAMS_COUNT")
            send_static("HELP_SUGGESTION")
            print("Failed to clear database by {} in {} ({}): {}".format(
                author_id, thread_id, thread_type, message_object.text))
            raise e
        try:
            with open('data.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            data = []
        data = [entry for entry in data if datetime.datetime.strptime(
            entry['date'], "%d.%m.%Y") > datetime.datetime.now() - datetime.timedelta(days=days)]
        with open('data.json', 'w+', encoding='utf-8') as f:
            json.dump(data, f)
        send_static("DB_CLEAR_SUCCESS", days=days)
        print("Tests older than {} days have been deleted".format(days))
        return True

    def EXAM_INFORM(self, author_id, message_object, thread_id, thread_type, **kwargs):
        send, send_static, send_static_list = kwargs["helper_send_functions"]
        if self.last_sent_time > datetime.datetime.now() - datetime.timedelta(minutes=5) and message_object.text != "!sprawdziany":
            print("Not informed {} about tests! (antispam is active)".format(thread_id))
            return False
        self.last_sent_time = datetime.datetime.now()
        try:
            with open('data.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            data = []
        if not data:
            send_static("EXAM_INFORM_NONE")
            print("Informed {} about tests!".format(thread_id))
            return True
        data.sort(key=lambda entry: datetime.datetime.strptime(
            entry["date"], "%d.%m.%Y"), reverse=False)
        data = "\n".join(["• {} • {} • {}".format(
            datetime.datetime.strptime(
                entry['date'], "%d.%m.%Y").strftime("%d.%m"),
            entry["subject"],
            entry["topic"]) for entry in data])
        send_static("EXAM_INFORM", data=data)
        print("Informed {} about tests!".format(thread_id))
        return True

    def run_markov(self, author_id, message_object, thread_id, thread_type, **kwargs):
        # send, send_static, send_static_list = kwargs["helper_send_functions"]
        # target = message_object.text[len("!markov"):].strip()
        # result = ""
        # send_static(MARKOV_RESULT, target, result)
        return True


def main():
    client = AdminBot(credentials_f="credentials.json")
    print('Bot ID {} started working'.format(client.uid))
    client.listen()


if __name__ == '__main__':
    main()
