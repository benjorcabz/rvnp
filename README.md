# Benjor Inventory Online

A responsive Flask web application built around the inventory fields and workflow concepts in the existing `BenjorInventory.py`. It starts with a **fresh database** and does not import or modify the old desktop app's JSON records.

## Included features

- **Admin:** dashboard, inventory management, create/disable accounts, service-request oversight, reports and audit log.
- **IT Support:** inventory register, search/edit items, review repair and borrowing requests, update status and add work notes.
- **Officer / Client:** sign in, submit repair or borrowing requests, see their own request history and track status.
- Inventory fields: control number, serial number, item, brand, details, purchase date, amount, status, assigned person, location and remarks.
- Item statuses, request references, CSRF-protected forms, password hashing, role checks and audit entries.
- SQLite for local testing; PostgreSQL support for hosted deployment.

## 1. Run locally on Windows

Install Python 3.10 or newer. Extract this folder, then open Command Prompt or PowerShell in the `benjor_inventory_online` folder.

```powershell
py -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000` in your browser.

**First local administrator (only created when the database has no users):**
- Username: `admin`
- Password: `ChangeMe123!`

Change the default password after first login by creating a replacement admin account and disabling the default account, or before first startup set `INITIAL_ADMIN_USERNAME` and `INITIAL_ADMIN_PASSWORD` in your environment. The initial password is a bootstrap convenience for local testing, not suitable for public deployment.

## 2. Put it online for access anywhere

You need a hosting provider and a managed PostgreSQL database. This project does not itself publish a website or provision a server. A typical deployment sequence on a Python web host is:

1. Create a new web service from this folder/repository and select Python.
2. Build/install command: `pip install -r requirements.txt`
3. Start command: `gunicorn app:app`
4. Attach a managed PostgreSQL database and set `DATABASE_URL` to its Internal Database URL. The app selects the installed psycopg 3 driver for PostgreSQL URLs.
5. Set environment variables before the first deploy (in Render's Environment tab):
   - `SECRET_KEY`: long, random secret (do not share it or commit it).
   - `DATABASE_URL`: provider's PostgreSQL URL.
   - `INITIAL_ADMIN_NAME`: administrator's display name.
   - `INITIAL_ADMIN_USERNAME`: non-default administrator username.
   - `INITIAL_ADMIN_EMAIL`: administrator email.
   - `INITIAL_ADMIN_PASSWORD`: unique strong password of at least 12 characters.
6. Deploy and open the HTTPS URL assigned by your host. Confirm HTTPS is enabled. The app uses secure session cookies when `FLASK_ENV=production`.
7. Sign in as the initial administrator and create IT Support and Officer / Client accounts. Share passwords privately; do not send them in public channels.

**Important:** the default administrator is created only if the connected database has zero users. If a production database was first started with default credentials, change that password immediately. Do not use the development secret key on a public website.

## 3. Role permissions

| Capability | Admin | IT Support | Officer / Client |
|---|---:|---:|---:|
| View and manage inventory | Yes | Yes | View available items on dashboard |
| Add/edit inventory | Yes | Yes | No |
| Delete inventory | Yes | No | No |
| Create user accounts | Yes | No | No |
| Submit repair/borrowing requests | No (admin can process) | No (staff can process) | Yes |
| Process requests and add notes | Yes | Yes | No |
| View own request history | Yes | Yes | Yes |
| View reports and activity log | Yes | Yes | No |

## 4. Request status flow

A request begins as `Pending`. Admin or IT Support can change it to `Approved`, `Rejected`, `In Progress`, `Ready for Pickup`, `Borrowed`, `Completed`, or `Cancelled`. The linked inventory item status is updated for common borrowing and repair transitions. IT Support should verify physical return/repair condition before marking a request complete.

## 5. Notes and limitations

- Fresh database: no old inventory, transfers, borrower slips or history are imported. The desktop app and its data remain untouched.
- This starter includes request tracking and staff notes; it does not yet send email/SMS notifications, accept file/photo attachments, or generate the desktop app's PDF borrower slips.
- There is no self-service password reset in this version. The administrator must provision accounts; implement a secure reset workflow before broad deployment if required.
- For production use, configure regular database backups and hosting access controls. Never expose the Flask development server directly to the public internet.
- This project is a working starter that should be tested with your organization's real approval policy before operational use.
