from fbchat import Client, logging
import json
import datetime

STATIC = {
    "PL": {
        "HELP_MESSAGE_LIST": [
            "Witaj w pomocy!",
            "Dodawanie sprawdzianu: !add <dd.mm>; <przedmiot>; <temat (ew. zagadnienia)>",
            "Czyszczenie bazy danych: !clear <dni>; <potwierdzenie: sure>- wyczyszczone zostaną wszystkie dane starsze niż dana ilość dni",
            "Dodawanie użytkownika: !user add @uzytkownik; ranga; dodatkowe, uprawnienia (po przecinkach lub [\"...\", \"...\", ...])",
            "Wyświetlanie listy użytkowników: !users list",
            "Przeładownie danych uprawnień: !permissions reload",
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
        "KILLED": "Bot został zabity.",
        "PERMISSIONS_USERS_ADD": "Pomyślnie dodano użytkownika {user} do grupy {group} (dodatkowe uprawnienia: {additional})",
        "PERMISSIONS_USERS_LIST": "• Użytkownicy\n\n{data}",
        "PERMISSIONS_NOT_ENOUGH": "Nie masz wystarczających uprawnień aby użyć tej komendy.",
        "BOT_ON": "Bot został włączony.",
        "BOT_OFF": "Bot został wyłączony."
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
        self.should_listen = True
        self.language = language
        self.last_sent_time = datetime.datetime.now() - datetime.timedelta(minutes=5)
        self.permissions = {}
        self._permissions_load()

    def onMessage(self, author_id, message_object, thread_id, thread_type, **kwargs):
        SHOULD_LISTEN_OVERRIDE = object()
        commands = [("!markov", "markov", self.run_markov),
                    ("!help", "help", self.show_help),
                    ("!clear", "db.clear", self.db_clear),
                    ("!bot kill", "bot.kill", self.bot_kill, SHOULD_LISTEN_OVERRIDE),
                    ("!bot toggle", "bot.toggle", self.bot_toggle, SHOULD_LISTEN_OVERRIDE),
                    ("!permissions reload", "permissions.reload", self.permissions_reload),
                    ("!users add", "permissions.users.add", self.permissions_users_add),
                    ("!users list", "permissions.users.list", self.permissions_users_list),
                    ("!add", "exam.add", self.exam_add),
                    ("!sprawdziany", "", self.exam_inform)]

        def send(string):
            return self.sendMessage(string, thread_id=thread_id, thread_type=thread_type)

        def send_static(name, *format_args, **format_kwargs):
            return send(STATIC[self.language][name].format(*format_args, **format_kwargs))

        def send_static_list(list_name, *format_args, **format_kwargs):
            for string in STATIC[self.language][list_name]:
                send(string.format(*format_args, **format_kwargs))

        def has_permission(author_id, permission):
            if permission == "":
                return True
            required = permission.split(".")
            try:
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
            except KeyError:
                return False
            return False

        kwargs_c = kwargs.copy()
        kwargs.update({"helper_send_functions": [
                      send, send_static, send_static_list]})
        comargs = (author_id, message_object, thread_id, thread_type)
        if author_id != self.uid:
            for command, permission, function, *others in commands:
                if message_object.text.startswith(command) and (self.should_listen or SHOULD_LISTEN_OVERRIDE in others):
                    if has_permission(author_id, permission):
                        if function(*comargs, **kwargs):
                            print("Successfully executed {} in {} by {}".format(
                                message_object.text, thread_id, author_id))
                            return True
                        else:
                            print("Something went wrong with {} in {} by {}".format(
                                message_object.text, thread_id, author_id))
                            return False
                    else:
                        send_static("PERMISSIONS_NOT_ENOUGH")
                        return False
                # WEIRD EXCEPIONS
                if "sprawdzian" in message_object.text.lower() and self.should_listen:
                    return self.exam_inform(*comargs, **kwargs)
            return False

    def bot_kill(self, author_id, message_object, thread_id, thread_type, **kwargs):
        send, send_static, send_static_list = kwargs["helper_send_functions"]
        send_static("KILLED")
        self.logout()
        self.listening = False
        raise BotExit("Killed by {}, message_object.text: \"{}\" in {} ({})".format(
            author_id, message_object.text, thread_id, thread_type))

    def _permissions_load(self):
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
                            "username": "headadmin"
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
                permission_data["roles"][values["role"]]["permissions"])
        return True

    def permissions_reload(self, author_id, message_object, thread_id, thread_type, **kwargs):
        send, send_static, send_static_list = kwargs["helper_send_functions"]
        return self._permissions_load()

    def permissions_users_add(self, author_id, message_object, thread_id, thread_type, **kwargs):
        send, send_static, send_static_list = kwargs["helper_send_functions"]
        try:
            username, role, extended_permissions = [
                p.strip() for p in (message_object.text[len("!users add "):] + ";").split(";")]
            username = username[1:]
            extended_permissions = [x.strip(
                "[").strip("]").split(",").replace("\"", "").replace("'", "") for x in extended_permissions]
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
                    group=role, additional=", ".join(extended_permissions))
        print("User {} added as {}.".format(username, role))
        return True

    def permissions_users_list(self, author_id, message_object, thread_id, thread_type, **kwargs):
        send, send_static, send_static_list = kwargs["helper_send_functions"]
        with open("permissions.json", "r", encoding="utf-8") as f:
            permission_data = json.load(f)
        users = permission_data["users"]
        print(users)
        data = [(uid, users[uid]["username"], users[uid]["role"], ", ".join(
            users[uid]["extended_permissions"])) for uid in users]
        data = sorted(data, key=lambda user: user[1])
        data = "\n".join(["• {} • {} • {} • {}".format(*user)
                          for user in data])
        send_static("PERMISSIONS_USERS_LIST", data=data)
        print("Listed users in {}".format(thread_id))
        return True

    def show_help(self, author_id, message_object, thread_id, thread_type, **kwargs):
        send, send_static, send_static_list = kwargs["helper_send_functions"]
        print("Demand for help from {} in {} ({}): !help".format(
            author_id, thread_type, thread_id))
        send_static_list("HELP_MESSAGE_LIST")
        return True

    def exam_add(self, author_id, message_object, thread_id, thread_type, **kwargs):
        send, send_static, send_static_list = kwargs["helper_send_functions"]
        try:
            date, subject, topic = [p.strip()
                                    for p in message_object.text[len("!add "):].split(";")]
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

    def db_clear(self, author_id, message_object, thread_id, thread_type, **kwargs):
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

    def exam_inform(self, author_id, message_object, thread_id, thread_type, **kwargs):
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
        data = [x for x in data if datetime.datetime.strptime(
            x["date"], "%d.%m.%Y") > datetime.datetime.now()]
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

    def bot_toggle(self, author_id, message_object, thread_id, thread_type, **kwargs):
        send, send_static, send_static_list = kwargs["helper_send_functions"]
        self.should_listen = not self.should_listen
        send_static("BOT_ON" if self.should_listen else "BOT_OFF")
        return True


def main():
    client = AdminBot(credentials_f="credentials.json")
    print('Bot ID {} started working'.format(client.uid))
    client.listen()


if __name__ == '__main__':
    main()
