/**
 * script.js - AI Assist Chatbot Frontend
 * Handles UI interactions, API communication, animations, and state management.
 */
(function () {
  'use strict';

  // ======================================================================
  // DOM References
  // ======================================================================
  const messagesContainer = document.getElementById('messagesContainer');
  const chatInput = document.getElementById('chatInput');
  const sendBtn = document.getElementById('sendBtn');
  const typingIndicator = document.getElementById('typingIndicator');
  const sidebar = document.getElementById('sidebar');
  const sidebarOverlay = document.getElementById('sidebarOverlay');
  const sidebarToggle = document.getElementById('sidebarToggle');
  const sidebarClose = document.getElementById('sidebarClose');
  const newChatBtn = document.getElementById('newChatBtn');
  const clearChatBtn = document.getElementById('clearChatBtn');
  const toast = document.getElementById('toast');
  const toastMessage = document.getElementById('toastMessage');

  // ======================================================================
  // State
  // ======================================================================
  const state = {
    isLoading: false,
    hasHistory: false,
    toastTimeout: null,
  };

  // ======================================================================
  // Utilities
  // ======================================================================
  function getTimestamp() {
    const now = new Date();
    return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  function scrollToBottom(smooth = true) {
    messagesContainer.scrollTo({
      top: messagesContainer.scrollHeight,
      behavior: smooth ? 'smooth' : 'instant',
    });
  }

  function showToast(msg) {
    toastMessage.textContent = msg;
    toast.classList.add('toast--visible');
    clearTimeout(state.toastTimeout);
    state.toastTimeout = setTimeout(() => {
      toast.classList.remove('toast--visible');
    }, 3000);
  }

  // ======================================================================
  // Typing Indicator
  // ======================================================================
  function showTyping() {
    typingIndicator.classList.add('typing-indicator--visible');
    scrollToBottom();
  }

  function hideTyping() {
    typingIndicator.classList.remove('typing-indicator--visible');
  }

  // ======================================================================
  // Message Rendering
  // ======================================================================
  function createMessageElement(role, content, timestamp) {
    const div = document.createElement('div');
    div.className = `message message--${role}`;

    // Avatar
    const avatar = document.createElement('div');
    avatar.className = 'message__avatar';
    if (role === 'bot') {
      avatar.innerHTML = `
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 2a10 10 0 0 1 10 10c0 2.5-1 4.8-2.6 6.5L21 21l-2.5-.6A10 10 0 1 1 12 2z"/>
        </svg>`;
    } else {
      avatar.textContent = 'U';
    }

    // Content wrapper
    const contentWrapper = document.createElement('div');
    contentWrapper.className = 'message__content';

    // Bubble
    const bubble = document.createElement('div');
    bubble.className = 'message__bubble';
    // Convert newlines to <br> and format bold markers
    const formatted = content
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\n/g, '<br>');
    bubble.innerHTML = formatted;

    // Time
    const time = document.createElement('span');
    time.className = 'message__time';
    time.textContent = timestamp || getTimestamp();

    contentWrapper.appendChild(bubble);
    contentWrapper.appendChild(time);
    div.appendChild(avatar);
    div.appendChild(contentWrapper);

    return div;
  }

  function addMessage(role, content, timestamp) {
    // Remove welcome suggestions if user sends first real message
    if (role === 'user') {
      const welcomeMsg = document.getElementById('welcomeMessage');
      if (welcomeMsg) {
        const suggestions = welcomeMsg.querySelector('.message__suggestions');
        if (suggestions) suggestions.remove();
      }
      state.hasHistory = true;
    }

    const el = createMessageElement(role, content, timestamp);
    messagesContainer.appendChild(el);
    scrollToBottom();

    // Animate in
    requestAnimationFrame(() => {
      el.style.animation = 'none';
      el.offsetHeight; // reflow
      el.style.animation = 'messageIn 0.4s cubic-bezier(0.16, 1, 0.3, 1)';
    });

    return el;
  }

  // ======================================================================
  // Suggestion Chips
  // ======================================================================
  messagesContainer.addEventListener('click', (e) => {
    const chip = e.target.closest('.suggestion-chip');
    if (!chip) return;
    const msg = chip.dataset.msg;
    if (msg) {
      chatInput.value = msg;
      autoResizeInput();
      handleSend();
    }
  });

  // ======================================================================
  // API Communication
  // ======================================================================
  async function sendMessage(message) {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(errData.response || errData.error || `HTTP ${response.status}`);
    }

    return response.json();
  }

  async function fetchHistory() {
    const response = await fetch('/api/history');
    if (!response.ok) return [];
    const data = await response.json();
    return data.history || [];
  }

  async function clearHistory() {
    const response = await fetch('/api/clear-history', { method: 'DELETE' });
    if (!response.ok) throw new Error('Failed to clear history');
    return response.json();
  }

  // ======================================================================
  // Core Actions
  // ======================================================================
  async function handleSend() {
    const message = chatInput.value.trim();
    if (!message || state.isLoading) return;

    // Clear input
    chatInput.value = '';
    autoResizeInput();

    // Show user message
    addMessage('user', message);

    // Loading state
    state.isLoading = true;
    sendBtn.disabled = true;
    sendBtn.classList.add('send-btn--loading');
    showTyping();

    try {
      const result = await sendMessage(message);
      hideTyping();
      addMessage('bot', result.response);
    } catch (err) {
      hideTyping();
      const errorMsg = err.message || 'Sorry, something went wrong. Please try again.';
      addMessage('bot', errorMsg);
      showToast('Connection error — please try again');
    } finally {
      state.isLoading = false;
      sendBtn.disabled = false;
      sendBtn.classList.remove('send-btn--loading');
      chatInput.focus();
    }
  }

  async function handleClearHistory() {
    if (!state.hasHistory && !messagesContainer.querySelectorAll('.message--user').length) {
      showToast('No messages to clear');
      return;
    }

    try {
      await clearHistory();
      // Remove all user & bot messages except welcome
      const msgs = messagesContainer.querySelectorAll('.message');
      msgs.forEach((m) => {
        if (m.id !== 'welcomeMessage') m.remove();
      });
      // Re-show welcome suggestions if hidden
      const welcomeMsg = document.getElementById('welcomeMessage');
      if (welcomeMsg) {
        const existing = welcomeMsg.querySelector('.message__suggestions');
        if (!existing) {
          const suggestions = document.createElement('div');
          suggestions.className = 'message__suggestions';
          suggestions.innerHTML = `
            <button class="suggestion-chip" data-msg="What are your timings?">🕘 Business Hours</button>
            <button class="suggestion-chip" data-msg="What services do you offer?">🚀 Our Services</button>
            <button class="suggestion-chip" data-msg="What are your prices?">💰 Pricing</button>
            <button class="suggestion-chip" data-msg="Is my data secure?">🔒 Security</button>
          `;
          welcomeMsg.querySelector('.message__bubble').appendChild(suggestions);
        }
      }
      state.hasHistory = false;
      showToast('Chat history cleared!');
    } catch (err) {
      showToast('Failed to clear history');
    }
  }

  async function handleNewChat() {
    await handleClearHistory();
    chatInput.focus();
  }

  function loadHistory() {
    fetchHistory().then((history) => {
      if (history.length === 0) return;

      // Remove welcome message
      const welcome = document.getElementById('welcomeMessage');
      if (welcome) welcome.remove();

      history.forEach((msg) => {
        addMessage(msg.role, msg.content, msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : undefined);
      });

      if (history.length > 0) {
        state.hasHistory = true;
      }
    }).catch(() => {
      // Silently fail — history is a nice-to-have
    });
  }

  // ======================================================================
  // Input Auto-Resize
  // ======================================================================
  function autoResizeInput() {
    chatInput.style.height = 'auto';
    chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
  }

  chatInput.addEventListener('input', autoResizeInput);

  // ======================================================================
  // Event Listeners
  // ======================================================================

  // Send on button click
  sendBtn.addEventListener('click', handleSend);

  // Send on Enter (Shift+Enter for newline)
  chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  });

  // Clear history
  clearChatBtn.addEventListener('click', handleClearHistory);

  // New chat
  newChatBtn.addEventListener('click', handleNewChat);

  // Sidebar toggle
  sidebarToggle.addEventListener('click', () => {
    sidebar.classList.add('sidebar--open');
    sidebarOverlay.classList.add('sidebar-overlay--visible');
  });

  sidebarClose.addEventListener('click', closeSidebar);
  sidebarOverlay.addEventListener('click', closeSidebar);

  function closeSidebar() {
    sidebar.classList.remove('sidebar--open');
    sidebarOverlay.classList.remove('sidebar-overlay--visible');
  }

  // ======================================================================
  // Initialisation
  // ======================================================================
  function init() {
    loadHistory();
    chatInput.focus();
    scrollToBottom(false);
  }

  init();
})();
