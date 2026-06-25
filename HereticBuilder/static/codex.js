(() => {
  const launchers = Array.from(document.querySelectorAll(".launcher"));
  const titleBar = document.querySelector(".title-bar");
  const page = document.querySelector(".codex-page");
  const ruleReturnStorageKey = "hereticCoreRuleReturnStack";

  function currentHref() {
    return `${window.location.pathname}${window.location.search}${window.location.hash}`;
  }

  function sameOriginHref(value) {
    if (!value) {
      return "";
    }
    try {
      const url = new URL(value, window.location.href);
      if (url.origin !== window.location.origin) {
        return "";
      }
      return `${url.pathname}${url.search}${url.hash}`;
    } catch (_error) {
      return "";
    }
  }

  function ruleReturnStack() {
    try {
      const value = JSON.parse(window.sessionStorage.getItem(ruleReturnStorageKey) || "[]");
      if (!Array.isArray(value)) {
        return [];
      }
      return value.map(sameOriginHref).filter(Boolean);
    } catch (_error) {
      return [];
    }
  }

  function setRuleReturnStack(stack) {
    const normalized = stack.map(sameOriginHref).filter(Boolean);
    if (normalized.length) {
      window.sessionStorage.setItem(ruleReturnStorageKey, JSON.stringify(normalized));
      return;
    }
    window.sessionStorage.removeItem(ruleReturnStorageKey);
  }

  function rememberRuleReturnHref(event) {
    const href = currentHref();
    const target = sameOriginHref(event?.currentTarget?.getAttribute("href"));
    const stack = ruleReturnStack();
    if (!target || target === href) {
      return;
    }
    if (stack[stack.length - 1] !== href) {
      stack.push(href);
    }
    setRuleReturnStack(stack);
  }

  function ruleReturnHref() {
    if (!page?.classList.contains("core-rule-page")) {
      return "";
    }
    const current = currentHref();
    const stack = ruleReturnStack();
    while (stack.length) {
      const href = stack.pop();
      if (href && href !== current) {
        setRuleReturnStack(stack);
        return href;
      }
    }
    setRuleReturnStack(stack);
    return "";
  }

  function goUp() {
    if (titleBar?.dataset.upHref) {
      window.location.href = titleBar.dataset.upHref;
    }
  }

  function closeWindow() {
    const returnHref = ruleReturnHref();
    if (returnHref) {
      window.location.href = returnHref;
      return;
    }
    goUp();
  }

  function selectLauncher(button) {
    launchers.forEach((item) => item.setAttribute("aria-pressed", "false"));
    button.setAttribute("aria-pressed", "true");
    if (button.dataset.href) {
      window.location.href = button.dataset.href;
      return;
    }
    history.replaceState(null, "", `#${button.dataset.route}`);
  }

  launchers.forEach((button) => {
    button.addEventListener("click", () => selectLauncher(button));
  });

  document.querySelectorAll("a[href]").forEach((link) => {
    const href = sameOriginHref(link.getAttribute("href"));
    if (!href.startsWith("/codex/core-rules/rule/")) {
      return;
    }
    link.addEventListener("click", rememberRuleReturnHref);
  });

  titleBar?.addEventListener("click", closeWindow);
  titleBar?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      closeWindow();
    }
  });

  const activeRoute = window.location.hash.replace("#", "");
  const activeButton = launchers.find((button) => button.dataset.route === activeRoute);
  if (activeButton) {
    activeButton.setAttribute("aria-pressed", "true");
  }

  window.setupWinScrollbars();
  window.addEventListener("load", window.setupWinScrollbars);
})();
