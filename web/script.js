const chatContainer = document.getElementById('chat-container');
const statusText = document.getElementById('status-text');
const orb = document.getElementById('nova-orb');
const stopBtn = document.getElementById('stop-btn');
const talkBtn = document.getElementById('talk-btn');

// Add a chat message to the UI
function addMessage(text, role) {
    const msgDiv = document.createElement('div');
    msgDiv.classList.add('message');
    
    if (role === 'user') {
        msgDiv.classList.add('msg-user');
        msgDiv.innerText = `🧑 You: ${text}`;
    } else if (role === 'agent') {
        msgDiv.classList.add('msg-agent');
        msgDiv.innerText = `🤖 Nova: ${text}`;
    } else {
        msgDiv.classList.add('msg-info');
        msgDiv.innerText = text;
    }
    
    chatContainer.appendChild(msgDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

// Update the orb animation and status text based on state
function setStatus(status) {
    statusText.innerText = status;
    const s = status.toLowerCase();

    // Show the Stop button while Nova is working (thinking/executing/speaking)
    // so the user can cut her off mid-sentence too.
    if (stopBtn) {
        stopBtn.style.display = (s.includes('thinking') || s.includes('speaking') || s.includes('stopping')) ? 'inline-flex' : 'none';
    }

    // Remove all animation classes
    orb.classList.remove('thinking', 'speaking');

    if (s.includes('thinking') || s.includes('listening')) {
        orb.classList.add('thinking');
        orb.style.filter = "hue-rotate(0deg)";
    } else if (s.includes('speaking')) {
        orb.classList.add('speaking');
    } else {
        orb.style.filter = "";
    }
}

// Eel callbacks from Python
eel.expose(updateStatus);
function updateStatus(status) {
    setStatus(status);
}

eel.expose(addChat);
function addChat(text, role) {
    addMessage(text, role);
}

// UI Triggers to Python
function onTalk() {
    eel.on_talk()();
}

function onSendText() {
    const input = document.getElementById('text-input');
    const text = (input.value || '').trim();
    if (!text) return;
    eel.on_text_input(text)();
    input.value = '';
}

function onWakeToggle(checkbox) {
    eel.on_wake_toggle(checkbox.checked)();
}

function onSetProvider(provider) {
    document.querySelectorAll('#provider-seg .seg-btn').forEach((b) => {
        b.classList.toggle('active', b.dataset.provider === provider);
    });
    eel.on_set_provider(provider)();
}

function onSetLanguage(lang) {
    document.querySelectorAll('#lang-seg .seg-btn').forEach((b) => {
        b.classList.toggle('active', b.dataset.lang === lang);
    });
    eel.on_set_language(lang)();
}

function onStop() {
    eel.on_stop()();
}

// Bind spacebar to push-to-talk, Escape to stop, Enter-in-textbox to send
document.addEventListener('keydown', (e) => {
    const isTextInput = e.target && e.target.id === 'text-input';
    if (isTextInput && e.code === 'Enter') {
        e.preventDefault();
        onSendText();
    } else if (e.code === 'Space' && e.target.tagName !== 'INPUT') {
        e.preventDefault();
        onTalk();
    } else if (e.code === 'Escape') {
        onStop();
    }
});

// Initial greeting
window.onload = () => {
    addMessage("( Nova started — click Push to Talk or press Space, or enable hands-free and say 'Hey Nova'.)", "info");
    setStatus("Ready. Click Push to Talk, or press Space.");
};
