// ── DOM refs ──

const sidebar = document.getElementById("sidebar");
const sidebarOverlay = document.getElementById("sidebarOverlay");
const sidebarToggleBtn = document.getElementById("sidebarToggleBtn");
const sidebarCloseBtn = document.getElementById("sidebarCloseBtn");
const newChatBtn = document.getElementById("newChatBtn");
const conversationListEl = document.getElementById("conversationList");
const appHeader = document.getElementById("appHeader");
const chatMessages = document.getElementById("chatMessages");
const messagesContainer = document.getElementById("messagesContainer");
const inputArea = document.getElementById("inputArea");
const chatForm = document.getElementById("chatForm");
const messageInput = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const modelSelect = document.getElementById("modelSelect");
const themeToggle = document.getElementById("themeToggle");
const sunIcon = document.getElementById("sunIcon");
const moonIcon = document.getElementById("moonIcon");

// ── State ──

let currentConversationId = null;
let conversations = [];
let sidebarOpen = false;
let models = {};  // id -> {id, name, provider}
let currentAbortController = null;  // for cancelling in-flight streams

// ── Hash routing ──

function setRoute(conversationId) {
    location.hash = conversationId ? `/c/${conversationId}` : "/";
}

function getRouteConversationId() {
    const match = location.hash.match(/^#\/c\/(.+)$/);
    return match ? match[1] : null;
}

// ── Marked configuration ──

const renderer = new marked.Renderer();

renderer.code = function ({ text, lang }) {
    const language = lang || "text";
    const label = language.toUpperCase();
    let highlighted;
    try {
        highlighted =
            lang && hljs.getLanguage(lang)
                ? hljs.highlight(text, { language: lang }).value
                : hljs.highlightAuto(text).value;
    } catch {
        highlighted = escapeHtml(text);
    }
    return `
        <div class="code-block-wrapper group relative my-4">
            <div class="code-block-header">
                <span>${label}</span>
                <button type="button" class="copy-btn" onclick="copyCode(this)" aria-label="Copy code">
                    <svg class="size-3.5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9.75a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184"/>
                    </svg>
                </button>
            </div>
            <div class="code-block-body">
                <pre><code class="hljs language-${language}">${highlighted}</code></pre>
            </div>
        </div>`;
};

renderer.codespan = function ({ text }) {
    return `<code>${text}</code>`;
};

marked.setOptions({ renderer, gfm: true, breaks: true });

function escapeHtml(str) {
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// ── Copy code ──

function copyCode(btn) {
    const wrapper = btn.closest(".code-block-wrapper");
    const code = wrapper.querySelector("pre code").textContent;
    navigator.clipboard.writeText(code).then(() => {
        btn.innerHTML = `<svg class="size-3.5 text-green-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5"/></svg>`;
        setTimeout(() => {
            btn.innerHTML = `<svg class="size-3.5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9.75a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184"/></svg>`;
        }, 2000);
    });
}
window.copyCode = copyCode;

// ── Parse <think> blocks ──

function extractThinkBlocks(text) {
    // Match both <think> and <thinking> tags (closed blocks)
    const closedRegex = /<(?:think|thinking)>([\s\S]*?)<\/(?:think|thinking)>/gi;
    const thinks = [];
    let match;
    while ((match = closedRegex.exec(text)) !== null) {
        thinks.push({ content: match[1].trim(), open: false });
    }
    let cleaned = text.replace(closedRegex, "").trim();

    // Handle unclosed think block (still streaming)
    const unclosedMatch = cleaned.match(/<(?:think|thinking)>([\s\S]*)$/i);
    if (unclosedMatch) {
        thinks.push({ content: unclosedMatch[1].trim(), open: true });
        cleaned = cleaned.slice(0, unclosedMatch.index).trim();
    }

    return { thinks, cleaned };
}

// ── Render markdown ──

function renderMarkdown(el, rawText, { streaming = false } = {}) {
    const { thinks, cleaned } = extractThinkBlocks(rawText);
    const thinkOnly = thinks.length > 0 && !cleaned.trim();
    let html = "";

    if (thinkOnly && !streaming) {
        // Model put everything inside think tags (e.g. Qwen 3) —
        // render think content directly as the main response
        const allContent = thinks.map(t => t.content).join("\n\n");
        html = allContent ? marked.parse(allContent) : "";
    } else {
        for (const think of thinks) {
            const thinkHtml = think.content ? marked.parse(think.content) : "";
            const label = think.open ? "Thinking..." : "Thinking";
            const pulse = think.open ? " animate-pulse" : "";
            // Show preview of first 100 chars in the summary line
            const preview = think.content
                ? escapeHtml(think.content.replace(/\s+/g, " ").slice(0, 100)) + (think.content.length > 100 ? "..." : "")
                : "";
            const previewHtml = preview
                ? `<span class="think-preview">${preview}</span>`
                : "";
            html += `
                <details class="think-block mb-4">
                    <summary class="think-summary">
                        <svg class="size-3.5 shrink-0${pulse}" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18"/>
                        </svg>
                        ${label}
                        ${previewHtml}
                    </summary>
                    <div class="think-content chat-markdown">${thinkHtml}</div>
                </details>`;
        }
        if (cleaned) html += marked.parse(cleaned);
    }
    el.innerHTML = html;
    el.classList.add("chat-markdown");
    if (typeof renderMathInElement === "function") {
        renderMathInElement(el, {
            delimiters: [
                { left: "$$", right: "$$", display: true },
                { left: "$", right: "$", display: false },
                { left: "\\(", right: "\\)", display: false },
                { left: "\\[", right: "\\]", display: true },
            ],
            throwOnError: false,
        });
    }
}

// ── Send / Stop button state ──

const SEND_ICON = `<svg class="size-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M4.5 10.5L12 3m0 0l7.5 7.5M12 3v18"/></svg>`;
const STOP_ICON = `<svg class="size-3.5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>`;

function setStreamingUI(streaming) {
    if (streaming) {
        sendBtn.innerHTML = STOP_ICON;
        sendBtn.disabled = false;
        sendBtn.classList.remove("bg-primary");
        sendBtn.classList.add("bg-destructive");
        messageInput.disabled = true;
    } else {
        sendBtn.innerHTML = SEND_ICON;
        sendBtn.disabled = false;
        sendBtn.classList.remove("bg-destructive");
        sendBtn.classList.add("bg-primary");
        messageInput.disabled = false;
        messageInput.focus();
    }
}

// ── SVG constants ──

const BOT_AVATAR = `
    <div class="h-8 w-8 shrink-0 rounded-full bg-primary/10 flex items-center justify-center">
        <svg class="size-4 text-primary" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z"/>
        </svg>
    </div>`;

const TYPING_INDICATOR = `
    <span class="inline-flex gap-1 items-center">
        <span class="size-1.5 rounded-full bg-current animate-bounce [animation-delay:-0.3s]"></span>
        <span class="size-1.5 rounded-full bg-current animate-bounce [animation-delay:-0.15s]"></span>
        <span class="size-1.5 rounded-full bg-current animate-bounce"></span>
    </span>`;

const EMPTY_STATE_HTML = `
    <div id="emptyState" class="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <div class="h-16 w-16 rounded-full bg-muted flex items-center justify-center">
            <svg class="size-8 text-muted-foreground/50" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z"/>
            </svg>
        </div>
        <div class="text-center">
            <h2 class="text-2xl font-semibold text-foreground">Welcome to Text Analysis</h2>
            <p class="text-sm text-muted-foreground mt-1">Start a conversation to analyze text with AI.</p>
        </div>
    </div>`;

// ── Sidebar ──

function isDesktop() {
    return window.innerWidth >= 768;
}

function setSidebar(open) {
    sidebarOpen = open;
    if (open) {
        sidebar.classList.remove("-translate-x-full");
        sidebar.classList.add("translate-x-0");
        if (isDesktop()) {
            appHeader.style.left = "300px";
            chatMessages.style.marginLeft = "300px";
            inputArea.style.left = "calc(50% + 150px)";
        }
        if (!isDesktop()) {
            sidebarOverlay.classList.remove("hidden");
        }
    } else {
        sidebar.classList.remove("translate-x-0");
        sidebar.classList.add("-translate-x-full");
        appHeader.style.left = "0";
        chatMessages.style.marginLeft = "0";
        inputArea.style.left = "50%";
        sidebarOverlay.classList.add("hidden");
    }
    localStorage.setItem("sidebarOpen", open ? "1" : "0");
}

sidebarToggleBtn.addEventListener("click", () => setSidebar(!sidebarOpen));
sidebarCloseBtn.addEventListener("click", () => setSidebar(false));
sidebarOverlay.addEventListener("click", () => setSidebar(false));

window.addEventListener("resize", () => {
    if (sidebarOpen) {
        if (isDesktop()) {
            sidebarOverlay.classList.add("hidden");
            appHeader.style.left = "300px";
            chatMessages.style.marginLeft = "300px";
            inputArea.style.left = "calc(50% + 150px)";
        } else {
            sidebarOverlay.classList.remove("hidden");
            appHeader.style.left = "0";
            chatMessages.style.marginLeft = "0";
            inputArea.style.left = "50%";
        }
    }
});

// ── Models ──

async function loadModels() {
    try {
        const res = await fetch("/api/inference/models");
        const data = await res.json();
        modelSelect.innerHTML = "";
        for (const model of data.models) {
            models[model.id] = model;
            const opt = document.createElement("option");
            opt.value = model.id;
            opt.textContent = `${model.name} — ${model.provider}`;
            if (model.id === data.default) opt.selected = true;
            modelSelect.appendChild(opt);
        }
        modelSelect.disabled = false;
    } catch {
        modelSelect.innerHTML = "<option>Failed to load models</option>";
    }
}

function getModelLabel(modelId) {
    const m = models[modelId];
    return m ? `${m.name} — ${m.provider}` : modelId || "";
}

// ── Conversations API ──

async function fetchConversations() {
    try {
        const res = await fetch("/api/conversation");
        conversations = await res.json();
        renderConversationList();
    } catch {
        conversations = [];
        renderConversationList();
    }
}

async function createConversation(title) {
    const res = await fetch("/api/conversation", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
    });
    if (!res.ok) throw new Error("Failed to create conversation");
    return await res.json();
}

async function loadConversation(id) {
    const res = await fetch(`/api/conversation/${id}`);
    if (!res.ok) throw new Error("Failed to load conversation");
    const data = await res.json();

    currentConversationId = id;
    setRoute(id);
    clearMessages();
    renderConversationList();

    // Render existing messages
    for (const msg of data.messages || []) {
        if (msg.role === "user") {
            appendMessage("user", msg.content);
        } else {
            const contentDiv = appendMessage("assistant", "", msg.model_id);
            renderMarkdown(contentDiv, msg.content);
        }
    }
    scrollToBottom();

    // Close sidebar on mobile
    if (!isDesktop()) setSidebar(false);
}

async function deleteConversation(id) {
    await fetch(`/api/conversation/${id}`, { method: "DELETE" });
    conversations = conversations.filter((c) => c.id !== id);
    renderConversationList();
    if (currentConversationId === id) {
        currentConversationId = null;
        setRoute(null);
        clearMessages();
        showEmptyState();
    }
}

// ── Conversation list rendering ──

function renderConversationList() {
    conversationListEl.innerHTML = "";
    if (conversations.length === 0) {
        conversationListEl.innerHTML = `
            <p class="text-xs text-muted-foreground text-center py-8">No conversations yet.</p>`;
        return;
    }
    for (const conv of conversations) {
        const isActive = conv.id === currentConversationId;
        const item = document.createElement("div");
        item.className = "group relative";

        item.innerHTML = `
            <div class="px-2.5 py-2 pr-10 rounded-lg cursor-pointer transition-colors
                        ${isActive ? "bg-muted/50" : "hover:bg-muted/20"}"
                 data-id="${conv.id}">
                <h3 class="text-sm truncate ${isActive ? "font-bold" : "font-medium"}"
                    style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
                    ${escapeHtml(conv.title)}
                </h3>
            </div>
            <button type="button"
                    class="delete-conv-btn inline-flex items-center justify-center
                           h-7 w-7 p-0 rounded-md
                           opacity-0 group-hover:opacity-100 transition-opacity
                           absolute right-2 top-1/2 -translate-y-1/2 z-10
                           hover:bg-destructive/10 text-muted-foreground hover:text-destructive
                           cursor-pointer"
                    data-id="${conv.id}"
                    aria-label="Delete conversation">
                <svg class="size-3.5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"/>
                </svg>
            </button>`;

        // Click to load
        item.querySelector("[data-id]").addEventListener("click", () => {
            loadConversation(conv.id);
        });

        // Click to delete
        item.querySelector(".delete-conv-btn").addEventListener("click", (e) => {
            e.stopPropagation();
            deleteConversation(conv.id);
        });

        conversationListEl.appendChild(item);
    }
}

// ── Scroll helper ──

function scrollToBottom() {
    requestAnimationFrame(() => {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    });
}

// ── Copy button helper ──

const COPY_ICON = `<svg class="size-3.5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9.75a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184"/></svg>`;
const CHECK_ICON = `<svg class="size-3.5 text-green-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5"/></svg>`;

function createCopyBtn(sourceEl) {
    const wrap = document.createElement("div");
    wrap.className = "flex items-center gap-1 mt-1 opacity-0 group-hover:opacity-100 transition-opacity";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "inline-flex items-center justify-center size-7 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/50 cursor-pointer transition-colors";
    btn.setAttribute("aria-label", "Copy message");
    btn.innerHTML = COPY_ICON;
    btn.addEventListener("click", () => {
        const text = sourceEl.innerText || sourceEl.textContent;
        navigator.clipboard.writeText(text).then(() => {
            btn.innerHTML = CHECK_ICON;
            setTimeout(() => { btn.innerHTML = COPY_ICON; }, 2000);
        });
    });
    wrap.appendChild(btn);
    return wrap;
}

// ── Message rendering ──

function clearMessages() {
    messagesContainer.innerHTML = "";
}

function showEmptyState() {
    messagesContainer.innerHTML = EMPTY_STATE_HTML;
}

function appendMessage(role, content, modelId) {
    const emptyState = document.getElementById("emptyState");
    if (emptyState) emptyState.remove();

    if (role === "user") {
        const row = document.createElement("div");
        row.className = "group flex flex-col items-end mb-4";
        const bubble = document.createElement("div");
        bubble.className =
            "max-w-[85%] rounded-lg bg-muted/40 py-3 px-3 text-sm whitespace-pre-wrap leading-relaxed break-words";
        bubble.textContent = content;
        row.appendChild(bubble);
        row.appendChild(createCopyBtn(bubble));
        messagesContainer.appendChild(row);
        scrollToBottom();
        return bubble;
    }

    // Assistant
    const row = document.createElement("div");
    row.className = "group flex justify-start items-start gap-3 mb-4";
    row.innerHTML = BOT_AVATAR;

    const wrapper = document.createElement("div");
    wrapper.className = "flex-1 min-w-0";

    // Model badge
    const label = getModelLabel(modelId || modelSelect.value);
    if (label) {
        const badge = document.createElement("span");
        badge.className =
            "inline-block mb-1.5 px-2 py-0.5 text-xs font-medium rounded-md bg-secondary text-secondary-foreground";
        badge.textContent = label;
        wrapper.appendChild(badge);
    }

    const bubble = document.createElement("div");
    bubble.className =
        "py-1 px-1 text-sm leading-relaxed break-words overflow-x-auto max-w-full";
    bubble.textContent = content;

    wrapper.appendChild(bubble);
    wrapper.appendChild(createCopyBtn(bubble));
    row.appendChild(wrapper);
    messagesContainer.appendChild(row);
    scrollToBottom();
    return bubble;
}

// ── Event listeners ──

chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    // If currently streaming, abort instead of sending
    if (currentAbortController) {
        currentAbortController.abort();
        return;
    }
    const text = messageInput.value.trim();
    if (!text) return;
    sendMessage(text);
});

