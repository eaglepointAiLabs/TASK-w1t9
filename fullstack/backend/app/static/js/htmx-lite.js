function readCookie(name) {
  const prefix = `${name}=`;
  return document.cookie
    .split(";")
    .map((value) => value.trim())
    .find((value) => value.startsWith(prefix))
    ?.slice(prefix.length);
}

function noticesRoot() {
  return document.querySelector("[data-ui-notices]");
}

function queueNotice(message, tone = "info") {
  sessionStorage.setItem("tablepay.notice", JSON.stringify({ message, tone }));
}

function flushQueuedNotice() {
  const raw = sessionStorage.getItem("tablepay.notice");
  if (!raw) {
    return;
  }
  sessionStorage.removeItem("tablepay.notice");
  try {
    const notice = JSON.parse(raw);
    showNotice(notice.message, notice.tone);
  } catch (_error) {
    showNotice(raw, "info");
  }
}

function showNotice(message, tone = "info") {
  const root = noticesRoot();
  if (!root) {
    window.alert(message);
    return;
  }
  const id = `notice-${Date.now()}`;
  const notice = document.createElement("div");
  notice.id = id;
  notice.className = "notice";
  notice.dataset.tone = tone;
  notice.textContent = message;
  root.prepend(notice);
  window.setTimeout(() => {
    document.getElementById(id)?.remove();
  }, 4500);
}

async function issueNonce(purpose) {
  const response = await fetch("/api/auth/nonces", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      "HX-Request": "true",
      "X-CSRF-Token": readCookie("csrf_token") || "",
    },
    body: JSON.stringify({ purpose }),
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.message || "Unable to issue nonce.");
  }
  return payload.data.nonce;
}

function applyCsrfToForms() {
  const token = readCookie("csrf_token") || "";
  document.querySelectorAll('input[name="csrf_token"]').forEach((input) => {
    input.value = token;
  });
}

async function handleResponse(response, targetSelector, swapMode, fallbackTarget = null) {
  const csrfHeader = response.headers.get("X-CSRF-Token");
  const toastMessage = response.headers.get("X-Toast-Message");
  const toastTone = response.headers.get("X-Toast-Tone") || "success";
  const redirectLocation = response.headers.get("X-Redirect-Location");
  if (csrfHeader) {
    document.cookie = `csrf_token=${csrfHeader}; path=/; samesite=lax`;
    applyCsrfToForms();
  }

  if (!targetSelector) {
    if (response.ok && toastMessage) {
      queueNotice(toastMessage, toastTone);
    }
    if (response.ok && redirectLocation) {
      window.location.href = redirectLocation;
      return;
    }
    if (response.ok && response.redirected) {
      window.location.href = response.url;
      return;
    }
    if (response.ok) {
      window.location.reload();
      return;
    }
  }

  const target = targetSelector === "closest article" ? fallbackTarget : document.querySelector(targetSelector);
  const payload = await response.text();

  if (!response.ok) {
    let message = toastMessage || "Request failed.";
    if (!toastMessage) {
      try {
        message = JSON.parse(payload).message || message;
      } catch (_error) {}
    }
    if (redirectLocation) {
      queueNotice(message, "error");
      window.location.href = redirectLocation;
      return;
    }
    showNotice(message, "error");
    return;
  }

  if (target) {
    if (swapMode === "outerHTML") {
      target.outerHTML = payload;
    } else if (swapMode === "afterbegin") {
      target.insertAdjacentHTML("afterbegin", payload);
    } else {
      target.innerHTML = payload;
    }
    applyCsrfToForms();
    wireForms();
    wirePreview();
    if (toastMessage) {
      showNotice(toastMessage, toastTone);
    }
  }
}

function wireForms() {
  document.querySelectorAll("form[hx-post], form[hx-patch], form[hx-delete]").forEach((form) => {
    if (form.dataset.hxBound === "true") {
      return;
    }
    form.dataset.hxBound = "true";
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      applyCsrfToForms();
      const method = form.getAttribute("hx-post")
        ? "POST"
        : form.getAttribute("hx-patch")
          ? "PATCH"
          : "DELETE";
      const action = form.getAttribute("hx-post") || form.getAttribute("hx-patch") || form.getAttribute("hx-delete");
      const autoNoncePurpose = form.dataset.autoNoncePurpose;
      const nonceInput = form.querySelector('input[name="nonce"]');
      if (autoNoncePurpose && nonceInput && !nonceInput.value) {
        try {
          nonceInput.value = await issueNonce(autoNoncePurpose);
        } catch (error) {
          showNotice(error.message || "Unable to issue nonce.", "error");
          return;
        }
      }

      const response = await fetch(action, {
        method,
        body: new FormData(form),
        credentials: "same-origin",
        headers: { "HX-Request": "true", "X-CSRF-Token": readCookie("csrf_token") || "" },
      });

      await handleResponse(
        response,
        form.getAttribute("hx-target"),
        form.getAttribute("hx-swap") || "innerHTML",
        form.closest("article"),
      );
      if (nonceInput) {
        nonceInput.value = "";
      }
    });
  });

  document.querySelectorAll("form[hx-get]").forEach((form) => {
    if (form.dataset.hxBound === "true") {
      return;
    }
    form.dataset.hxBound = "true";
    const triggerFetch = async () => {
      const params = new URLSearchParams(new FormData(form));
      const response = await fetch(`${form.getAttribute("hx-get")}?${params.toString()}`, {
        method: "GET",
        credentials: "same-origin",
        headers: { "HX-Request": "true" },
      });
      await handleResponse(
        response,
        form.getAttribute("hx-target"),
        form.getAttribute("hx-swap") || "innerHTML",
      );
    };
    form.addEventListener("change", triggerFetch);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      await triggerFetch();
    });
  });

  document.querySelectorAll("[hx-get] button").forEach((button) => {
    if (button.dataset.hxBound === "true") {
      return;
    }
    button.dataset.hxBound = "true";
    button.addEventListener("click", async (event) => {
      const container = button.closest("[hx-get]");
      const response = await fetch(container.getAttribute("hx-get"), {
        method: "GET",
        credentials: "same-origin",
        headers: { "HX-Request": "true" },
      });
      const payload = await response.text();
      if (response.ok) {
        button.closest("article").outerHTML = payload;
        applyCsrfToForms();
        wireForms();
        wirePreview();
      }
    });
  });
}

function wirePreview() {
  document.querySelectorAll(".image-upload-form input[type='file']").forEach((input) => {
    if (input.dataset.previewBound === "true") {
      return;
    }
    input.dataset.previewBound = "true";
    input.addEventListener("change", () => {
      const [file] = input.files;
      const preview = input.closest(".image-upload-form").querySelector(".local-preview");
      preview.innerHTML = "";
      if (!file) {
        return;
      }
      const reader = new FileReader();
      reader.onload = () => {
        const image = document.createElement("img");
        image.src = reader.result;
        image.alt = "Preview";
        image.className = "dish-image";
        const caption = document.createElement("p");
        caption.textContent = file.name;
        preview.append(image, caption);
      };
      reader.readAsDataURL(file);
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  applyCsrfToForms();
  wireForms();
  wirePreview();
  flushQueuedNotice();
});
