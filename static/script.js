document.addEventListener('DOMContentLoaded', () => {
    // Auth Logic
    const authModal = document.getElementById('auth-modal');
    const authTitle = document.getElementById('auth-title');
    const usernameInput = document.getElementById('username');
    const passwordInput = document.getElementById('password');
    const emailInput = document.getElementById('email');
    const authSubmitBtn = document.getElementById('auth-submit-btn');
    const toggleAuthModeBtn = document.getElementById('toggle-auth-mode');
    const loginError = document.getElementById('login-error');

    let isRegisterMode = false;
    let jwtToken = localStorage.getItem('access_token');

    // UI Elements
    const talkBtn = document.getElementById('talk-btn');
    const statusDiv = document.getElementById('status');
    const messagesDiv = document.getElementById('chat-messages');
    const clearBtn = document.getElementById('clear-btn');
    const exportBtn = document.getElementById('export-btn');
    const visualizerCanvas = document.getElementById('visualizer');
    const canvasCtx = visualizerCanvas.getContext('2d');

    // State
    let mediaRecorder;
    let isRecording = false;
    let ws = null;
    let audioContext;
    let analyser;
    let microphone;
    let javascriptNode;
    let chatHistory = [];
    let audioQueue = [];
    let isPlaying = false;
    let currentAiMessageDiv = null;

    // Check Auth
    if (jwtToken) {
        authModal.style.display = 'none';
        initWebSocket();
    }

    toggleAuthModeBtn.addEventListener('click', (e) => {
        e.preventDefault();
        isRegisterMode = !isRegisterMode;
        if (isRegisterMode) {
            authTitle.textContent = "注册";
            authSubmitBtn.textContent = "注册";
            toggleAuthModeBtn.textContent = "已有账号？去登录";
            emailInput.style.display = 'block';
        } else {
            authTitle.textContent = "登录";
            authSubmitBtn.textContent = "登录";
            toggleAuthModeBtn.textContent = "没有账号？去注册";
            emailInput.style.display = 'none';
        }
    });

    authSubmitBtn.addEventListener('click', async () => {
        const username = usernameInput.value;
        const password = passwordInput.value;
        const email = emailInput.value;

        const endpoint = isRegisterMode ? '/auth/register' : '/auth/login';
        const body = isRegisterMode ? { username, password, email } : { username, password };

        try {
            const res = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });

            const data = await res.json();
            if (res.ok) {
                jwtToken = data.access_token;
                localStorage.setItem('access_token', jwtToken);
                authModal.style.display = 'none';
                initWebSocket();
            } else {
                loginError.textContent = data.detail || "Authentication Failed";
            }
        } catch (e) {
            loginError.textContent = "Network Error";
        }
    });

    function initWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/chat?token=${jwtToken}`;

        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            console.log("WebSocket Connected");
            statusDiv.textContent = "连接成功，请按住说话";
        };

        ws.onclose = () => {
            console.log("WebSocket Disconnected");
            statusDiv.textContent = "连接断开，尝试重连...";
            setTimeout(initWebSocket, 3000);
        };

        ws.onmessage = async (event) => {
            // Handle binary audio (TTS)
            if (event.data instanceof Blob) {
                const arrayBuffer = await event.data.arrayBuffer();
                audioQueue.push(arrayBuffer);
                if (!isPlaying) {
                    playNextAudioChunk();
                }
                return;
            }

            // Handle text/json
            try {
                const data = JSON.parse(event.data);
                handleWsMessage(data);
            } catch (e) {
                console.error("WS Parse Error", e);
            }
        };
    }

    function handleWsMessage(data) {
        if (data.type === 'asr_partial') {
            statusDiv.textContent = `听: ${data.text}`;
        } else if (data.type === 'asr_final') {
            addMessage(data.text, 'user');
            statusDiv.textContent = "思考中...";
            // Create placeholder for AI response
            currentAiMessageDiv = addMessage("...", 'ai');
        } else if (data.type === 'llm_token') {
            if (currentAiMessageDiv) {
                const bubble = currentAiMessageDiv.querySelector('.bubble');
                if (bubble.textContent === "...") bubble.textContent = "";
                bubble.textContent += data.text;
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            }
        } else if (data.type === 'turn_end') {
            statusDiv.textContent = "准备就绪";
            currentAiMessageDiv = null;
        } else if (data.type === 'error') {
            statusDiv.textContent = `错误: ${data.message}`;
            addMessage(`Error: ${data.message}`, 'ai');
        }
    }

    function playNextAudioChunk() {
        if (audioQueue.length === 0) {
            isPlaying = false;
            return;
        }
        isPlaying = true;
        const chunk = audioQueue.shift();

        // Use AudioContext to play raw PCM/MP3 chunks seamlessly?
        // Simple HTML5 Audio with Blob URL for now (might have gaps)
        // Better: SourceBuffer with MediaSource Extensions (MSE) for streaming.
        // Or decodeAudioData with AudioContext (best for seamless chunks).

        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        audioCtx.decodeAudioData(chunk, (buffer) => {
            const source = audioCtx.createBufferSource();
            source.buffer = buffer;
            source.connect(audioCtx.destination);
            source.onended = () => {
                playNextAudioChunk();
            };
            source.start(0);
        }, (e) => {
            console.error("Audio Decode Error", e);
            playNextAudioChunk();
        });
    }

    function addMessage(text, sender) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', sender);

        const bubbleDiv = document.createElement('div');
        bubbleDiv.classList.add('bubble');
        bubbleDiv.textContent = text;

        const timestampDiv = document.createElement('div');
        timestampDiv.classList.add('timestamp');
        const now = new Date();
        timestampDiv.textContent = now.getHours().toString().padStart(2, '0') + ':' + now.getMinutes().toString().padStart(2, '0');

        messageDiv.appendChild(bubbleDiv);
        messageDiv.appendChild(timestampDiv);
        messagesDiv.appendChild(messageDiv);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
        return messageDiv;
    }

    // Recording Logic
    const startRecording = async () => {
        if (!ws || ws.readyState !== WebSocket.OPEN) {
            statusDiv.textContent = "未连接服务器";
            return;
        }

        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            setupVisualizer(stream);

            // Use MediaRecorder with small timeslice to stream chunks
            const mimeType = 'audio/webm;codecs=opus'; // Supported by Chrome/Firefox
            mediaRecorder = new MediaRecorder(stream, { mimeType });

            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0 && ws.readyState === WebSocket.OPEN) {
                    ws.send(event.data);
                }
            };

            mediaRecorder.start(100); // Send chunk every 100ms
            isRecording = true;
            talkBtn.classList.add('recording');
            talkBtn.textContent = "松开 发送";
            statusDiv.textContent = "正在聆听...";

        } catch (err) {
            console.error("Mic Error:", err);
            statusDiv.textContent = "麦克风访问失败";
        }
    };

    const stopRecording = () => {
        if (mediaRecorder && isRecording) {
            mediaRecorder.stop();
            mediaRecorder.stream.getTracks().forEach(track => track.stop());
            stopVisualizer();

            // Send Finish Signal
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ "action": "finish_speaking" }));
            }

            isRecording = false;
            talkBtn.classList.remove('recording');
            talkBtn.textContent = "按住说话";
        }
    };

    // UI Events
    talkBtn.addEventListener('mousedown', startRecording);
    talkBtn.addEventListener('mouseup', stopRecording);
    talkBtn.addEventListener('mouseleave', stopRecording);
    talkBtn.addEventListener('touchstart', (e) => { e.preventDefault(); startRecording(); });
    talkBtn.addEventListener('touchend', (e) => { e.preventDefault(); stopRecording(); });

    // Clear History
    clearBtn.addEventListener('click', () => {
        if(confirm("确定清除?")) { messagesDiv.innerHTML = ''; }
    });

    // Visualizer Setup (Same as before)
    const setupVisualizer = (stream) => {
        if (!audioContext) audioContext = new (window.AudioContext || window.webkitAudioContext)();
        if (audioContext.state === 'suspended') audioContext.resume();
        analyser = audioContext.createAnalyser();
        microphone = audioContext.createMediaStreamSource(stream);
        javascriptNode = audioContext.createScriptProcessor(2048, 1, 1);
        analyser.smoothingTimeConstant = 0.8;
        analyser.fftSize = 1024;
        microphone.connect(analyser);
        analyser.connect(javascriptNode);
        javascriptNode.connect(audioContext.destination);
        javascriptNode.onaudioprocess = () => {
            const array = new Uint8Array(analyser.frequencyBinCount);
            analyser.getByteTimeDomainData(array);
            canvasCtx.fillStyle = '#f9f9f9';
            canvasCtx.fillRect(0, 0, visualizerCanvas.width, visualizerCanvas.height);
            canvasCtx.lineWidth = 2;
            canvasCtx.strokeStyle = '#007bff';
            canvasCtx.beginPath();
            const sliceWidth = visualizerCanvas.width * 1.0 / array.length;
            let x = 0;
            for (let i = 0; i < array.length; i++) {
                const v = array[i] / 128.0;
                const y = v * visualizerCanvas.height / 2;
                if (i === 0) canvasCtx.moveTo(x, y);
                else canvasCtx.lineTo(x, y);
                x += sliceWidth;
            }
            canvasCtx.lineTo(visualizerCanvas.width, visualizerCanvas.height / 2);
            canvasCtx.stroke();
        };
    };
    const stopVisualizer = () => {
        if (javascriptNode) { javascriptNode.disconnect(); javascriptNode = null; }
        if (microphone) { microphone.disconnect(); microphone = null; }
        if (analyser) { analyser.disconnect(); analyser = null; }
        canvasCtx.clearRect(0, 0, visualizerCanvas.width, visualizerCanvas.height);
    };
});
