# Library Management System

A premium mini project built with **Python Flask + SQLite + HTML/CSS/JS**.

## Features

### Admin
- Admin signup and login
- Add, edit, delete books
- Search books
- View student list
- Approve or reject book requests
- Mark issued books as returned
- Dashboard with stats and recent activity

### Student
- Student signup and login
- Search available books
- Request books
- View pending, issued, returned, and rejected history

## Default Admin Login

```txt
Email: admin@library.com
Password: admin123
```

## How to Run

1. Open the project folder in VS Code.
2. Open terminal in the project folder.
3. Create virtual environment:

```bash
python -m venv venv
```

4. Activate virtual environment:

Windows:

```bash
venv\Scripts\activate
```

Mac/Linux:

```bash
source venv/bin/activate
```

5. Install requirements:

```bash
pip install -r requirements.txt
```

6. Run the app:

```bash
python app.py
```

7. Open in browser:

```txt
http://127.0.0.1:5000
```

## Notes

- The database `library.db` is created automatically when you run the app.
- Sample books and a default admin account are inserted automatically.
- You can create new admin/student accounts from the landing page.
