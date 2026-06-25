(() => {
  const root = document.querySelector(".taskbar-search");
  if (!root) {
    return;
  }

  const input = root.querySelector(".taskbar-search-input");
  const results = root.querySelector(".taskbar-search-results");
  const resultList = document.createElement("div");
  const clearButton = document.createElement("button");
  let controller = null;
  let searchTimer = 0;
  let dragStart = null;

  resultList.className = "taskbar-search-results-list";
  resultList.setAttribute("role", "list");
  results.removeAttribute("role");
  results.replaceChildren(resultList);

  const scrollbar = document.createElement("div");
  scrollbar.className = "win-scrollbar taskbar-search-scrollbar";
  scrollbar.hidden = true;
  scrollbar.innerHTML = `
    <button class="scroll-button scroll-button-up" type="button" aria-label="Scroll up"></button>
    <div class="scroll-track"><div class="scroll-thumb"></div></div>
    <button class="scroll-button scroll-button-down" type="button" aria-label="Scroll down"></button>
  `;
  results.append(scrollbar);

  const upButton = scrollbar.querySelector(".scroll-button-up");
  const downButton = scrollbar.querySelector(".scroll-button-down");
  const track = scrollbar.querySelector(".scroll-track");
  const thumb = scrollbar.querySelector(".scroll-thumb");

  clearButton.className = "taskbar-search-clear";
  clearButton.type = "button";
  clearButton.setAttribute("aria-label", "Clear search");
  clearButton.textContent = "x";
  input.after(clearButton);

  function setOpen(open) {
    root.classList.toggle("is-open", open);
    input.setAttribute("aria-expanded", String(open));
    results.hidden = !open;
    if (open) {
      requestAnimationFrame(refreshScrollbar);
    }
  }

  function syncClearButton() {
    root.classList.toggle("has-value", Boolean(input.value.trim()));
  }

  function clearResults() {
    resultList.replaceChildren();
    setOpen(false);
  }

  function resultText(value) {
    return String(value || "").trim();
  }

  function renderMessage(message) {
    const item = document.createElement("div");
    item.className = "taskbar-search-message";
    item.textContent = message;
    resultList.replaceChildren(item);
    setOpen(true);
  }

  function renderResults(items) {
    resultList.replaceChildren();
    if (!items.length) {
      renderMessage("No results");
      return;
    }

    const fragment = document.createDocumentFragment();
    items.forEach((item) => {
      const link = document.createElement("a");
      link.className = "taskbar-search-result";
      link.href = item.href;
      link.setAttribute("role", "listitem");

      const title = document.createElement("span");
      title.className = "taskbar-search-result-title";
      title.textContent = resultText(item.title);
      link.append(title);

      const meta = document.createElement("span");
      meta.className = "taskbar-search-result-meta";
      const type = resultText(item.type);
      const context = resultText(item.meta);
      meta.textContent = [type, context].filter(Boolean).join(" / ");
      link.append(meta);

      fragment.append(link);
    });
    resultList.append(fragment);
    setOpen(true);
  }

  function scrollStep() {
    return Math.max(64, Math.floor(resultList.clientHeight * 0.35));
  }

  function updateThumb() {
    const maxScroll = Math.max(0, resultList.scrollHeight - resultList.clientHeight);
    const trackHeight = track.clientHeight;
    const thumbHeight = Math.max(24, Math.floor(resultList.clientHeight / resultList.scrollHeight * trackHeight));
    const travel = Math.max(0, trackHeight - thumbHeight);
    const thumbTop = maxScroll ? Math.round(resultList.scrollTop / maxScroll * travel) : 0;
    thumb.style.height = `${thumbHeight}px`;
    thumb.style.transform = `translateY(${thumbTop}px)`;
  }

  function refreshScrollbar() {
    if (results.hidden) {
      return;
    }
    const isScrollable = resultList.scrollHeight - resultList.clientHeight > 1;
    results.classList.toggle("has-search-scrollbar", isScrollable);
    scrollbar.hidden = !isScrollable;
    if (isScrollable) {
      updateThumb();
    }
  }

  async function runSearch(query) {
    if (controller) {
      controller.abort();
    }
    controller = new AbortController();

    try {
      const response = await fetch(`/api/search?q=${encodeURIComponent(query)}&limit=30`, {
        signal: controller.signal,
      });
      if (!response.ok) {
        throw new Error(`Search failed: ${response.status}`);
      }
      const payload = await response.json();
      if (input.value.trim() !== query) {
        return;
      }
      renderResults(payload.results || []);
    } catch (error) {
      if (error.name === "AbortError") {
        return;
      }
      renderMessage("Search unavailable");
    }
  }

  function scheduleSearch() {
    window.clearTimeout(searchTimer);
    const query = input.value.trim();
    syncClearButton();
    if (query.length < 2) {
      clearResults();
      return;
    }
    searchTimer = window.setTimeout(() => runSearch(query), 160);
  }

  root.addEventListener("submit", (event) => {
    event.preventDefault();
  });

  clearButton.addEventListener("click", () => {
    input.value = "";
    syncClearButton();
    clearResults();
    input.focus();
  });

  upButton.addEventListener("click", () => resultList.scrollBy({ top: -scrollStep(), behavior: "auto" }));
  downButton.addEventListener("click", () => resultList.scrollBy({ top: scrollStep(), behavior: "auto" }));
  track.addEventListener("click", (event) => {
    if (event.target !== track) {
      return;
    }
    const thumbRect = thumb.getBoundingClientRect();
    resultList.scrollBy({ top: event.clientY < thumbRect.top ? -resultList.clientHeight : resultList.clientHeight, behavior: "auto" });
  });
  thumb.addEventListener("pointerdown", (event) => {
    dragStart = { y: event.clientY, scrollTop: resultList.scrollTop };
    thumb.setPointerCapture(event.pointerId);
    event.preventDefault();
  });
  thumb.addEventListener("pointermove", (event) => {
    if (!dragStart) {
      return;
    }
    const maxScroll = resultList.scrollHeight - resultList.clientHeight;
    const travel = Math.max(1, track.clientHeight - thumb.offsetHeight);
    resultList.scrollTop = dragStart.scrollTop + (event.clientY - dragStart.y) * maxScroll / travel;
  });
  thumb.addEventListener("pointerup", () => {
    dragStart = null;
  });
  thumb.addEventListener("pointercancel", () => {
    dragStart = null;
  });
  resultList.addEventListener("scroll", updateThumb, { passive: true });
  window.addEventListener("resize", refreshScrollbar);
  if ("ResizeObserver" in window) {
    const observer = new ResizeObserver(refreshScrollbar);
    observer.observe(results);
    observer.observe(resultList);
  }

  input.addEventListener("input", scheduleSearch);
  input.addEventListener("focus", scheduleSearch);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
    }
    if (event.key === "Escape") {
      clearResults();
      input.blur();
    }
  });

  document.addEventListener("pointerdown", (event) => {
    if (!root.contains(event.target)) {
      clearResults();
    }
  });

  syncClearButton();
})();
