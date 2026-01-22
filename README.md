# User Behavior Tracking and Analytics System

## Overview

This project is a custom-built Web Analytics System designed to track, process, and visualize user behavior on a website. It consists of a lightweight JavaScript SDK for the frontend and a high-performance FastAPI backend. The system serves as a privacy-focused, self-hosted alternative to Google Analytics, capable of tracking user sessions, page views, engagement time, and traffic sources.

## Features

- **Real-Time Monitoring**: View live active users and traffic trends in the last 30 minutes.
- **Growth Trends**: Analyze historical data for Users, Sessions, and Page Views over 24h, 7 days, or 30 days.
- **User Retention**: Distinguish between New and Returning visitors.
- **Traffic Attribution**: Automatically detect traffic sources (Direct, Google, WeChat, DingTalk, etc.) with UTM parameter support.
- **User Flow Visualization**: Sankey diagrams to visualize user navigation paths.
- **Heatmap / Engagement**: Track average engagement time per session.
- **Privacy Focused**: Uses anonymous Visitor IDs and Session IDs without storing PII (Personally Identifiable Information).

## Tech Stack

- **Backend**: Python 3.9+, FastAPI, SQLAlchemy, SQLite
- **Frontend**: Vanilla JavaScript (SDK), ECharts (Visualization), HTML5/CSS3
- **Deployment**: Uvicorn, Nginx (Optional), Linux (CentOS/OpenCloudOS)

## Project Structure

```
web-data-analytic/
├── analytics_site/
│   ├── main.py              # FastAPI application entry point
│   ├── database.py          # Database connection
│   ├── models.py            # SQLAlchemy models
│   ├── schemas.py           # Pydantic schemas
│   ├── static/
│   │   └── sdk.js           # Frontend Tracking SDK
│   ├── templates/
│   │   └── index.html       # Analytics Dashboard
│   ├── requirements.txt     # Python dependencies
│   └── run.sh               # Startup script
├── docs/
│   └── IEEE_Technical_Report.md  # Technical Documentation
└── README.md
```

## Installation & Setup

### 1. Clone the Repository

```bash
git clone https://github.com/garywanggali/web_data_analytic.git
cd web_data_analytic/analytics_site
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the Server

```bash
python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 5270
```

The dashboard will be available at `http://localhost:5270/`.

### 4. Integrate the SDK

Add the following script to your target website's HTML `<head>`:

```html
<script src="http://your-analytics-server:5270/sdk.js"></script>
```

## API Endpoints

- `POST /api/collect`: Ingest user event data.
- `GET /api/analytics/stats`: Retrieve aggregated statistics.
- `GET /api/analytics/sankey`: Retrieve user flow data.

## License

MIT License
