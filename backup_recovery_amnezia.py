import os
import shutil
import argparse
from datetime import datetime, timedelta
import json
import filecmp
import sys
import subprocess

LOCAL_BACKUP_DIR = os.getenv('LOCAL_BACKUP_DIR')
NETWORK_BACKUP_DIR = os.getenv('NETWORK_BACKUP_DIR')
CONTAINER_NAME = 'amnezia-awg'
WG0_CONF_PATH = 'opt/amnezia/awg/wg0.conf'
CLIENTS_TABLE_PATH = 'opt/amnezia/awg/clientsTable'
BACKUP_RETENTION_DAYS = 30

if not LOCAL_BACKUP_DIR:
    raise EnvironmentError("Environment variable LOCAL_BACKUP_DIR is not set.")
if not NETWORK_BACKUP_DIR:
    raise EnvironmentError("Environment variable NETWORK_BACKUP_DIR is not set.")

def get_container_id(container_name):
    try:
        result = subprocess.run(['docker', 'ps', '-q', '-f', f'name={container_name}'], capture_output=True, text=True)
        container_id = result.stdout.strip()
        if not container_id:
            raise Exception(f"Container named {container_name} not found.")
        return container_id
    except Exception as e:
        print(f"Error retrieving container ID: {e}")
        return None

def get_file_path_in_container(container_id, file_path):
    try:
        result = subprocess.run(['docker', 'inspect', '--format', f'{{{{.GraphDriver.Data.MergedDir}}}}', container_id], capture_output=True, text=True)
        merged_dir = result.stdout.strip()
        if not merged_dir:
            raise Exception(f"Failed to get MergedDir path for container {container_id}.")
        return os.path.join(merged_dir, file_path)
    except Exception as e:
        print(f"Error retrieving file path in container: {e}")
        return None

container_id = get_container_id(CONTAINER_NAME)
if container_id:
    wg0_conf_path = get_file_path_in_container(container_id, WG0_CONF_PATH)
    clients_table_path = get_file_path_in_container(container_id, CLIENTS_TABLE_PATH)

if not os.path.exists(LOCAL_BACKUP_DIR):
    os.makedirs(LOCAL_BACKUP_DIR)

def create_backup(backup_dir):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_subdir = os.path.join(backup_dir, timestamp)
    os.makedirs(backup_subdir)
    
    wg0_backup_path = backup_file(wg0_conf_path, backup_subdir)
    clients_table_backup_path = backup_file(clients_table_path, backup_subdir)

    if wg0_backup_path and clients_table_backup_path:
        print(f"Backups successfully created in {backup_subdir}")
        sync_directories(backup_dir, NETWORK_BACKUP_DIR)
        delete_old_backups(backup_dir, BACKUP_RETENTION_DAYS)
    else:
        print("Error creating backups.")

def backup_file(src_path, backup_dir):
    if os.path.exists(src_path):
        basename = os.path.basename(src_path)
        backup_path = os.path.join(backup_dir, basename)
        shutil.copy2(src_path, backup_path)
        print(f"Backup of {src_path} created: {backup_path}")
        return backup_path
    else:
        print(f"File {src_path} not found.")
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
        print(f"Error: file {file_path} is not valid JSON.")
        return 0

def restore_file(src_path, backup_path):
    if not os.path.exists(backup_path):
        print(f"Backup {backup_path} not found.")
        return

    print(f"Restoring {src_path} from {backup_path}")
    if os.path.exists(src_path):
        if os.path.getsize(src_path) == 0:
            print(f"Source file {src_path} is empty, it will be overwritten.")
        elif filecmp.cmp(src_path, backup_path):
            print("Files are identical, no overwrite needed.")
            return
        else:
            if 'wg0.conf' in src_path:
                src_accounts = count_wg0_conf_accounts(src_path)
                backup_accounts = count_wg0_conf_accounts(backup_path)
            elif 'clientsTable' in src_path:
                src_accounts = count_clients_table_accounts(src_path)
                backup_accounts = count_clients_table_accounts(backup_path)
            print(f"Number of accounts in source file: {src_accounts}")
            print(f"Number of accounts in backup: {backup_accounts}")
    else:
        print(f"Source file {src_path} not found, a new file will be created.")
    
    shutil.copy2(backup_path, src_path)
    print(f"File {src_path} successfully restored from {backup_path}")

