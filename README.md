# AI Voice Assistant

A real-time voice assistant web application using Volcengine (ASR), SiliconFlow (LLM), and Minimax (TTS).

## Features

*   **Real-time Interaction:** WebSocket-based full-duplex communication.
*   **Streaming ASR:** Volcengine WebSocket API for low-latency recognition.
*   **Streaming LLM:** SiliconFlow (DeepSeek) with token streaming.
*   **Streaming TTS:** Minimax audio streaming.
*   **Authentication:** User registration and login (JWT).
*   **Dockerized:** Easy deployment with Docker Compose.

## Quick Start

1.  **Clone the repository.**
2.  **Configure Credentials:**
    Create a `.env` file or set environment variables in `docker-compose.yml`.
    ```env
    VOLC_APPID=your_volc_appid
    VOLC_TOKEN=your_volc_token
    VOLC_SECRET=your_volc_secret
    SILICON_KEY=your_silicon_key
    MINIMAX_GROUP_ID=your_minimax_group_id
    MINIMAX_API_KEY=your_minimax_api_key
    ```
3.  **Run with Docker Compose:**
    ```bash
    docker-compose up --build
    ```
4.  **Access:**
    Open `http://localhost:8000`.

## API Documentation

*   **HTTP API:** `http://localhost:8000/docs` (Swagger UI)
*   **WebSocket:** `/ws/chat`

## Development

1.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
2.  **Run Locally:**
    ```bash
    uvicorn main:app --reload
    ```
3.  **Run Tests:**
    ```bash
    pytest
    ```

## Architecture

*   **Frontend:** Vanilla JS, WebSocket, AudioContext.
*   **Backend:** FastAPI, AsyncIO.
*   **Database:** SQLite (Async).

