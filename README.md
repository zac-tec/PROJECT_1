# live_brickapp


## Repository contents

`brickfactory/` contains the backend, SQL files, frontend and tests. `brickfactory/task.md` coordinates remaining work. Active browser scripts are documented in `brickfactory/frontend/js/README.md`.

Copy `brickfactory/.env.example` to a private `.env` when configuring an installation. Never commit the live `.env`, virtualenv, backups or old Git metadata. Install dependencies from `requirements.txt`; do not copy the Pi's virtualenv to another machine. This is an existing application: follow the migration/restore task before using the legacy schema on any database containing data.
