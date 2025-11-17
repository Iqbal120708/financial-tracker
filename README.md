# financial-tracker
This project check and manage file csv, file csv which containing your expense data and output send to google sheets

# feature
- check file csv
- manage file csv
- send output to google sheets
- send info message with email (message languange indonesia)
- logging (message languange indonesia)

# Arsitektur
- Django > Backend
- Redis > Broker
- Celery > Worker
- Celery Beat > Scheduler

# Install
- python 3.12
- liblary in requirements.txt
- redis 7.2.5

# Folder Structure
financial-tracker/
├── README.md
├── credentials/
│   └── file_credentials.json
├── fin_track/
│   ├── fin_track/
│   │   ├── settings.py
│   │   ├── celery.py
│   │   └── ...
│   ├── core/
│   ├── accounts/
│   ├── finlogic/
│   └── manage.py
└── logs/
    ├── debug.log
    └── error.log

# Explain Folders
`financial-tracker/`
Root directory of the project. All core files and configurations are stored here.

`credentials/`
Directory for Google API service account credentials required to access Google Sheets.

`file_credentials.json`
JSON key file used for authenticating Google Sheets API requests.

`fin_track/`
Main Django project folder. Contains configuration files, apps, and Celery integration.

`fin_track/fin_track/`
Core Django configuration package. Includes settings, Celery setup, and project initialization files.

`settings.py`
Django settings module for environment variables, apps, middleware, logging, etc.

`celery.py`
Celery configuration file that initializes the Celery worker and integrates it with Django.

`logs/`
Directory for storing application log files.

`debug.log`
Log file that records debug-level events during development.

`error.log`
Log file that records error and exception details.

`finlogic/`
Core logic app

`core/`
contains the basic code, `BaseModel` which used for other files

`accounts/`
For authentication logic django, can ignore

## Environment Variables

Configure the application using the following environment variables. Each variable must be adjusted according to your environment.

- **EMAIL_HOST_USER** → Email address used for SMTP authentication.  
- **EMAIL_HOST_PASSWORD** → App password or SMTP credential for `EMAIL_HOST_USER`.  
- **ID_FILE_GOOGLE_SHEETS** → The ID of the Google Sheets file used by the application.  
- **PATH_CREDENTIALS** → Path to the Google API credentials file (e.g., `credentials.json`).  
- **SENDER_EMAIL** → Email address used as the sender for notifications.  
- **TARGETS_EMAIL** → List of recipient email addresses (multiple values allowed, separated by commas).  
- **CELERY_BROKER_URL** → Celery message broker URL, typically Redis.

- **CELERY_RESULT_BACKEND** → Backend used for storing Celery task results.  
- **SECRET_KEY** → Django secret key used for security-related operations.  
- **DEBUG** → Debug mode flag (`True` or `False`).

# How ro run
- create a new folder credentials and logs, place according to folder structure
- Create a Google API credentials file by creating a Service Account in the Google Cloud Console and enabling the Sheets API. Download the JSON key and save the file in the credentials/ directory. For complete instructions, see the official guide: Google Cloud → Creating and managing service accounts.
- create a new file google sheets, you can get id file and can use to environment variable **ID_FILE_GOOGLE_SHEETS**
- create a new sheets with name `Category Expense` and `Monthly Expense`
- create header `Category Expense` with value **month**, **category**, **total_expense** start sheets A1, end sheets C1
- create header `Monthly Expense` with value **month**, **total_expense**, **avg_per_day**, **days_count** start sheets A1, end sheets D1
- Share your Google Sheets file with the service account email. You can find the service account email by opening your `credentials.json` file and copying the value of **client_email**
- create a new file .env, place according to folder structure and fill with environment variables
- Create a virtual environment and activate it
- install liblary in requirements.txt
- activate redis
- activate celery worker and beat
- script will run task if hour 0,4,8,12,16,20 in time zone Asia/Jakarta

# sintaks
`pip install -r requirements.txt` for install liblary
`python3 -m venv env` for create virtual environment
`source env/bin/activate` for activate  virtual environment
`redis-server` for activate redis
`celery -A fin_track worker` for activate celery worker, add `-l info` if you want debugging
`celery -A fin_track beat` for activate celery worker, add `-l info` if you want debugging

# Format Data File CSV
- column which require is `date`, `category`, `price`
- `date` format `yyyy-mm-dd`
- `category` use data type text 
- `price` use data type number
- you can add new column but the column have no influence

# Other
if you want change the message email, you can find `file_processors.py`, `file_readers.py`, `tasks.py`, location file in `financial-tracker/fin_track/finlogic/`
for easy search, you can use key `send_mail_task` or `message` in search

if you want change the message log, you can find `financial-tracker/fin_track/finlogic/file_processors.py`
for easy search, you can use key `logger` in search

if you want change the hour, you can open file `financial-tracker/fin_track/fin_track/settings.py`, then chnage time zone according your time zone area
you can change the hour with search variabel **CELERY_BEAT_SCHEDULE** then change value crontab