sendBtn.addEventListener("click", (e) => {
    if (currentAbortController) {
        e.preventDefault();
        currentAbortController.abort();
    }
});

messageInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        chatForm.dispatchEvent(new Event("submit"));
    }
});

messageInput.addEventListener("input", () => {
    messageInput.style.height = "auto";
    messageInput.style.height = messageInput.scrollHeight + "px";
});

newChatBtn.addEventListener("click", () => {
    currentConversationId = null;
    setRoute(null);
    clearMessages();
    showEmptyState();
    renderConversationList();
    messageInput.focus();
    if (!isDesktop()) setSidebar(false);
});

// ── Send message ──

async function sendMessage(text) {
    // Create conversation on first message
    if (!currentConversationId) {
        try {
            const title = text.length > 50 ? text.slice(0, 50) + "..." : text;
            const conv = await createConversation(title);
            currentConversationId = conv.id;
            setRoute(conv.id);
            conversations.unshift(conv);
            renderConversationList();
        } catch (err) {
            appendMessage("assistant", `Error creating conversation: ${err.message}`);
            return;
        }
    }

    appendMessage("user", text);
    messageInput.value = "";
    messageInput.style.height = "auto";

    const abortController = new AbortController();
    currentAbortController = abortController;
    setStreamingUI(true);

    const contentDiv = appendMessage("assistant", "", modelSelect.value);
    contentDiv.innerHTML = TYPING_INDICATOR;
    let fullResponse = "";

    try {
        const response = await fetch("/api/inference/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                conversation_id: currentConversationId,
                content: text,
                model_id: modelSelect.value,
            }),
            signal: abortController.signal,
        });

        if (!response.ok) {
            const err = await response.text();
            contentDiv.textContent = `Error: ${err}`;
            return;
        }

        const reader = response.body
            .pipeThrough(new TextDecoderStream())
            .getReader();
        let buffer = "";
        let streamDone = false;
        let renderScheduled = false;

        // Throttle live rendering to once per frame
        const scheduleRender = () => {
            if (!renderScheduled) {
                renderScheduled = true;
                requestAnimationFrame(() => {
                    renderMarkdown(contentDiv, fullResponse, { streaming: true });
                    scrollToBottom();
                    renderScheduled = false;
                });
            }
        };

        while (!streamDone) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += value;
            const lines = buffer.split("\n");
            buffer = lines.pop(); // keep incomplete trailing line

            for (const line of lines) {
                if (!line.startsWith("data: ")) continue;
                const data = line.slice(6).trim();
                if (data === "[DONE]") { streamDone = true; break; }

                try {
                    const parsed = JSON.parse(data);
                    if (parsed.error) {
                        contentDiv.textContent = `Error: ${parsed.error}`;
                        return;
                    }
                    fullResponse += parsed.token;
                    scheduleRender();
                } catch {
                    // skip malformed chunks
                }
            }
        }

        // Final render to ensure complete markdown
        if (fullResponse) {
            renderMarkdown(contentDiv, fullResponse);
            scrollToBottom();
        } else {
            contentDiv.textContent = "No response received from the model.";
        }

        // Refresh conversation list to update ordering
        fetchConversations();
    } catch (err) {
        if (err.name === "AbortError") {
            // User cancelled — render whatever we have so far
            if (fullResponse) {
                renderMarkdown(contentDiv, fullResponse);
            } else {
                contentDiv.textContent = "Generation stopped.";
            }
        } else {
            contentDiv.textContent = `Connection error: ${err.message}`;
        }
    } finally {
        currentAbortController = null;
        setStreamingUI(false);
    }
}

