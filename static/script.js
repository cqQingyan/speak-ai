document.addEventListener('DOMContentLoaded', () => {
    const talkBtn = document.getElementById('talk-btn');
    const statusDiv = document.getElementById('status');
    const messagesDiv = document.getElementById('chat-messages');
    const clearBtn = document.getElementById('clear-btn');
    const exportBtn = document.getElementById('export-btn');
    const visualizerCanvas = document.getElementById('visualizer');
    const canvasCtx = visualizerCanvas.getContext('2d');

    let mediaRecorder;
    let audioChunks = [];
    let chatHistory = [];
    let isRecording = false;
    let audioQueue = [];
    let isPlaying = false;

    // Audio Context for Visualization
    let audioContext;
    let analyser;
    let microphone;
    let javascriptNode;

    // Service Worker Registration
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/static/sw.js')
            .then(registration => {
                console.log('ServiceWorker registration successful with scope: ', registration.scope);
            })
            .catch(err => {
                console.log('ServiceWorker registration failed: ', err);
            });
    }

    // Initialize UI
    const now = new Date();
    const timeStr = now.getHours().toString().padStart(2, '0') + ':' + now.getMinutes().toString().padStart(2, '0');
    if (document.querySelector('.message.ai .timestamp')) {
        document.querySelector('.message.ai .timestamp').textContent = timeStr;
    }

    // Check for MediaRecorder support
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        statusDiv.textContent = "您的浏览器不支持录音功能。";
        talkBtn.disabled = true;
        return;
    }

    // Visualization Function
    const setupVisualizer = (stream) => {
        if (!audioContext) {
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
        }

        // Ensure AudioContext is running (mobile browsers suspend it)
        if (audioContext.state === 'suspended') {
            audioContext.resume();
        }

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

            canvasCtx.fillStyle = '#f9f9f9'; // bg color
            canvasCtx.fillRect(0, 0, visualizerCanvas.width, visualizerCanvas.height);

            canvasCtx.lineWidth = 2;
            canvasCtx.strokeStyle = '#007bff';
            canvasCtx.beginPath();

            const sliceWidth = visualizerCanvas.width * 1.0 / array.length;
            let x = 0;

            for (let i = 0; i < array.length; i++) {
                const v = array[i] / 128.0;
                const y = v * visualizerCanvas.height / 2;

                if (i === 0) {
                    canvasCtx.moveTo(x, y);
                } else {
                    canvasCtx.lineTo(x, y);
                }

                x += sliceWidth;
            }

            canvasCtx.lineTo(visualizerCanvas.width, visualizerCanvas.height / 2);
            canvasCtx.stroke();
        };
    };

    const stopVisualizer = () => {
        if (javascriptNode) {
            javascriptNode.disconnect();
            javascriptNode = null;
        }
        if (microphone) {
            microphone.disconnect();
            microphone = null;
        }
        if (analyser) {
            analyser.disconnect();
            analyser = null;
        }
        // clear canvas
        canvasCtx.fillStyle = '#f9f9f9';
        canvasCtx.fillRect(0, 0, visualizerCanvas.width, visualizerCanvas.height);
    };

    const startRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

            setupVisualizer(stream);

            mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });

            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    audioChunks.push(event.data);
                }
            };

            mediaRecorder.onstop = sendAudio;

            audioChunks = [];
            mediaRecorder.start();
            isRecording = true;
            talkBtn.classList.add('recording');
            talkBtn.textContent = "松开 发送";
            statusDiv.textContent = "正在录音...";
        } catch (err) {
            console.error("Error accessing microphone:", err);
            statusDiv.textContent = "无法访问麦克风。";
        }
    };

    const stopRecording = () => {
        if (mediaRecorder && isRecording) {
            mediaRecorder.stop();
            // Stop all tracks to release microphone
            mediaRecorder.stream.getTracks().forEach(track => track.stop());
            stopVisualizer();

            isRecording = false;
            talkBtn.classList.remove('recording');
            talkBtn.textContent = "按住说话";
            statusDiv.textContent = "处理中...";
        }
    };

    const playNextAudioChunk = () => {
        if (audioQueue.length === 0) {
            isPlaying = false;
            statusDiv.textContent = "";
            return;
        }

        isPlaying = true;
        statusDiv.textContent = "正在播放...";
        const base64Data = audioQueue.shift();
        const audio = new Audio("data:audio/mp3;base64," + base64Data);
        audio.onended = playNextAudioChunk;
        audio.play().catch(e => {
            console.error("Audio play error:", e);
            playNextAudioChunk();
        });
    };

    const sendAudio = async () => {
        const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
        const formData = new FormData();
        formData.append('audio', audioBlob, 'recording.webm');
        formData.append('history', JSON.stringify(chatHistory));

        try {
            const response = await fetch('/api/process_audio', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || 'Server error');
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder("utf-8");
            let buffer = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split("\n");
                buffer = lines.pop(); // Keep last incomplete line

                for (const line of lines) {
                    if (!line.trim()) continue;
                    try {
                        const data = JSON.parse(line);
                        if (data.type === 'meta') {
                            addMessage(data.user_text, 'user');
                            addMessage(data.ai_text, 'ai');

                            chatHistory.push({role: "user", content: data.user_text});
                            chatHistory.push({role: "assistant", content: data.ai_text});
                            if (chatHistory.length > 20) chatHistory = chatHistory.slice(-20);
                        } else if (data.type === 'audio') {
                            audioQueue.push(data.data);
                            if (!isPlaying) {
                                playNextAudioChunk();
                            }
                        }
                    } catch (e) {
                        console.error("JSON Parse Error", e);
                    }
                }
            }

        } catch (error) {
            console.error("Error sending audio:", error);
            statusDiv.textContent = "发生错误: " + error.message;
            addMessage("Error: " + error.message, 'ai');
        }
    };

    const addMessage = (text, sender) => {
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
    };

    // Clear History
    clearBtn.addEventListener('click', () => {
        if(confirm("确定要清除聊天记录吗？")) {
             chatHistory = [];
             messagesDiv.innerHTML = '<div class="message ai"><div class="bubble">聊天记录已清除。</div><div class="timestamp">' +
             (new Date()).getHours().toString().padStart(2, '0') + ':' + (new Date()).getMinutes().toString().padStart(2, '0') + '</div></div>';
        }
    });

    // Export History
    exportBtn.addEventListener('click', () => {
        const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(chatHistory, null, 2));
        const downloadAnchorNode = document.createElement('a');
        downloadAnchorNode.setAttribute("href", dataStr);
        downloadAnchorNode.setAttribute("download", "chat_history_" + new Date().toISOString() + ".json");
        document.body.appendChild(downloadAnchorNode); // required for firefox
        downloadAnchorNode.click();
        downloadAnchorNode.remove();
    });

    talkBtn.addEventListener('mousedown', startRecording);
    talkBtn.addEventListener('mouseup', stopRecording);
    talkBtn.addEventListener('mouseleave', stopRecording);

    talkBtn.addEventListener('touchstart', (e) => {
        e.preventDefault();
        startRecording();
    });
    talkBtn.addEventListener('touchend', (e) => {
        e.preventDefault();
        stopRecording();
    });
});
