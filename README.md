# Voice Assistant

A voice assistant web application built with Python FastAPI and Vanilla JS. Supports Audio Recording, ASR, LLM Chat, and Streaming TTS.

## Features

- **Voice Interaction:** Push-to-talk recording with waveform visualization.
- **AI Chat:** Uses SiliconFlow (DeepSeek) for intelligence.
- **Streaming TTS:** Low latency audio response using Minimax API.
- **Chat History:** Save/Clear/Export chat history.
- **Mobile Friendly:** PWA support, optimized touch controls.
- **Performance:** Async backend, caching for TTS.

## Installation

1. Clone the repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file with your API keys:
   ```env
   SILICON_KEY=your_siliconflow_key
   MINIMAX_GROUP_ID=your_minimax_group_id
   MINIMAX_API_KEY=your_minimax_api_key
   ```

## Usage

Run the server:
```bash
python main.py
```
Or with uvicorn directly:
```bash
uvicorn main:app --reload
```

Open `http://localhost:8000` in your browser.

## Testing

Run tests with pytest:
```bash
pytest
```
