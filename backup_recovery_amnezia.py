import os
import shutil
import argparse
from datetime import datetime, timedelta
import json
import filecmp
import sys
import subprocess

def get_container_id(container_name):
    try:
        result = subprocess.run(['docker', 'ps', '-q', '-f', f'name={container_name}'], capture_output=True, text=True)
        container_id = result.stdout.strip()
        if not container_id:
            raise Exception(f"Контейнер с именем {container_name} не найден.")
        return container_id
    except Exception as e:
        print(f"Ошибка получения ID контейнера: {e}")
        return None

def get_file_path_in_container(container_id, file_path):
    try:
        result = subprocess.run(['docker', 'inspect', '--format', f'{{{{.GraphDriver.Data.MergedDir}}}}', container_id], capture_output=True, text=True)
        merged_dir = result.stdout.strip()
        if not merged_dir:
            raise Exception(f"Не удалось получить путь MergedDir для контейнера {container_id}.")
        return os.path.join(merged_dir, file_path)
    except Exception as e:
        print(f"Ошибка получения пути файла в контейнере: {e}")
        return None

container_name = 'amnezia-awg'
container_id = get_container_id(container_name)
if container_id:
    wg0_conf_path = get_file_path_in_container(container_id, 'opt/amnezia/awg/wg0.conf')
    clients_table_path = get_file_path_in_container(container_id, 'opt/amnezia/awg/clientsTable')

local_backup_dir = os.getenv('LOCAL_BACKUP_DIR')
network_backup_dir = os.getenv('NETWORK_BACKUP_DIR')

if not local_backup_dir:
    raise EnvironmentError("Переменная окружения LOCAL_BACKUP_DIR не установлена.")
if not network_backup_dir:
    raise EnvironmentError("Переменная окружения NETWORK_BACKUP_DIR не установлена.")


if not os.path.exists(local_backup_dir):
    os.makedirs(local_backup_dir)

def create_backup(backup_dir):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_subdir = os.path.join(backup_dir, timestamp)
    os.makedirs(backup_subdir)
    
    wg0_backup_path = backup_file(wg0_conf_path, backup_subdir)
    clients_table_backup_path = backup_file(clients_table_path, backup_subdir)

    if wg0_backup_path and clients_table_backup_path:
        print(f"Резервные копии успешно созданы в {backup_subdir}")
        sync_directories(backup_dir, network_backup_dir)
    else:
        print("Ошибка создания резервных копий.")

def backup_file(src_path, backup_dir):
    if os.path.exists(src_path):
        basename = os.path.basename(src_path)
        backup_path = os.path.join(backup_dir, basename)
        shutil.copy2(src_path, backup_path)
        print(f"Резервная копия {src_path} создана: {backup_path}")
        return backup_path
    else:
        print(f"Файл {src_path} не найден.")
        return None

def restore_backup(backup_dir, timestamp):
    backup_subdir = os.path.join(backup_dir, timestamp)
    wg0_backup_path = os.path.join(backup_subdir, "wg0.conf")
    clients_table_backup_path = os.path.join(backup_subdir, "clientsTable")

    restore_file(wg0_conf_path, wg0_backup_path)
    restore_file(clients_table_path, clients_table_backup_path)

def count_wg0_conf_accounts(file_path):
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        return 0
    with open(file_path, 'r') as file:
        return sum(1 for line in file if line.strip() == '[Peer]')

def count_clients_table_accounts(file_path):
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        return 0
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)
            return len(data)
    except json.JSONDecodeError:
        print(f"Ошибка: файл {file_path} не является валидным JSON.")
        return 0

def restore_file(src_path, backup_path):
    if not os.path.exists(backup_path):
        print(f"Резервная копия {backup_path} не найдена.")
        return

    print(f"Восстановление {src_path} из {backup_path}")
    if os.path.exists(src_path):
        if os.path.getsize(src_path) == 0:
            print(f"Исходный файл {src_path} пуст, будет перезаписан.")
        elif filecmp.cmp(src_path, backup_path):
            print("Файлы идентичны, перезапись не требуется.")
            return
        else:
            if 'wg0.conf' in src_path:
                src_accounts = count_wg0_conf_accounts(src_path)
                backup_accounts = count_wg0_conf_accounts(backup_path)
            elif 'clientsTable' in src_path:
                src_accounts = count_clients_table_accounts(src_path)
                backup_accounts = count_clients_table_accounts(backup_path)
            print(f"Количество учетных записей в исходном файле: {src_accounts}")
            print(f"Количество учетных записей в резервной копии: {backup_accounts}")
    else:
        print(f"Исходный файл {src_path} не найден, будет создан новый файл.")
    
    shutil.copy2(backup_path, src_path)
    print(f"Файл {src_path} успешно восстановлен из {backup_path}")


