const chatMessages = document.getElementById("chatMessages");
const chatForm = document.getElementById("chatForm");
const messageInput = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const modelSelect = document.getElementById("modelSelect");

const conversationHistory = [];

// Load available models on startup
async function loadModels() {
    try {
        const res = await fetch("/api/inference/models");
        const data = await res.json();

        modelSelect.innerHTML = "";
        for (const model of data.models) {
            const opt = document.createElement("option");
            opt.value = model.id;
            opt.textContent = `${model.name} — ${model.provider}`;
            if (model.id === data.default) opt.selected = true;
            modelSelect.appendChild(opt);
        }
        modelSelect.disabled = false;
    } catch {
        modelSelect.innerHTML = '<option>Failed to load models</option>';
    }
}

loadModels();

chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = messageInput.value.trim();
    if (!text) return;
    sendMessage(text);
});

messageInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        chatForm.dispatchEvent(new Event("submit"));
    }
});

// Auto-resize textarea
messageInput.addEventListener("input", () => {
    messageInput.style.height = "auto";
    messageInput.style.height = messageInput.scrollHeight + "px";
});

function appendMessage(role, content) {
    const div = document.createElement("div");
    div.className = `message ${role}`;
    div.textContent = content;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return div;
}

async function sendMessage(text) {
    // Add user message
    conversationHistory.push({ role: "user", content: text });
    appendMessage("user", text);
    messageInput.value = "";
    messageInput.style.height = "auto";

    // Disable input while streaming
    sendBtn.disabled = true;
    messageInput.disabled = true;
    modelSelect.disabled = true;

    // Create assistant message bubble
    const assistantDiv = appendMessage("assistant", "");

    try {
        const response = await fetch("/api/inference/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                messages: conversationHistory,
                model: modelSelect.value,
            }),
        });

        if (!response.ok) {
            const err = await response.text();
            assistantDiv.textContent = `Error: ${err}`;
            return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullResponse = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            const lines = chunk.split("\n");

            for (const line of lines) {
                if (!line.startsWith("data: ")) continue;
                const data = line.slice(6);
                if (data === "[DONE]") break;

                try {
                    const parsed = JSON.parse(data);
                    fullResponse += parsed.token;
                    assistantDiv.textContent = fullResponse;
                    chatMessages.scrollTop = chatMessages.scrollHeight;
                } catch {
                    // skip malformed chunks
                }
            }
        }

        conversationHistory.push({ role: "assistant", content: fullResponse });
    } catch (err) {
        assistantDiv.textContent = `Connection error: ${err.message}`;
    } finally {
        sendBtn.disabled = false;
        messageInput.disabled = false;
        modelSelect.disabled = false;
        messageInput.focus();
    }
}
