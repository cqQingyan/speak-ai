let mediaRecorder;
let audioChunks = [];
let isRecording = false;
let audioContext;
let analyser;
let source;
let animationId;
let token = localStorage.getItem('access_token');

// DOM Elements
const talkBtn = document.getElementById('talk-btn');
const statusDiv = document.getElementById('status');
const chatMessages = document.getElementById('chat-messages');
const visualizer = document.getElementById('visualizer');
const canvasCtx = visualizer.getContext('2d');
const clearBtn = document.getElementById('clear-btn');
const settingsBtn = document.getElementById('settings-btn');
const settingsPanel = document.getElementById('settings-panel');
const inputModeSelect = document.getElementById('input-mode');
const voiceSelect = document.getElementById('voice-select');
const voiceControls = document.getElementById('voice-controls');
const textControls = document.getElementById('text-controls');
const textInput = document.getElementById('text-input');
const sendTextBtn = document.getElementById('send-text-btn');

// Auth Elements
const authModal = document.getElementById('auth-modal');
const usernameInput = document.getElementById('username');
const passwordInput = document.getElementById('password');
const loginBtn = document.getElementById('login-btn');
const registerBtn = document.getElementById('register-btn');
const authMsg = document.getElementById('auth-msg');
const logoutBtn = document.getElementById('logout-btn');

// State
let chatHistory = [];
let audioQueue = [];
let isPlaying = false;

// --- Auth Logic ---
if (token) {
    authModal.style.display = "none";
}

async function handleAuth(endpoint) {
    const username = usernameInput.value;
    const password = passwordInput.value;

    if(!username || !password) {
        authMsg.textContent = "Please enter username and password.";
        return;
    }

    try {
        let body;
        let headers = {};

        if (endpoint.includes('token')) {
            // OAuth2 expects form data
            body = new URLSearchParams();
            body.append('username', username);
            body.append('password', password);
            headers['Content-Type'] = 'application/x-www-form-urlencoded';
        } else {
            body = JSON.stringify({ username, password });
            headers['Content-Type'] = 'application/json';
        }

        const response = await fetch(endpoint, {
            method: 'POST',
            headers: headers,
            body: body
        });

        const data = await response.json();

        if (response.ok) {
            token = data.access_token;
            localStorage.setItem('access_token', token);
            authModal.style.display = "none";
            authMsg.textContent = "";
        } else {
            authMsg.textContent = data.detail || "Error";
        }
    } catch (e) {
        authMsg.textContent = "Network Error";
    }
}

loginBtn.addEventListener('click', () => handleAuth('/api/auth/token'));
registerBtn.addEventListener('click', () => handleAuth('/api/auth/register'));
logoutBtn.addEventListener('click', () => {
    localStorage.removeItem('access_token');
    location.reload();
});

// --- UI Logic ---
settingsBtn.addEventListener('click', () => {
    settingsPanel.style.display = settingsPanel.style.display === 'block' ? 'none' : 'block';
});

inputModeSelect.addEventListener('change', (e) => {
    if(e.target.value === 'text') {
        voiceControls.style.display = 'none';
        textControls.style.display = 'flex';
        // Force hidden class removal if used
        textControls.classList.remove('hidden');
    } else {
        voiceControls.style.display = 'block';
        textControls.style.display = 'none';
        textControls.classList.add('hidden');
    }
});

// --- Audio Logic ---

// Initialize Audio Context (must be triggered by user interaction)
function initAudio() {
    if (!audioContext) {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        analyser = audioContext.createAnalyser();
        analyser.fftSize = 256;
    }
}

// Visualizer
function drawVisualizer() {
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    function draw() {
        if (!isRecording) return;
        animationId = requestAnimationFrame(draw);

        analyser.getByteFrequencyData(dataArray);

        canvasCtx.fillStyle = 'rgb(240, 240, 240)';
        canvasCtx.fillRect(0, 0, visualizer.width, visualizer.height);

        const barWidth = (visualizer.width / bufferLength) * 2.5;
        let barHeight;
        let x = 0;

        for(let i = 0; i < bufferLength; i++) {
            barHeight = dataArray[i] / 2;

            canvasCtx.fillStyle = 'rgb(50,50,' + (barHeight+100) + ')';
            canvasCtx.fillRect(x, visualizer.height-barHeight, barWidth, barHeight);

            x += barWidth + 1;
        }
    }
    draw();
}

// Recording
talkBtn.addEventListener('mousedown', async () => {
    if (!token) return alert("Please login first");
    initAudio();
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream); // Default browser format (likely webm)
        audioChunks = [];

        source = audioContext.createMediaStreamSource(stream);
        source.connect(analyser);

        mediaRecorder.ondataavailable = (event) => {
            audioChunks.push(event.data);
        };

        mediaRecorder.start();
        isRecording = true;
        statusDiv.textContent = "正在录音...";
        talkBtn.classList.add('recording');
        drawVisualizer();

    } catch (err) {
        console.error("Error accessing microphone:", err);
        statusDiv.textContent = "无法访问麦克风";
    }
});

