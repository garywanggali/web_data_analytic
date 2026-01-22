# Design and Implementation of a User Behavior Tracking and Analytics System

**Author:** Gary Wang  
**Date:** January 22, 2026

## Abstract

This paper presents the design and implementation of a comprehensive User Behavior Tracking and Analytics System. The system is designed to capture, process, and visualize user interactions on a web-based platform in real-time. Key features include a lightweight JavaScript SDK for frontend telemetry, a scalable FastAPI-based backend for data ingestion, and an interactive dashboard for data visualization. The system supports advanced tracking capabilities such as session management, source attribution (UTM/Referrer/User-Agent), scroll depth tracking, and engagement time analysis. The solution was successfully deployed in a production-like environment, demonstrating its effectiveness in providing actionable insights into user behavior.

## I. Introduction

In the modern digital landscape, understanding user behavior is critical for optimizing user experience (UX) and improving conversion rates. While commercial solutions like Google Analytics 4 (GA4) exist, they often come with data ownership concerns and complexity. This project aims to build a custom, lightweight, and privacy-focused analytics system that captures essential metrics—User, Acquisition, and Engagement—similar to industry standards.

The objectives of this project are:
1.  Develop a non-intrusive frontend script to capture user events (page views, clicks, scrolls).
2.  Build a high-performance backend API to handle concurrent data ingestion.
3.  Design a data visualization dashboard to interpret the collected data.
4.  Deploy the full stack to a remote server for real-world testing.

## II. System Architecture

The system follows a classic three-tier architecture: Presentation Layer (Frontend SDK & Dashboard), Application Layer (Backend API), and Data Layer (Database).

### A. Architecture Diagram

```mermaid
graph LR
    User[User Browser] -->|sdk.js| SDK[Frontend Tracker SDK]
    SDK -->|POST /api/collect| API[Analytics API (FastAPI)]
    API -->|Write| DB[(SQLite Database)]
    Admin[Administrator] -->|View| Dash[Visualization Dashboard]
    Dash -->|GET /api/stats| API
    API -->|Read| DB
```

### B. Components

1.  **Frontend Tracker SDK (`sdk.js`)**: A lightweight JavaScript library embedded in the client website. It automatically handles session generation, event listeners (scroll, click, visibility change), and data transmission via `fetch` or `navigator.sendBeacon`.
2.  **Backend API**: Built with Python **FastAPI**, chosen for its high performance and asynchronous capabilities. It exposes endpoints for data collection and retrieval.
3.  **Database**: **SQLite** via **SQLAlchemy ORM** is used for data persistence. It stores event logs including timestamp, visitor ID, session ID, event type, and metadata.
4.  **Visualization Dashboard**: An HTML/JS interface powered by **ECharts**, providing real-time graphs for user flow, acquisition sources, and engagement metrics.

## III. Implementation Details

### A. Frontend Event Tracking Method

The tracking logic is encapsulated in `sdk.js`. Key implementation details include:

1.  **Session Management & User Identification**:
    *   **User (Visitor)**: Represents a unique individual or device. Identified by a persistent UUID (`visitor_id`) stored in `localStorage`. This ID remains constant across multiple visits unless the browser cache is cleared.
    *   **Session**: Represents a single continuous period of user activity. Identified by a temporary UUID (`session_id`) stored in `sessionStorage`. A session expires after 30 minutes of inactivity.
    *   **Relationship**: One User can generate multiple Sessions over time (e.g., visiting in the morning and again at night counts as 1 User but 2 Sessions).

2.  **Event Types**:
    *   **Page View**: Triggered on page load. Captures URL, title, and performance metrics (load time).
    *   **User Engagement**: Triggered on `beforeunload` or `visibilitychange`. Calculates the duration the page was active in the foreground.
    *   **Scroll**: Triggered when the user scrolls past 90% of the page height.
    *   **Click**: Automatically intercepts clicks on external links (`<a>` tags) for outbound traffic tracking.

3.  **Source Attribution**:
    The system implements a priority-based attribution model:
    *   **Priority 1**: UTM Parameters (`utm_source` in URL).
    *   **Priority 2**: User-Agent detection (e.g., distinguishing WeChat or DingTalk built-in browsers).
    *   **Priority 3**: `document.referrer` analysis (e.g., Google, Bing, direct entry).

### B. API Design

The backend exposes the following RESTful endpoints:

1.  **Data Collection**:
    *   `POST /api/collect`
    *   **Request Body**:
        ```json
        {
          "event_type": "pageview",
          "url": "http://example.com/course/1",
          "referrer": "https://google.com",
          "visitor_id": "uuid-v4",
          "session_id": "uuid-v4",
          "data": { "load_time_ms": 120, "source": "google" }
        }
        ```
    *   **Response**: `200 OK`

2.  **Data Retrieval**:
    *   `GET /api/analytics/stats`: Returns aggregated metrics (Total Users, Sessions, Top Sources, Device Breakdown).
    *   `GET /api/analytics/sankey`: Returns node-link data for generating the User Flow Sankey chart.

### C. Data Visualization

The dashboard visualizes the data to provide actionable insights. Recent updates have introduced advanced analytical capabilities:

1.  **Real-Time Monitoring**:
    *   **Live Users**: Displays the count of unique users active within the last 5 minutes.
    *   **Real-Time Trend**: A dynamic line chart showing user activity minute-by-minute for the last 30 minutes, allowing administrators to monitor immediate traffic spikes.

2.  **Growth Trend Analysis**:
    *   A multi-line chart tracking **Users**, **Sessions**, and **Page Views** over time.
    *   Supports dynamic time aggregation (hourly buckets for 24h view, daily buckets for longer periods) to visualize growth patterns and peak traffic hours.

3.  **User Retention Analysis (New vs. Returning)**:
    *   Classifies users based on their session history.
    *   **New Visitors**: Users with only one session in the selected period.
    *   **Returning Visitors**: Users with multiple sessions, indicating retention and engagement.
    *   Visualized via pie charts (user count ratio) and bar charts (activity volume by user type).

4.  **Traffic Acquisition & User Flow**:
    *   **Acquisition Pie Chart**: Breaks down traffic by source (Direct, Search, Social), prioritizing UTM parameters and User-Agent detection (e.g., WeChat).
    *   **Sankey Diagram**: Maps the user journey from entry to exit, highlighting popular navigation paths and drop-off points.

5.  **Interactive Filtering**:
    *   A global time range selector (24 Hours, 7 Days, 30 Days, All Time) allows users to slice data across different temporal dimensions, updating all charts dynamically via AJAX.

## IV. Deployment

The system was deployed on a Linux server (`110.40.153.38`) using the following configuration:

*   **Analytics Server**: Running on port **5270** using `uvicorn` with optimized worker processes.
*   **Target Website**: Running on port **5007**, instrumented with the `sdk.js` script.
*   **Process Management**: `nohup` was used for background process execution, ensuring high availability.

Access URL: `http://110.40.153.38:5270/`

## V. Conclusion

This project successfully demonstrates the end-to-end development of a web analytics system. By implementing custom tracking logic and visualizing the data, the system provides valuable insights into user behavior without relying on third-party services. The robust architecture ensures scalability, while the detailed attribution logic solves common tracking challenges in the mobile-first ecosystem (e.g., in-app browsers like WeChat). Future work could include adding heatmaps and conversion funnel analysis.

## VI. References

[1] Google Analytics 4 Documentation, "Events and parameters," Google Developers.
[2] Mozilla Developer Network, "Beacon API," MDN Web Docs.
[3] FastAPI Documentation, "FastAPI - Modern Python Web Framework."
