/**
 * chat.js — vanilla JS chat client.
 *
 * Manages:
 *  - in-memory conversation history
 *  - sending POST /api/chat
 *  - rendering user, assistant, typing, and error bubbles
 *  - composer behavior (auto-resize, Enter to send, Shift+Enter for newline)
 */

(function () {
  "use strict";

  const API_URL = "/api/chat";

  // In-memory history — array of {role, content} pairs (matches Anthropic's format).
  // Reset on page refresh; never persisted.
  let history = [];

  // DOM references
  const messagesEl = document.getElementById("messages");
  const formEl = document.getElementById("composer");
  const inputEl = document.getElementById("input");
  const sendBtn = document.getElementById("send");

  // ------------------------------------------------------------- composer

  /** Auto-resize the textarea up to its max-height. */
  function autoResize() {
    inputEl.style.height = "auto";
    inputEl.style.height = inputEl.scrollHeight + "px";
  }

  inputEl.addEventListener("input", autoResize);

  /** Enter sends. Shift+Enter inserts a newline. */
  inputEl.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      formEl.requestSubmit();
    }
  });

  formEl.addEventListener("submit", function (e) {
    e.preventDefault();
    const question = inputEl.value.trim();
    if (!question) return;
    sendQuestion(question);
  });

  // ------------------------------------------------------------- rendering

  /** Append a message bubble; returns the element so callers can update/remove it. */
  function renderBubble(role, content, opts) {
    opts = opts || {};
    const wrapper = document.createElement("div");
    wrapper.className = "msg msg-" + role;
    if (opts.extraClass) wrapper.classList.add(opts.extraClass);

    const bubble = document.createElement("div");
    bubble.className = "msg-bubble";

    if (opts.html) {
      bubble.innerHTML = content;
    } else {
      bubble.textContent = content;
    }

    wrapper.appendChild(bubble);
    messagesEl.appendChild(wrapper);
    scrollToBottom();
    return wrapper;
  }

  function renderTyping() {
    return renderBubble(
      "assistant",
      '<span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>',
      { html: true, extraClass: "msg-typing" }
    );
  }

  function renderError(text) {
    return renderBubble("assistant", text, { extraClass: "msg-error" });
  }

  function scrollToBottom() {
    requestAnimationFrame(function () {
      window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
    });
  }

  // ------------------------------------------------------------- send

  async function sendQuestion(question) {
    // Render the user's message immediately
    renderBubble("user", question);

    // Clear input + disable composer while waiting
    inputEl.value = "";
    autoResize();
    setComposerDisabled(true);

    // Show "typing" indicator
    const typingEl = renderTyping();

    try {
      const res = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: question, history: history }),
      });

      // Remove typing indicator regardless of success / failure
      typingEl.remove();

      if (!res.ok) {
        let errMsg = "Request failed (" + res.status + ").";
        try {
          const errJson = await res.json();
          if (errJson && errJson.error) errMsg = errJson.error;
        } catch (_) {
          /* response wasn't JSON */
        }
        renderError(errMsg);
        return;
      }

      const data = await res.json();
      if (!data || typeof data.answer !== "string") {
        renderError("Got an unexpected response from the server.");
        return;
      }

      // Render the assistant's answer + update history
      renderBubble("assistant", data.answer);
      if (Array.isArray(data.history)) {
        history = data.history;
      }
    } catch (err) {
      typingEl.remove();
      renderError("Network error: " + (err && err.message ? err.message : err));
    } finally {
      setComposerDisabled(false);
      inputEl.focus();
    }
  }

  function setComposerDisabled(disabled) {
    inputEl.disabled = disabled;
    sendBtn.disabled = disabled;
    sendBtn.textContent = disabled ? "Sending..." : "Send";
  }

  // Focus the input on load
  inputEl.focus();
})();