// ── Dark mode ──

function setTheme(dark) {
    document.documentElement.classList.toggle("dark", dark);
    sunIcon.classList.toggle("hidden", !dark);
    moonIcon.classList.toggle("hidden", dark);
    localStorage.setItem("theme", dark ? "dark" : "light");
    document.getElementById("hljs-dark").disabled = !dark;
    document.getElementById("hljs-light").disabled = dark;
}

const storedTheme = localStorage.getItem("theme");
if (
    storedTheme === "dark" ||
    (!storedTheme && window.matchMedia("(prefers-color-scheme: dark)").matches)
) {
    setTheme(true);
}

themeToggle.addEventListener("click", () => {
    setTheme(!document.documentElement.classList.contains("dark"));
});

// ── Init ──

async function init() {
    await loadModels();
    await fetchConversations();

    // Restore conversation from URL hash
    const routeId = getRouteConversationId();
    if (routeId && conversations.some((c) => c.id === routeId)) {
        await loadConversation(routeId);
    }

    // Open sidebar by default on desktop
    if (isDesktop() && localStorage.getItem("sidebarOpen") !== "0") {
        setSidebar(true);
    }
}

init();

// ── Hash routing (back/forward) ──

window.addEventListener("hashchange", () => {
    const id = getRouteConversationId();
    if (id && id !== currentConversationId) {
        loadConversation(id);
    } else if (!id && currentConversationId) {
        currentConversationId = null;
        clearMessages();
        showEmptyState();
        renderConversationList();
    }
});
