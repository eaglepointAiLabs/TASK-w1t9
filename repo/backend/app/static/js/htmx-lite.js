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

function setFormPending(form, isPending) {
  form.dataset.submitting = isPending ? "true" : "false";
  form.setAttribute("aria-busy", isPending ? "true" : "false");
  form.classList.toggle("is-submitting", isPending);
  form.querySelectorAll("button, input[type='submit']").forEach((control) => {
    if (isPending) {
      control.dataset.wasDisabled = control.disabled ? "true" : "false";
      control.disabled = true;
      return;
    }
    if (control.dataset.wasDisabled === "false") {
      control.disabled = false;
    }
    delete control.dataset.wasDisabled;
  });
}

async function handleResponse(
  response,
  targetSelector,
  swapMode,
  fallbackTarget = null,
) {
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

  const target =
    targetSelector === "closest article"
      ? fallbackTarget
      : document.querySelector(targetSelector);
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
    wireManagerEditor();
    if (toastMessage) {
      showNotice(toastMessage, toastTone);
    }
  }
}

function wireForms() {
  document
    .querySelectorAll("form[hx-post], form[hx-patch], form[hx-delete]")
    .forEach((form) => {
      if (form.dataset.hxBound === "true") {
        return;
      }
      form.dataset.hxBound = "true";
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (form.dataset.submitting === "true") {
          return;
        }
        setFormPending(form, true);
        const nonceInput = form.querySelector('input[name="nonce"]');
        try {
          applyCsrfToForms();
          if (form.matches("[data-manager-editor]")) {
            syncManagerStructuredFields(form);
          }
          const method = form.getAttribute("hx-post")
            ? "POST"
            : form.getAttribute("hx-patch")
              ? "PATCH"
              : "DELETE";
          const action =
            form.getAttribute("hx-post") ||
            form.getAttribute("hx-patch") ||
            form.getAttribute("hx-delete");
          const autoNoncePurpose = form.dataset.autoNoncePurpose;
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
            headers: {
              "HX-Request": "true",
              "X-CSRF-Token": readCookie("csrf_token") || "",
            },
          });

          await handleResponse(
            response,
            form.getAttribute("hx-target"),
            form.getAttribute("hx-swap") || "innerHTML",
            form.closest("article"),
          );
        } catch (error) {
          showNotice(error.message || "Request failed.", "error");
        } finally {
          if (nonceInput) {
            nonceInput.value = "";
          }
          setFormPending(form, false);
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
      const response = await fetch(
        `${form.getAttribute("hx-get")}?${params.toString()}`,
        {
          method: "GET",
          credentials: "same-origin",
          headers: { "HX-Request": "true" },
        },
      );
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
        wireManagerEditor();
      }
    });
  });
}

