import json
import os
from datetime import datetime

# Пути к файлам
wg0_conf_path = "/var/lib/docker/overlay2/b4f245ea4d73670f029ab11320e8ecece13f92d8d855ef3014ed98fc0d979f1d/merged/opt/amnezia/awg/wg0.conf"
clients_table_path = "/var/lib/docker/overlay2/b4f245ea4d73670f029ab11320e8ecece13f92d8d855ef3014ed98fc0d979f1d/merged/opt/amnezia/awg/clientsTable"

# Функция для чтения и парсинга файла wg0.conf
def parse_wg0_conf(path):
    with open(path, "r") as file:
        lines = file.readlines()

    peers = []
    peer = {}
    for line in lines:
        line = line.strip()
        if line.startswith("[Peer]"):
            if peer:
                peers.append(peer)
                peer = {}
        elif line.startswith("PublicKey"):
            peer["PublicKey"] = line.split(" = ")[1]
        elif line.startswith("PresharedKey"):
            peer["PresharedKey"] = line.split(" = ")[1]
        elif line.startswith("AllowedIPs"):
            peer["AllowedIPs"] = line.split(" = ")[1]

    if peer:
        peers.append(peer)

    return peers

# Функция для чтения и парсинга файла clientsTable
def parse_clients_table(path):
    if not os.path.exists(path):
        return []

    with open(path, "r") as file:
        return json.load(file)

# Функция для обновления clientsTable
def update_clients_table(clients, peers):
    existing_clients = {client["clientId"] for client in clients}
    new_clients = []
    user_count = len(clients) + 1

    for peer in peers:
        if peer["PublicKey"] not in existing_clients:
            new_clients.append({
                "clientId": peer["PublicKey"],
                "userData": {
                    "clientName": f"user{user_count}",
                    "creationDate": datetime.now().strftime("%a %b %d %H:%M:%S %Y")
                }
            })
            user_count += 1

    return clients + new_clients

# Чтение данных
peers = parse_wg0_conf(wg0_conf_path)
clients = parse_clients_table(clients_table_path)

# Обновление clientsTable
updated_clients = update_clients_table(clients, peers)

# Запись обновленного clientsTable
with open(clients_table_path, "w") as file:
    json.dump(updated_clients, file, indent=4)

print("ClientsTable успешно обновлен.")
