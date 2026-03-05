# Genny RAG Dashboard

A web dashboard for managing a Retrieval-Augmented Generation (RAG) system. It provides authentication, document upload, search, and management features with a dark theme UI.

## Features

- User authentication with session cookies
- Document upload with group/project categorization
- Search functionality powered by Haystack
- Document management (delete, move)
- Stats display (total docs, chunks, Haystack status)
- Settings page for changing username/password

## How to Run

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the application:
   ```bash
   uvicorn app:app --host 0.0.0.0 --port 8001
   ```

## Default Credentials

- Username: admin
- Password: admin

**Important:** Change the password on first login via the settings page.

## Configuration

The app uses `config.json` for storing user credentials and first-login flag. It connects to a PostgreSQL database for document metadata and interacts with Haystack for search queries.