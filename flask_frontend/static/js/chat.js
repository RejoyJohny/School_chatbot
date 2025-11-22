document.addEventListener("DOMContentLoaded", function () {
  const sendBtn = document.getElementById("sendBtn");
  const input = document.getElementById("messageInput");
  const chatbox = document.getElementById("chatbox");

  function appendMessage(text, who) {
    const div = document.createElement("div");
    div.className = "msg " + (who === "me" ? "me" : "bot");
    div.innerText = text;
    chatbox.appendChild(div);
    chatbox.scrollTop = chatbox.scrollHeight;
  }

  async function sendMessage() {
    const txt = input.value.trim();
    if (!txt) return;
    appendMessage(txt, "me");
    input.value = "";
    // show loader
    const loader = document.createElement("div");
    loader.className = "msg bot";
    loader.innerHTML = '<span class="loader"></span> Bot is typing...';
    chatbox.appendChild(loader);
    chatbox.scrollTop = chatbox.scrollHeight;

    try {
      const res = await fetch("/chat/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: txt })
      });
      const data = await res.json();
      // remove loader
      loader.remove();
      if (res.status !== 200) {
        appendMessage(data.detail || data.error || "Server error", "bot");
      } else {
        // backend returns { sql, summary, results }
        let reply = data.summary || (data.results ? JSON.stringify(data.results.slice(0, 5), null, 2) : "No results");
        appendMessage(reply, "bot");
      }
    } catch (e) {
      loader.remove();
      appendMessage("Could not reach backend: " + e.message, "bot");
    }
  }

  sendBtn.addEventListener("click", sendMessage);
  input.addEventListener("keypress", function (e) { if (e.key === "Enter") sendMessage(); });
});
