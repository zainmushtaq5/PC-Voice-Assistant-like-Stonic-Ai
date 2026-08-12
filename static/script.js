document.addEventListener('DOMContentLoaded', () => {
    const orb = document.getElementById('orb');
    const recordBtn = document.getElementById('record-btn');
    const btnText = document.getElementById('btn-text');
    const statusText = document.getElementById('status');
    const chatContainer = document.getElementById('chat-container');
    const sysBanner = document.getElementById('sys-banner');

    let mediaRecorder;
    let audioChunks = [];
    let isRecording = false;
    let stream = null;

    checkStatus();

    function checkStatus() {
        fetch('/api/status')
            .then(r => r.json())
            .then(data => {
                if (!data.ok && sysBanner) {
                    sysBanner.textContent = 'Ollama is not reachable: ' + (data.error || 'unknown error');
                    sysBanner.style.display = 'block';
                } else if (sysBanner && data.model) {
                    sysBanner.textContent = 'Model: ' + data.model;
                    sysBanner.style.display = 'block';
                }
            })
            .catch(() => {});
    }

    navigator.mediaDevices.getUserMedia({ audio: true })
        .then(mediaStream => {
            stream = mediaStream;
            setupRecorder(mediaStream);
            initPulse(mediaStream);
        })
        .catch(err => {
            console.error("Microphone access denied:", err);
            statusText.innerText = "Microphone Denied";
            recordBtn.disabled = true;
        });

    function setupRecorder(mediaStream) {
        const options = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus'];
        let chosen = {};
        for (const type of options) {
            if (MediaRecorder.isTypeSupported(type)) {
                chosen = { mimeType: type };
                break;
            }
        }
        mediaRecorder = new MediaRecorder(mediaStream, chosen);

        mediaRecorder.ondataavailable = e => {
            if (e.data && e.data.size > 0) audioChunks.push(e.data);
        };

        mediaRecorder.onstop = () => {
            const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
            audioChunks = [];
            sendAudioToBackend(audioBlob);
        };
    }

    function setState(state) {
        orb.className = 'orb';
        if (state === 'listening') {
            orb.classList.add('listening');
            statusText.innerText = 'Listening...';
            recordBtn.classList.add('recording');
            btnText.innerText = 'Stop Listening';
        } else if (state === 'thinking') {
            orb.classList.add('thinking');
            statusText.innerText = 'Thinking...';
            recordBtn.classList.remove('recording');
            btnText.innerText = 'Listening Again';
        } else if (state === 'speaking') {
            orb.classList.add('speaking');
            statusText.innerText = 'Speaking...';
            recordBtn.classList.remove('recording');
            btnText.innerText = 'Listening Again';
        } else {
            orb.classList.remove('listening', 'thinking', 'speaking');
            statusText.innerText = 'Idle';
            recordBtn.classList.remove('recording');
            btnText.innerText = 'Start Listening';
        }
    }

    recordBtn.addEventListener('click', () => {
        if (!mediaRecorder) return;
        if (!isRecording) {
            mediaRecorder.start();
            isRecording = true;
            setState('listening');
        } else {
            mediaRecorder.stop();
            isRecording = false;
            setState('thinking');
        }
    });

    function appendMessage(role, text) {
        if (!text) return;
        const div = document.createElement('div');
        div.className = `msg ${role}`;
        div.innerText = text;
        chatContainer.appendChild(div);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }


    function playBase64Audio(b64) {
        if (!b64) {
            setState('idle');
            return;
        }
        const byteString = atob(b64);
        const bytes = new Uint8Array(byteString.length);
        for (let i = 0; i < byteString.length; i++) bytes[i] = byteString.charCodeAt(i);
        const audioBlob = new Blob([bytes], { type: 'audio/wav' });
        const url = URL.createObjectURL(audioBlob);
        const audio = new Audio(url);
        setState('speaking');
        audio.onended = () => {
            URL.revokeObjectURL(url);
            setState('idle');
        };
        audio.onerror = () => setState('idle');
        audio.play().catch(() => setState('idle'));
    }

    async function sendAudioToBackend(audioBlob) {
        const formData = new FormData();
        formData.append('audio', audioBlob, 'recording.webm');

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                body: formData
            });

            const data = await response.json().catch(() => ({}));

            if (!response.ok) {
                throw new Error(data.error || "Server returned an error");
            }

            if (data.text) appendMessage('user', data.text);
            if (data.response) appendMessage('agent', data.response);
            playBase64Audio(data.audio || '');

        } catch (error) {
            console.error(error);
            statusText.innerText = 'Error processing request';
            orb.className = 'orb';
            btnText.innerText = 'Start Listening';
        }
    }

    // Live volume indicator: the orb pulses with your voice while listening.
    function initPulse(mediaStream) {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const analyser = ctx.createAnalyser();
        const source = ctx.createMediaStreamSource(mediaStream);
        source.connect(analyser);
        analyser.fftSize = 256;
        const data = new Uint8Array(analyser.frequencyBinCount);

        (function pump() {
            if (isRecording && orb.classList.contains('listening')) {
                analyser.getByteFrequencyData(data);
                const avg = data.reduce((a, b) => a + b, 0) / data.length;
                orb.style.transform = `scale(${0.9 + (avg / 160) * 0.4})`;
            } else {
                orb.style.transform = '';
            }
            requestAnimationFrame(pump);
        })();
    }
});