function wirePreview() {
  document
    .querySelectorAll(".image-upload-form input[type='file']")
    .forEach((input) => {
      if (input.dataset.previewBound === "true") {
        return;
      }
      input.dataset.previewBound = "true";
      input.addEventListener("change", () => {
        const [file] = input.files;
        const preview = input
          .closest(".image-upload-form")
          .querySelector(".local-preview");
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

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function safeParseJson(value, fallback) {
  try {
    return JSON.parse(value);
  } catch (_error) {
    return fallback;
  }
}

function defaultRule(displayType = "single_select") {
  const isSingleSelect = displayType !== "multi_select";
  return {
    rule_type: isSingleSelect
      ? "single_select_required"
      : "bounded_multi_select",
    is_required: isSingleSelect,
    min_select: isSingleSelect ? 1 : 0,
    max_select: 1,
  };
}

function defaultOptionValue() {
  return {
    label: "",
    value_code: "",
    price_delta: "0.00",
    is_available: true,
    sort_order: 0,
  };
}

function defaultOptionGroup(displayType = "single_select") {
  return {
    name: "",
    code: "",
    display_type: displayType,
    sort_order: 0,
    rules: [defaultRule(displayType)],
    values: [defaultOptionValue()],
  };
}

function managerWindowTemplate(windowData = {}) {
  const selectedDay = Number.parseInt(windowData.day_of_week ?? 0, 10);
  const dayOptions = [
    { value: 0, label: "Mon" },
    { value: 1, label: "Tue" },
    { value: 2, label: "Wed" },
    { value: 3, label: "Thu" },
    { value: 4, label: "Fri" },
    { value: 5, label: "Sat" },
    { value: 6, label: "Sun" },
  ]
    .map(
      (day) =>
        `<option value="${day.value}"${day.value === selectedDay ? " selected" : ""}>${day.label}</option>`,
    )
    .join("");

  return `
    <article class="structured-block manager-window">
      <div class="editor-toolbar">
        <strong>Window</strong>
        <button type="button" class="nav-link" data-remove-window>Remove</button>
      </div>
      <div class="grid compact-grid">
        <label>Day of week
          <select data-window-field="day_of_week">${dayOptions}</select>
        </label>
        <label>Start time
          <input type="time" data-window-field="start_time" value="${escapeHtml(windowData.start_time ?? "09:00")}">
        </label>
        <label>End time
          <input type="time" data-window-field="end_time" value="${escapeHtml(windowData.end_time ?? "17:00")}">
        </label>
        <label class="checkbox-row">
          <input type="checkbox" data-window-field="is_enabled"${windowData.is_enabled === false ? "" : " checked"}>
          Enabled
        </label>
      </div>
    </article>
  `;
}

function managerRuleTemplate(ruleData = {}) {
  return `
    <div class="structured-subblock manager-option-rule">
      <div class="grid compact-grid">
        <label>Rule type
          <input type="text" data-rule-field="rule_type" value="${escapeHtml(ruleData.rule_type ?? "single_select_required")}">
        </label>
        <label class="checkbox-row">
          <input type="checkbox" data-rule-field="is_required"${ruleData.is_required ? " checked" : ""}>
          Required
        </label>
        <label>Min select
          <input type="number" min="0" data-rule-field="min_select" value="${escapeHtml(ruleData.min_select ?? 0)}">
        </label>
        <label>Max select
          <input type="number" min="1" data-rule-field="max_select" value="${escapeHtml(ruleData.max_select ?? 1)}">
        </label>
      </div>
      <button type="button" class="nav-link" data-remove-rule>Remove rule</button>
    </div>
  `;
}

function managerValueTemplate(valueData = {}) {
  return `
    <div class="structured-subblock manager-option-value">
      <div class="grid compact-grid">
        <label>Label
          <input type="text" data-value-field="label" value="${escapeHtml(valueData.label ?? "")}">
        </label>
        <label>Code
          <input type="text" data-value-field="value_code" value="${escapeHtml(valueData.value_code ?? "")}">
        </label>
        <label>Price delta
          <input type="number" step="0.01" data-value-field="price_delta" value="${escapeHtml(valueData.price_delta ?? "0.00")}">
        </label>
        <label>Sort order
          <input type="number" data-value-field="sort_order" value="${escapeHtml(valueData.sort_order ?? 0)}">
        </label>
        <label class="checkbox-row">
          <input type="checkbox" data-value-field="is_available"${valueData.is_available === false ? "" : " checked"}>
          Available
        </label>
      </div>
      <button type="button" class="nav-link" data-remove-value>Remove value</button>
    </div>
  `;
}

function managerOptionGroupTemplate(optionData = {}) {
  const rules = optionData.rules?.length
    ? optionData.rules
    : [defaultRule(optionData.display_type)];
  const values = optionData.values?.length
    ? optionData.values
    : [defaultOptionValue()];

  return `
    <article class="structured-block manager-option-group">
      <div class="editor-toolbar">
        <strong>Option group</strong>
        <button type="button" data-remove-option-group>Remove group</button>
      </div>
      <div class="grid">
        <label>Name
          <input type="text" data-option-field="name" value="${escapeHtml(optionData.name ?? "")}">
        </label>
        <label>Code
          <input type="text" data-option-field="code" value="${escapeHtml(optionData.code ?? "")}">
        </label>
        <label>Display type
          <select data-option-field="display_type">
            <option value="single_select"${optionData.display_type !== "multi_select" ? " selected" : ""}>Single select</option>
            <option value="multi_select"${optionData.display_type === "multi_select" ? " selected" : ""}>Multi select</option>
          </select>
        </label>
        <label>Sort order
          <input type="number" data-option-field="sort_order" value="${escapeHtml(optionData.sort_order ?? 0)}">
        </label>
      </div>
      <section class="structured-subsection stack">
        <div class="editor-toolbar">
          <strong>Required rules</strong>
          <button type="button" data-add-rule>Add rule</button>
        </div>
        <div class="stack" data-rule-list>
          ${rules.map((rule) => managerRuleTemplate(rule)).join("")}
        </div>
      </section>
      <section class="structured-subsection stack">
        <div class="editor-toolbar">
          <strong>Values and price deltas</strong>
          <button type="button" data-add-value>Add value</button>
        </div>
        <div class="stack" data-value-list>
          ${values.map((value) => managerValueTemplate(value)).join("")}
        </div>
      </section>
    </article>
  `;
}

function renderManagerStructuredBlocks(form, payload = {}) {
  const windowList = form.querySelector("[data-window-list]");
  const optionList = form.querySelector("[data-option-group-list]");
  const windows = payload.availability_windows || [];
  const options = payload.options || [];

  windowList.innerHTML = windows.length
    ? windows.map((windowData) => managerWindowTemplate(windowData)).join("")
    : '<p class="muted">No windows configured. The dish stays available all day.</p>';
  optionList.innerHTML = options.length
    ? options
        .map((optionData) => managerOptionGroupTemplate(optionData))
        .join("")
    : '<p class="muted">No option groups configured yet.</p>';
}

function syncManagerStructuredFields(form) {
  const availabilityInput = form.querySelector(
    'input[name="availability_windows"]',
  );
  const optionsInput = form.querySelector('input[name="options"]');
  const windows = Array.from(form.querySelectorAll(".manager-window")).map(
    (windowBlock) => ({
      day_of_week: Number.parseInt(
        windowBlock.querySelector('[data-window-field="day_of_week"]').value ||
          "0",
        10,
      ),
      start_time: windowBlock.querySelector('[data-window-field="start_time"]')
        .value,
      end_time: windowBlock.querySelector('[data-window-field="end_time"]')
        .value,
      is_enabled: windowBlock.querySelector('[data-window-field="is_enabled"]')
        .checked,
    }),
  );
  const options = Array.from(
    form.querySelectorAll(".manager-option-group"),
  ).map((groupBlock) => ({
    name: groupBlock.querySelector('[data-option-field="name"]').value,
    code: groupBlock.querySelector('[data-option-field="code"]').value,
    display_type: groupBlock.querySelector('[data-option-field="display_type"]')
      .value,
    sort_order: Number.parseInt(
      groupBlock.querySelector('[data-option-field="sort_order"]').value || "0",
      10,
    ),
    rules: Array.from(groupBlock.querySelectorAll(".manager-option-rule")).map(
      (ruleBlock) => ({
        rule_type: ruleBlock.querySelector('[data-rule-field="rule_type"]')
          .value,
        is_required: ruleBlock.querySelector('[data-rule-field="is_required"]')
          .checked,
        min_select: Number.parseInt(
          ruleBlock.querySelector('[data-rule-field="min_select"]').value ||
            "0",
          10,
        ),
        max_select: Number.parseInt(
          ruleBlock.querySelector('[data-rule-field="max_select"]').value ||
            "1",
          10,
        ),
      }),
    ),
    values: Array.from(
      groupBlock.querySelectorAll(".manager-option-value"),
    ).map((valueBlock) => ({
      label: valueBlock.querySelector('[data-value-field="label"]').value,
      value_code: valueBlock.querySelector('[data-value-field="value_code"]')
        .value,
      price_delta:
        valueBlock.querySelector('[data-value-field="price_delta"]').value ||
        "0.00",
      is_available: valueBlock.querySelector(
        '[data-value-field="is_available"]',
      ).checked,
      sort_order: Number.parseInt(
        valueBlock.querySelector('[data-value-field="sort_order"]').value ||
          "0",
        10,
      ),
    })),
  }));

  availabilityInput.value = JSON.stringify(windows);
  optionsInput.value = JSON.stringify(options);
}

function resetManagerEditor(form) {
  const createUrl = form.dataset.createUrl;
  form.reset();
  form.dataset.editingDishId = "";
  form.setAttribute("action", createUrl);
  form.setAttribute("hx-post", createUrl);
  form.removeAttribute("hx-patch");
  form.querySelector("[data-editor-mode]").textContent = "Creating a new dish";
  form.querySelector("[data-editor-title]").textContent =
    "Structured dish editor";
  form.querySelector("[data-editor-submit]").textContent = "Create dish";
  renderManagerStructuredBlocks(form, {
    availability_windows: [],
    options: [],
  });
  syncManagerStructuredFields(form);
}

function loadDishIntoManagerEditor(form, payload) {
  const updateUrl = form.dataset.updateUrlTemplate.replace(
    "__dish_id__",
    payload.id,
  );
  form.dataset.editingDishId = payload.id;
  form.querySelector('[name="name"]').value = payload.name || "";
  form.querySelector('[name="description"]').value = payload.description || "";
  form.querySelector('[name="category_name"]').value = payload.category || "";
  form.querySelector('[name="base_price"]').value = payload.base_price || "";
  form.querySelector('[name="tags"]').value = (payload.tags || []).join(", ");
  form.querySelector('[name="stock_quantity"]').value = String(
    payload.stock_quantity ?? 0,
  );
  form.querySelector('[name="sort_order"]').value = String(
    payload.sort_order ?? 0,
  );
  form.querySelector('[name="is_published"]').checked = Boolean(
    payload.is_published,
  );
  form.querySelector('[name="is_sold_out"]').checked = Boolean(
    payload.is_sold_out,
  );
  form.querySelector('[name="archived"]').checked = Boolean(
    payload.archived_at,
  );
  form.setAttribute("action", updateUrl);
  form.removeAttribute("hx-post");
  form.setAttribute("hx-patch", updateUrl);
  form.querySelector("[data-editor-mode]").textContent =
    `Editing ${payload.name}`;
  form.querySelector("[data-editor-title]").textContent =
    "Update live dish configuration";
  form.querySelector("[data-editor-submit]").textContent = "Save changes";
  renderManagerStructuredBlocks(form, payload);
  syncManagerStructuredFields(form);
}

function wireManagerEditor() {
  document.querySelectorAll("[data-manager-editor]").forEach((form) => {
    if (form.dataset.managerEditorBound !== "true") {
      form.dataset.managerEditorBound = "true";
      resetManagerEditor(form);
      form.addEventListener("click", (event) => {
        if (event.target.matches("[data-editor-reset]")) {
          event.preventDefault();
          resetManagerEditor(form);
          return;
        }
        if (event.target.matches("[data-add-window]")) {
          event.preventDefault();
          const windowList = form.querySelector("[data-window-list]");
          if (windowList.querySelector(".muted")) {
            windowList.innerHTML = "";
          }
          windowList.insertAdjacentHTML("beforeend", managerWindowTemplate());
          syncManagerStructuredFields(form);
          return;
        }
        if (event.target.matches("[data-remove-window]")) {
          event.preventDefault();
          event.target.closest(".manager-window")?.remove();
          syncManagerStructuredFields(form);
          if (!form.querySelector(".manager-window")) {
            renderManagerStructuredBlocks(form, {
              availability_windows: [],
              options: safeParseJson(
                form.querySelector('input[name="options"]').value,
                [],
              ),
            });
          }
          return;
        }
        if (event.target.matches("[data-add-option-group]")) {
          event.preventDefault();
          const optionList = form.querySelector("[data-option-group-list]");
          if (optionList.querySelector(".muted")) {
            optionList.innerHTML = "";
          }
          optionList.insertAdjacentHTML(
            "beforeend",
            managerOptionGroupTemplate(defaultOptionGroup()),
          );
          syncManagerStructuredFields(form);
          return;
        }
        if (event.target.matches("[data-remove-option-group]")) {
          event.preventDefault();
          event.target.closest(".manager-option-group")?.remove();
          syncManagerStructuredFields(form);
          if (!form.querySelector(".manager-option-group")) {
            renderManagerStructuredBlocks(form, {
              availability_windows: safeParseJson(
                form.querySelector('input[name="availability_windows"]').value,
                [],
              ),
              options: [],
            });
          }
          return;
        }
        if (event.target.matches("[data-add-rule]")) {
          event.preventDefault();
          const group = event.target.closest(".manager-option-group");
          const displayType = group.querySelector(
            '[data-option-field="display_type"]',
          ).value;
          group
            .querySelector("[data-rule-list]")
            .insertAdjacentHTML(
              "beforeend",
              managerRuleTemplate(defaultRule(displayType)),
            );
          syncManagerStructuredFields(form);
          return;
        }
        if (event.target.matches("[data-remove-rule]")) {
          event.preventDefault();
          event.target.closest(".manager-option-rule")?.remove();
          syncManagerStructuredFields(form);
          return;
        }
        if (event.target.matches("[data-add-value]")) {
          event.preventDefault();
          event.target
            .closest(".manager-option-group")
            .querySelector("[data-value-list]")
            .insertAdjacentHTML(
              "beforeend",
              managerValueTemplate(defaultOptionValue()),
            );
          syncManagerStructuredFields(form);
          return;
        }
        if (event.target.matches("[data-remove-value]")) {
          event.preventDefault();
          event.target.closest(".manager-option-value")?.remove();
          syncManagerStructuredFields(form);
        }
      });
      form.addEventListener("input", () => syncManagerStructuredFields(form));
      form.addEventListener("change", () => syncManagerStructuredFields(form));
    }
  });

  document.querySelectorAll("[data-load-dish-editor]").forEach((button) => {
    if (button.dataset.editorBound === "true") {
      return;
    }
    button.dataset.editorBound = "true";
    button.addEventListener("click", () => {
      const form = document.querySelector("[data-manager-editor]");
      const payload = safeParseJson(button.dataset.loadDishEditor, null);
      if (!form || !payload) {
        return;
      }
      loadDishIntoManagerEditor(form, payload);
      form.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  applyCsrfToForms();
  wireForms();
  wirePreview();
  wireManagerEditor();
  flushQueuedNotice();
});