def delete_old_backups(backup_dir, days=30):
    now = datetime.now()
    cutoff = now - timedelta(days=days)
    for subdir in os.listdir(backup_dir):
        subdir_path = os.path.join(backup_dir, subdir)
        if os.path.isdir(subdir_path):
            dir_time = datetime.fromtimestamp(os.path.getmtime(subdir_path))
            if dir_time < cutoff:
                shutil.rmtree(subdir_path)
                print(f"Удалена старая резервная копия: {subdir_path}")

def list_backups(backup_dir):
    backups = sorted(os.listdir(backup_dir), key=lambda x: os.path.getmtime(os.path.join(backup_dir, x)))
    for idx, backup in enumerate(backups, start=1):
        print(f"{idx}. {backup}")

def sync_directories(src_dir, dst_dir):
    if not os.access(dst_dir, os.W_OK):
        print(f"Каталог {dst_dir} не доступен для записи. Синхронизация пропущена.")
        return

    print(f"Синхронизация каталогов: {src_dir} -> {dst_dir}")
    
    src_files = set(os.listdir(src_dir))
    dst_files = set(os.listdir(dst_dir))

    for file in src_files - dst_files:
        src_file_path = os.path.join(src_dir, file)
        dst_file_path = os.path.join(dst_dir, file)
        shutil.copytree(src_file_path, dst_file_path)
        print(f"Скопирован {src_file_path} в {dst_file_path}")

    for file in dst_files - src_files:
        dst_file_path = os.path.join(dst_dir, file)
        if os.path.isdir(dst_file_path):
            shutil.rmtree(dst_file_path)
        else:
            os.remove(dst_file_path)
        print(f"Удален {dst_file_path}")

def print_help():
    script_name = os.path.basename(sys.argv[0])
    help_message = f"""
Использование: {script_name} [OPTIONS]

Опции:
  --backup             Создать резервную копию конфигурационных файлов
  --restore [NAME]     Восстановить конфигурационные файлы из резервной копии. Если NAME не указан, будет предложен выбор.
  --cleanup            Удалить старые резервные копии
  --list               Вывести список резервных копий
  -h, --help           Показать эту справку и выйти

Примеры:
  {script_name} --backup
  {script_name} --restore
  {script_name} --restore 20230615_123456
  {script_name} --cleanup
  {script_name} --list
"""
    print(help_message)

def main():
    parser = argparse.ArgumentParser(description="Скрипт резервного копирования, восстановления и управления резервными копиями.", add_help=False)
    parser.add_argument('--backup', action='store_true', help='Создать резервную копию конфигурационных файлов')
    parser.add_argument('--restore', nargs='?', const=True, help='Восстановить конфигурационные файлы из резервной копии')
    parser.add_argument('--cleanup', action='store_true', help='Удалить старые резервные копии')
    parser.add_argument('--list', action='store_true', help='Вывести список резервных копий')
    parser.add_argument('-h', '--help', action='store_true', help='Показать эту справку и выйти')

    args = parser.parse_args()

    if not any(vars(args).values()) or args.help:
        print_help()
        return

    if args.backup:
        create_backup(local_backup_dir)

    if args.restore is not None:
        backups = sorted(os.listdir(local_backup_dir), key=lambda x: os.path.getmtime(os.path.join(local_backup_dir, x)))
        if not backups:
            print("Нет доступных резервных копий.")
            return

        if args.restore is True:
            list_backups(local_backup_dir)
            default_choice = len(backups)
            choice = input(f"Введите номер резервной копии для восстановления [по умолчанию {default_choice}]: ") or default_choice

            try:
                choice_idx = int(choice) - 1
                backup_name = backups[choice_idx]
            except (IndexError, ValueError):
                print("Некорректный выбор.")
                return
        else:
            backup_name = args.restore

        restore_backup(local_backup_dir, backup_name)

    if args.cleanup:
        delete_old_backups(local_backup_dir)

    if args.list:
        list_backups(local_backup_dir)

if __name__ == "__main__":
    main()

