# MalSharePoint

MalSharepoint is a modern webserver, optimized for sharing exploit codes, payloads or malware with an advanced Level of obfuscation and stealth. The application simplifies the delivery process in pentests or red team engagements, also being a useful tool for Threat Simulation or Network Security Audits.

## Features

- File upload and download
- Secure User-Management with strict rights
- Seperate Administration Panel for Webserver Configuration

## Techstack

- **Frontend**: React.js and Vue.js
- **Database**: sqlite3
- **Backend**: Python-Flask

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/MalSharePoint.git
   cd MalSharePoint
   ```

2. Install the backend dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Initialize the database:
   ```bash
   python manage.py init-db
   ```

4. Run the development server:
   ```bash
   python app.py
   ```
