# Backup and Recovery Script for AmneziaVPN
This script is designed to create backups, restore, and manage configuration files for AmneziaVPN.
## Description
The script performs the following functions:
- Creating backup copies of configuration files.
- Restoring configuration files from backups.
- Deleting old backups.
- Listing available backups.
## Installation
1. Make sure you have Python and Docker installed.
2. Clone this repository to your local computer.
3. Install any necessary dependencies, if any.
## Environment Variables
Before running the script, set the following environment variables:
- `LOCAL_BACKUP_DIR`: path to the local directory for storing backups.
- `NETWORK_BACKUP_DIR`: path to the network directory for storing backups.
Example (for Linux/MacOS):
```bash
export LOCAL_BACKUP_DIR='/your/local/backup/path'
export NETWORK_BACKUP_DIR='/your/network/backup/path'
```
## Usage
Run the script with the desired parameters:
### Creating a backup
```bash
python backup_recovery_amnezia.py --backup
```
### Restoring from a backup
```bash
python backup_recovery_amnezia.py --restore
```
You can also specify a specific backup to restore:
```bash
python backup_recovery_amnezia.py --restore <backup_name>
```
### Deleting old backups
```bash
python backup_recovery_amnezia.py --cleanup
```
### Listing available backups
```bash
python backup_recovery_amnezia.py --list
```
## Note
Make sure you have sufficient permissions to perform Docker operations and access the specified directories for storing backups.
## License
This project is licensed under the MIT License. Please read the full license text in the [LICENSE](LICENSE) file.