def delete_old_backups(backup_dir, days=30):
    now = datetime.now()
    cutoff = now - timedelta(days=days)
    for subdir in os.listdir(backup_dir):
        subdir_path = os.path.join(backup_dir, subdir)
        if os.path.isdir(subdir_path):
            dir_time = datetime.fromtimestamp(os.path.getmtime(subdir_path))
            if dir_time < cutoff:
                shutil.rmtree(subdir_path)
                print(f"Old backup deleted: {subdir_path}")

def list_backups(backup_dir):
    backups = sorted(os.listdir(backup_dir), key=lambda x: os.path.getmtime(os.path.join(backup_dir, x)))
    for idx, backup in enumerate(backups, start=1):
        print(f"{idx}. {backup}")

def sync_directories(src_dir, dst_dir):
    if not os.access(dst_dir, os.W_OK):
        print(f"Directory {dst_dir} is not writable. Synchronization skipped.")
        return

    print(f"Synchronizing directories: {src_dir} -> {dst_dir}")
    
    src_files = set(os.listdir(src_dir))
    dst_files = set(os.listdir(dst_dir))

    for file in src_files - dst_files:
        src_file_path = os.path.join(src_dir, file)
        dst_file_path = os.path.join(dst_dir, file)
        shutil.copytree(src_file_path, dst_file_path)
        print(f"Copied {src_file_path} to {dst_file_path}")

    for file in dst_files - src_files:
        dst_file_path = os.path.join(dst_dir, file)
        if os.path.isdir(dst_file_path):
            shutil.rmtree(dst_file_path)
        else:
            os.remove(dst_file_path)
        print(f"Deleted {dst_file_path}")

def print_help():
    script_name = os.path.basename(sys.argv[0])
    help_message = f"""
Usage: {script_name} [OPTIONS]

Options:
--backup Create a backup of configuration files
--restore [NAME] Restore configuration files from a backup. If NAME is not specified, a selection will be prompted.
--cleanup Delete old backups
--list List all backups
--sync Synchronize local backup directory with network backup directory
-h, --help Show this help message and exit

Examples:
  {script_name} --backup
  {script_name} --restore
  {script_name} --restore 20230615_123456
  {script_name} --cleanup
  {script_name} --list
  {script_name} --sync
"""
    print(help_message)

def main():
    parser = argparse.ArgumentParser(description="Backup, restore, and backup management script.", add_help=False)
    parser.add_argument('--backup', action='store_true', help='Create a backup of configuration files')
    parser.add_argument('--restore', nargs='?', const=True, help='Restore configuration files from a backup')
    parser.add_argument('--cleanup', action='store_true', help='Delete old backups')
    parser.add_argument('--list', action='store_true', help='List all backups')
    parser.add_argument('--sync', action='store_true', help='Synchronize local backup directory with network backup directory')
    parser.add_argument('-h', '--help', action='store_true', help='Show this help message and exit')

    args = parser.parse_args()

    if not any(vars(args).values()) or args.help:
        print_help()
        return

    if args.backup:
        create_backup(LOCAL_BACKUP_DIR)

    if args.restore is not None:
        backups = sorted(os.listdir(LOCAL_BACKUP_DIR), key=lambda x: os.path.getmtime(os.path.join(LOCAL_BACKUP_DIR, x)))
        if not backups:
            print("No backups available.")
            return

        if args.restore is True:
            list_backups(LOCAL_BACKUP_DIR)
            default_choice = len(backups)
            choice = input(f"Enter the number of the backup to restore [default is {default_choice}]: ") or default_choice

            try:
                choice_idx = int(choice) - 1
                backup_name = backups[choice_idx]
            except (IndexError, ValueError):
                print("Invalid choice.")
                return
        else:
            backup_name = args.restore

        restore_backup(LOCAL_BACKUP_DIR, backup_name)

    if args.cleanup:
        delete_old_backups(LOCAL_BACKUP_DIR)

    if args.list:
        list_backups(LOCAL_BACKUP_DIR)

    if args.sync:
        sync_directories(LOCAL_BACKUP_DIR, NETWORK_BACKUP_DIR)

if __name__ == "__main__":
    main()
