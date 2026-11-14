# Excellence Cloud deployment

URL: http://agents.excellencetechnologies.in:20311/
Login: http://agents.excellencetechnologies.in:20311/login/

The integrated FastAPI application serves both the built frontend and API on
0.0.0.0:20311. Frontend API requests use the same origin.
Port 20311 was free within the authorized 20300–20330 range at deployment.

From the repository root:

```sh
export PM2_HOME="$PWD/.runtime/pm2"
pm2 status conversational-ai
pm2 restart conversational-ai
pm2 stop conversational-ai
```

To rebuild:

```sh
cd frontend-preview
npm run build:integrated
```

To launch when not already running, from the repository root with the authorized
secret environment injected:

```sh
export PM2_HOME="$PWD/.runtime/pm2"
pm2 start deploy/ecosystem.config.cjs
```

Secrets are loaded from injected environment or the existing backend environment
configuration; never add them to deployment files or PM2 dumps.
PM2 restarts application crashes and continues after chat completion.
Automatic recovery after a full host reboot is not configured. The platform
requires operator-managed boot integration for that guarantee.

Validation: production build and frontend test suite passed; live integrated
registration, streamed chat, database persistence and memory controls passed.
Health reports production mode and healthy database. HTTP requests to the public
hostname succeeded from this server. Independent browser verification was blocked
by the managed browser socket-directory permission error.

This is a publicly reachable app with account authentication and uses the owner's
shared 2 CPU / 8 GB resource allowance.

## Full host reboot recovery (prepared, not installed)

`conversational-ai.service` runs the same PM2 application under systemd.
This session cannot install/enable it: user systemd bus and crontab access
were refused. A cloud administrator must:

1. Configure boot-time injection of the existing Vault secrets
   `SECRET_GEMINI_API_KEY` and `SECRET_GROQ_API_KEY` into this service.
   The existing backend environment file does not contain usable provider keys.
   Do not copy secrets into source control or a PM2 dump.
2. Install this unit in `/etc/systemd/system/conversational-ai.service`.
3. Arrange a controlled handover from the running project PM2 daemon to
   this service, preserving port 20311 and the existing project database.
4. Run `systemctl daemon-reload` and
   `systemctl enable --now conversational-ai.service` as administrator.
5. Verify service status and `/health`, `/api/runtime`, and authenticated chat.
6. During an authorized maintenance window, reboot and repeat those checks.

The unit has not been enabled or reboot-tested. The existing deployment
continues running under PM2.
