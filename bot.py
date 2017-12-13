# -*- coding: UTF-8 -*-

from fbchat import Client, log
from fbchat.models import *
import csv
import json
import datetime

class AdminBot(Client):
    def __init__(self, login, password, admin_threads):
        self.admin_threads = admin_threads
        Client.__init__(self, login, password)
        self.antispam = datetime.datetime.now() - datetime.timedelta(minutes=5)

    def onMessage(self, author_id, message, thread_id, thread_type, **kwargs):
        now = datetime.datetime.now()
        if author_id == self.uid:
            super(type(self), self).onMessage(author_id=author_id, message=message, thread_id=thread_id, thread_type=thread_type, **kwargs)
        elif message == '!help' and thread_id in self.admin_threads:
            print("Demand for help from {} in {} (GROUP): !help".format(author_id, thread_id))
            self.sendMessage("Witaj w pomocy!", thread_id=thread_id, thread_type=thread_type)
            self.sendMessage("Schemat dodawania sprawdzianu to: !add PRZEDMIOT; DZIEŃ; MIESIĄC; TEMAT; ew. zagadnienia;", thread_id=thread_id, thread_type=thread_type)
            self.sendMessage("Schemat czyszczenia bazy danych to: !clear ; wyczyszczone zostaną wszystkie dane nie będące w miesiącach -1 do +2", thread_id=thread_id, thread_type=thread_type)

        # ADDING A TEST
        elif message.split(" ")[0] == "!add" and thread_id in self.admin_threads:
            params = message.replace("!add ", "").replace(" ;", ";").replace("; ", ";")
            params = params.split(";")

            if len(params) < 4:
                self.sendMessage("Wprowadzono za mało parametrów.", thread_id=thread_id, thread_type=thread_type)
                self.sendMessage("Wpisz !help by otrzymać pomoc.", thread_id=thread_id, thread_type=thread_type)
                print("Failed to add test by {} in {} (GROUP): {}".format(author_id, thread_id, message))
                return False

            params.insert(3, None)
            try:
                date = datetime.datetime.strptime('{} {}'.format(params[1], params[2]),
                                                  "%d %m")
            except ValueError:
                self.sendMessage("Wprowadzona data jest niepoprawna.", thread_id=thread_id, thread_type=thread_type)
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

            self.sendMessage("Pomyślnie dodano test.", thread_id=thread_id, thread_type=thread_type)
            print("Test added by {} in {} (GROUP): {}".format(author_id, thread_id, message))
            return True

        elif message == '!clear' and thread_id in self.admin_threads:
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
            self.sendMessage("Testy wcześniejsze niż 14 dni temu zostały usunięte.", thread_id=thread_id, thread_type=thread_type)
            print("Tests older than 14 days have been deleted")
            return True
        elif message == '!killbot':
            raise Exception("Killed!")
        elif "sprawdzian" in message:
            if self.antispam > now - datetime.timedelta(minutes=5) and message != "!sprawdziany":
                print("Not informed {} about tests! (antispam is active)".format(thread_id))
                return False
            self.antispam = now
            data = []
            with open('data.csv', 'r', newline='') as file:
                reader = csv.reader(file, delimiter=';')
                for row in reader:
                    if datetime.datetime.strptime("{} {} {}".format(row[1], row[2], row[3]), "%d %m %Y") < now + datetime.timedelta(days=30):
                        data.append(row)
            data.sort(key = lambda row: datetime.datetime.strptime("{} {} {}".format(row[1], row[2], row[3]), "%d %m %Y"),
                      reverse = False)
            data = ["• " + " • ".join(row[:3] + row[4:]) for row in data]
            data.insert(0, "--- SPRAWDZIANY NA 30 DNI ---\nprzedmiot; dzień; miesiąc; temat; ew. zagadnienia\n")
            data.append("\nBot developed by Piotr Grynfelder.\nhttps://github.com/pitek1")
            data = "\n".join(data)
            self.sendMessage(data, thread_id=thread_id, thread_type=thread_type)
            print("Informed {} about tests!".format(thread_id))
            #print(now, self.antispam)
            return True
        else:
            super(type(self), self).onMessage(author_id=author_id, message=message, thread_id=thread_id, thread_type=thread_type, **kwargs)
def main():
    with open("config.json", "r") as cfg:
        config = json.load(cfg)
    admin_threads = config['admin_threads']
    USERNAME = config['credentials']['username']
    PASSWORD = config['credentials']['password']
    config = None
    client = AdminBot(USERNAME, PASSWORD, admin_threads)
    print('Bot ID {} started working'.format(client.uid))
    client.listen()
    client.logout()

if __name__ == '__main__':
    main()