talkBtn.addEventListener('mouseup', () => {
    if (isRecording && mediaRecorder) {
        mediaRecorder.stop();
        isRecording = false;
        statusDiv.textContent = "处理中...";
        talkBtn.classList.remove('recording');
        cancelAnimationFrame(animationId);

        // Stop all tracks
        mediaRecorder.stream.getTracks().forEach(track => track.stop());

        mediaRecorder.onstop = async () => {
            const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
            await processAudio(audioBlob);
        };
    }
});

// Text Input
sendTextBtn.addEventListener('click', async () => {
    const text = textInput.value;
    if(!text) return;

    // UI Update immediately
    // addMessage('user', text); // Don't add twice, meta event will add it.
    // Actually, usually good to add immediately for UI responsiveness, but our stream returns meta first.
    // Let's wait for meta or add pending.
    // Let's add it but manage duplication?
    // The `handleStreamData` adds message. If I add here, I get double.
    // I will NOT add here, and let the server response drive UI.
    // Or I can add here and ignore 'user_text' from meta if I track it.
    // Simple way: Clear input, let server echo back.
    textInput.value = '';

    try {
        const voiceId = voiceSelect.value;
        const body = JSON.stringify({
            text: text,
            history: chatHistory,
            voice_id: voiceId,
            temperature: 0.7
        });

        const response = await fetch('/api/process_text', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: body
        });

        await handleResponseStream(response);

    } catch (e) {
        console.error("Text Chat Failed", e);
        statusDiv.textContent = "发送失败";
    }
});

async function processAudio(audioBlob) {
    const formData = new FormData();
    formData.append("audio", audioBlob, "recording.webm");
    formData.append("history", JSON.stringify(chatHistory));
    formData.append("voice_id", voiceSelect.value);
    formData.append("temperature", "0.7"); // Could be dynamic

    try {
        const response = await fetch('/api/process_audio', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            },
            body: formData
        });

        await handleResponseStream(response);

    } catch (e) {
        console.error("Upload failed", e);
        statusDiv.textContent = "网络错误，请重试";
    }
}

async function handleResponseStream(response) {
        if (response.status === 401) {
             authModal.style.display = "block";
             statusDiv.textContent = "请重新登录";
             return;
        }

        if (!response.ok) {
            const err = await response.text();
            console.error("Server Error:", err);
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop(); // Keep incomplete line

            for (const line of lines) {
                if (!line) continue;
                try {
                    const data = JSON.parse(line);
                    handleStreamData(data);
                } catch (e) {
                    console.error("JSON Parse Error", e);
                }
            }
        }

        statusDiv.textContent = "完成";
}

        if (response.status === 401) {
             authModal.style.display = "block";
             statusDiv.textContent = "请重新登录";
             return;
        }

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop(); // Keep incomplete line

            for (const line of lines) {
                if (!line) continue;
                try {
                    const data = JSON.parse(line);
                    handleStreamData(data);
                } catch (e) {
                    console.error("JSON Parse Error", e);
                }
            }
        }

        statusDiv.textContent = "完成";

    } catch (e) {
        console.error("Upload failed", e);
        statusDiv.textContent = "网络错误，请重试";
    }
}

function handleStreamData(data) {
    if (data.type === 'meta') {
        addMessage('user', data.user_text);
        addMessage('ai', data.ai_text);

        // Update History
        chatHistory.push({role: "user", content: data.user_text});
        chatHistory.push({role: "assistant", content: data.ai_text});
    } else if (data.type === 'audio') {
        queueAudio(data.data);
    }
}

function addMessage(role, text) {
    const div = document.createElement('div');
    div.className = `message ${role}`;
    div.innerHTML = `<div class="bubble">${text}</div><div class="timestamp">${new Date().toLocaleTimeString()}</div>`;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function queueAudio(base64Data) {
    audioQueue.push(base64Data);
    if (!isPlaying) {
        playNextAudio();
    }
}

async function playNextAudio() {
    if (audioQueue.length === 0) {
        isPlaying = false;
        return;
    }

    isPlaying = true;
    const base64Data = audioQueue.shift();
    const audioBytes = Uint8Array.from(atob(base64Data), c => c.charCodeAt(0));

    try {
        const audioBuffer = await audioContext.decodeAudioData(audioBytes.buffer);
        const source = audioContext.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(audioContext.destination);
        source.onended = playNextAudio;
        source.start(0);
    } catch (e) {
        console.error("Audio Decode Error", e);
        playNextAudio();
    }
}

clearBtn.addEventListener('click', () => {
    chatHistory = [];
    chatMessages.innerHTML = '';
});
