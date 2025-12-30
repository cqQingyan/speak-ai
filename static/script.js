document.addEventListener('DOMContentLoaded', () => {
    const talkBtn = document.getElementById('talk-btn');
    const statusDiv = document.getElementById('status');
    const messagesDiv = document.getElementById('chat-messages');

    let mediaRecorder;
    let audioChunks = [];
    let chatHistory = [];
    let isRecording = false;

    // Check for MediaRecorder support
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        statusDiv.textContent = "您的浏览器不支持录音功能。";
        talkBtn.disabled = true;
        return;
    }

    const startRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' }); // Chrome uses webm by default

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
            isRecording = false;
            talkBtn.classList.remove('recording');
            talkBtn.textContent = "按住说话";
            statusDiv.textContent = "处理中...";
        }
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
                const errorData = await response.json();
                throw new Error(errorData.error || 'Server error');
            }

            const data = await response.json();

            // 1. Add user message
            addMessage(data.user_text, 'user');

            // 2. Add AI message
            addMessage(data.ai_text, 'ai');

            // 3. Update history (keep last 10 turns to avoid token limits)
            chatHistory.push({role: "user", content: data.user_text});
            chatHistory.push({role: "assistant", content: data.ai_text});
            if (chatHistory.length > 20) chatHistory = chatHistory.slice(-20);

            // 4. Play audio
            if (data.audio_base64) {
                statusDiv.textContent = "正在播放...";
                const audio = new Audio("data:audio/mp3;base64," + data.audio_base64);
                audio.onended = () => {
                    statusDiv.textContent = "";
                };
                audio.play();
            } else {
                statusDiv.textContent = "无语音回复";
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

        messageDiv.appendChild(bubbleDiv);
        messagesDiv.appendChild(messageDiv);

        // Scroll to bottom
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    };

    // Mouse events
    talkBtn.addEventListener('mousedown', startRecording);
    talkBtn.addEventListener('mouseup', stopRecording);
    talkBtn.addEventListener('mouseleave', stopRecording); // Stop if mouse leaves button

    // Touch events for mobile
    talkBtn.addEventListener('touchstart', (e) => {
        e.preventDefault(); // Prevent ghost clicks
        startRecording();
    });
    talkBtn.addEventListener('touchend', (e) => {
        e.preventDefault();
        stopRecording();
    });
});
