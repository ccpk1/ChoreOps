class ChoreOpsQuickChoreEditorPocCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = null;
    this._hass = null;
    this._mode = "create";
    this._selectedUserId = "";
    this._selectedChoreId = "";
    this._draft = {
      name: "",
      points: "",
      assignedUserNames: [],
      completionCriteria: "independent",
      description: "",
      icon: "",
      dueDate: "",
      frequency: "none",
    };
    this._busy = false;
    this._message = "";
    this._messageType = "info";
  }

  static getStubConfig() {
    return {
      type: "custom:choreops-quick-chore-editor-poc",
      title: "Quick chore editor",
    };
  }

  setConfig(config) {
    const acceptedTypes = new Set([
      "custom:choreops-create-chore-poc",
      "custom:choreops-quick-chore-editor-poc",
    ]);
    if (!config || !acceptedTypes.has(config.type)) {
      throw new Error("Invalid card configuration");
    }

    this._config = {
      title: "Quick chore editor",
      ...config,
    };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return this._mode === "edit" ? 7 : 6;
  }

  _escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  _setMessage(message, type = "info") {
    this._message = message;
    this._messageType = type;
  }

  _resetDraft() {
    this._draft = {
      name: "",
      points: "",
      assignedUserNames: [],
      completionCriteria: "independent",
      description: "",
      icon: "",
      dueDate: "",
      frequency: "none",
    };
  }

  _toDateTimeLocalValue(value) {
    if (typeof value !== "string" || !value.trim()) {
      return "";
    }

    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
      return value.includes("T") ? value.slice(0, 16) : "";
    }

    const pad = (part) => String(part).padStart(2, "0");
    return `${parsed.getFullYear()}-${pad(parsed.getMonth() + 1)}-${pad(parsed.getDate())}T${pad(parsed.getHours())}:${pad(parsed.getMinutes())}`;
  }

  _fromDateTimeLocalValue(value) {
    if (typeof value !== "string" || !value.trim()) {
      return "";
    }

    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? "" : parsed.toISOString();
  }

  _getCompletionCriteriaOptions() {
    return [
      "independent",
      "shared_first",
      "shared_all",
      "rotation_simple",
      "rotation_smart",
    ];
  }

  _getSupportedFrequencyOptions() {
    return [
      "none",
      "daily",
      "daily_multi",
      "weekly",
      "biweekly",
      "monthly",
      "quarterly",
      "yearly",
      "week_end",
      "month_end",
      "quarter_end",
      "year_end",
    ];
  }

  _resolveSystemHelper() {
    if (!this._hass) {
      return { state: null, error: "" };
    }

    if (this._config?.system_dashboard_helper) {
      return {
        state: this._hass.states[this._config.system_dashboard_helper] ?? null,
        error: "",
      };
    }

    const wantedEntryId = this._config?.config_entry_id;
    const candidates = Object.values(this._hass.states).filter((stateObj) => {
      if (!stateObj?.entity_id?.startsWith("sensor.")) {
        return false;
      }
      if (stateObj.attributes?.purpose !== "purpose_system_dashboard_helper") {
        return false;
      }
      if (
        wantedEntryId &&
        stateObj.attributes?.integration_entry_id !== wantedEntryId
      ) {
        return false;
      }
      return true;
    });

    if (candidates.length > 1 && !wantedEntryId) {
      return {
        state: null,
        error:
          "Multiple ChoreOps system helpers found. Set config_entry_id or system_dashboard_helper.",
      };
    }

    return { state: candidates[0] ?? null, error: "" };
  }

  _getResolvedConfigEntryId(systemHelperState) {
    return (
      this._config?.config_entry_id ||
      systemHelperState?.attributes?.integration_entry_id ||
      ""
    );
  }

  _getTranslations(systemHelperState) {
    if (!this._hass || !systemHelperState) {
      return {};
    }

    const translationSensorId =
      systemHelperState.attributes?.translation_sensor_eid || "";
    const translationState = this._hass.states[translationSensorId];
    return translationState?.attributes?.ui_translations || {};
  }

  _t(translations, key, fallback) {
    const value = translations?.[key];
    return typeof value === "string" && value.trim() ? value : fallback;
  }

  _getUserOptions(systemHelperState) {
    if (!this._hass || !systemHelperState) {
      return [];
    }

    const helperMap = systemHelperState.attributes?.user_dashboard_helpers;
    if (!helperMap || typeof helperMap !== "object") {
      return [];
    }

    return Object.entries(helperMap)
      .map(([userId, helperEntityId]) => {
        const helperState = this._hass.states[helperEntityId];
        const userName = helperState?.attributes?.user_name;
        return userName
          ? {
              userId,
              helperEntityId,
              helperState,
              name: userName,
            }
          : null;
      })
      .filter(Boolean)
      .sort((left, right) => left.name.localeCompare(right.name));
  }

  _getChoreOptions(selectedUserOption) {
    const chores = selectedUserOption?.helperState?.attributes?.chores;
    if (!Array.isArray(chores)) {
      return [];
    }

    return chores
      .map((chore) => {
        if (
          !chore ||
          typeof chore !== "object" ||
          typeof chore.chore_id !== "string" ||
          typeof chore.eid !== "string" ||
          typeof chore.name !== "string"
        ) {
          return null;
        }

        return {
          choreId: chore.chore_id,
          entityId: chore.eid,
          name: chore.name,
        };
      })
      .filter(Boolean)
      .sort((left, right) => left.name.localeCompare(right.name));
  }

  _syncLocalSelections(userOptions, choreOptions) {
    if (
      this._selectedUserId &&
      !userOptions.some((option) => option.userId === this._selectedUserId)
    ) {
      this._selectedUserId = "";
      this._selectedChoreId = "";
      this._resetDraft();
    }

    if (
      this._selectedChoreId &&
      !choreOptions.some((option) => option.choreId === this._selectedChoreId)
    ) {
      this._selectedChoreId = "";
      this._resetDraft();
    }

    const allowedNames = new Set(userOptions.map((option) => option.name));
    this._draft.assignedUserNames = this._draft.assignedUserNames.filter((name) =>
      allowedNames.has(name),
    );
  }

  _loadDraftFromChore(choreOption) {
    if (!this._hass || !choreOption) {
      this._resetDraft();
      return;
    }

    const choreState = this._hass.states[choreOption.entityId];
    const choreAttrs = choreState?.attributes || {};
    const assignedUserNames = Array.isArray(choreAttrs.assigned_user_names)
      ? choreAttrs.assigned_user_names.filter((name) => typeof name === "string")
      : [];
    const pointsValue = choreAttrs.default_points;
    const parsedPoints = Number(pointsValue);
    const normalizedPoints =
      pointsValue === "" || pointsValue === null || pointsValue === undefined
        ? ""
        : Number.isFinite(parsedPoints)
          ? String(pointsValue)
          : "";

    this._draft = {
      name:
        typeof choreAttrs.chore_name === "string" && choreAttrs.chore_name.trim()
          ? choreAttrs.chore_name
          : choreOption.name,
      points: normalizedPoints,
      assignedUserNames,
      completionCriteria:
        typeof choreAttrs.completion_criteria === "string" &&
        choreAttrs.completion_criteria.trim()
          ? choreAttrs.completion_criteria
          : "independent",
      description:
        typeof choreAttrs.description === "string" ? choreAttrs.description : "",
      icon: typeof choreAttrs.icon === "string" ? choreAttrs.icon : "",
      dueDate: this._toDateTimeLocalValue(choreAttrs.due_date),
      frequency:
        typeof choreAttrs.recurring_frequency === "string" &&
        choreAttrs.recurring_frequency.trim()
          ? choreAttrs.recurring_frequency
          : "none",
    };
  }

  _setMode(mode) {
    if (mode !== "create" && mode !== "edit") {
      return;
    }

    this._mode = mode;
    this._selectedChoreId = "";
    if (mode === "create") {
      this._selectedUserId = "";
    }
    this._resetDraft();
    this._setMessage("", "info");
    this._render();
  }

  _bindEvents(systemHelperState, translations) {
    const modeButtons = this.shadowRoot.querySelectorAll("[data-mode]");
    const manageUserSelect = this.shadowRoot.querySelector("#manage-user");
    const choreSelect = this.shadowRoot.querySelector("#selected-chore");
    const nameInput = this.shadowRoot.querySelector("#chore-name");
    const pointsInput = this.shadowRoot.querySelector("#chore-points");
    const assigneeSelect = this.shadowRoot.querySelector("#chore-assignees");
    const completionCriteriaSelect = this.shadowRoot.querySelector(
      "#chore-completion-criteria",
    );
    const descriptionInput = this.shadowRoot.querySelector("#chore-description");
    const iconInput = this.shadowRoot.querySelector("#chore-icon");
    const dueDateInput = this.shadowRoot.querySelector("#chore-due-date");
    const frequencySelect = this.shadowRoot.querySelector("#chore-frequency");
    const submitButton = this.shadowRoot.querySelector("#submit");
    const resetButton = this.shadowRoot.querySelector("#reset");

    modeButtons.forEach((button) => {
      button.addEventListener("click", () => {
        this._setMode(button.dataset.mode);
      });
    });

    if (manageUserSelect) {
      manageUserSelect.addEventListener("change", (event) => {
        this._selectedUserId = event.target.value;
        this._selectedChoreId = "";
        this._resetDraft();
        this._setMessage("", "info");
        this._render();
      });
    }

    if (choreSelect) {
      choreSelect.addEventListener("change", (event) => {
        this._selectedChoreId = event.target.value;

        const userOptions = this._getUserOptions(systemHelperState);
        const selectedUserOption = userOptions.find(
          (option) => option.userId === this._selectedUserId,
        );
        const choreOptions = this._getChoreOptions(selectedUserOption);
        const selectedChore = choreOptions.find(
          (option) => option.choreId === this._selectedChoreId,
        );

        this._loadDraftFromChore(selectedChore);
        this._setMessage("", "info");
        this._render();
      });
    }

    if (nameInput) {
      nameInput.addEventListener("input", (event) => {
        this._draft.name = event.target.value;
      });
    }

    if (pointsInput) {
      pointsInput.addEventListener("input", (event) => {
        this._draft.points = event.target.value;
      });
    }

    if (assigneeSelect) {
      assigneeSelect.addEventListener("change", (event) => {
        this._draft.assignedUserNames = Array.from(event.target.selectedOptions).map(
          (option) => option.value,
        );
      });
    }

    if (completionCriteriaSelect) {
      completionCriteriaSelect.addEventListener("change", (event) => {
        this._draft.completionCriteria = event.target.value;
      });
    }

    if (descriptionInput) {
      descriptionInput.addEventListener("input", (event) => {
        this._draft.description = event.target.value;
      });
    }

    if (iconInput) {
      iconInput.addEventListener("input", (event) => {
        this._draft.icon = event.target.value;
      });
    }

    if (dueDateInput) {
      dueDateInput.addEventListener("input", (event) => {
        this._draft.dueDate = event.target.value;
      });
    }

    if (frequencySelect) {
      frequencySelect.addEventListener("change", (event) => {
        this._draft.frequency = event.target.value;
      });
    }

    if (submitButton) {
      submitButton.addEventListener("click", () => {
        this._handleSubmit(systemHelperState, translations);
      });
    }

    if (resetButton) {
      resetButton.addEventListener("click", () => {
        this._selectedChoreId = "";
        this._resetDraft();
        this._setMessage("", "info");
        this._render();
      });
    }
  }

  _validateDraft(translations) {
    if (this._mode === "edit" && !this._selectedChoreId) {
      return this._t(
        translations,
        "select_chore_to_manage",
        "Select a chore to manage",
      );
    }

    if (!this._draft.name.trim()) {
      return this._t(
        translations,
        "quick_chore_editor_chore_name_required",
        "Chore name is required",
      );
    }

    if (this._draft.assignedUserNames.length === 0) {
      return this._t(translations, "select_user_first", "Select a user first");
    }

    const points = Number(this._draft.points);
    if (!Number.isFinite(points) || points < 0) {
      return this._t(
        translations,
        "quick_chore_editor_points_invalid",
        "Points must be a number greater than or equal to 0",
      );
    }

    return "";
  }

  async _handleSubmit(systemHelperState, translations) {
    if (!this._hass || !this._config || this._busy || !systemHelperState) {
      return;
    }

    const validationError = this._validateDraft(translations);
    if (validationError) {
      this._setMessage(validationError, "error");
      this._render();
      return;
    }

    const payload = {
      name: this._draft.name.trim(),
      points: Number(this._draft.points),
      assigned_user_names: [...this._draft.assignedUserNames],
      completion_criteria: this._draft.completionCriteria,
      description: this._draft.description.trim(),
      icon: this._draft.icon.trim(),
      frequency: this._draft.frequency,
    };

    const dueDate = this._fromDateTimeLocalValue(this._draft.dueDate);
    if (dueDate) {
      payload.due_date = dueDate;
    }

    if (this._mode === "edit") {
      payload.id = this._selectedChoreId;
    }

    const configEntryId = this._getResolvedConfigEntryId(systemHelperState);
    if (configEntryId) {
      payload.config_entry_id = configEntryId;
    }

    const serviceName = this._mode === "edit" ? "update_chore" : "create_chore";
    const busyMessage = this._t(
      translations,
      this._mode === "edit"
        ? "quick_chore_editor_update_action"
        : "quick_chore_editor_create_action",
      this._mode === "edit" ? "Update chore" : "Create chore",
    );

    this._busy = true;
    this._setMessage(`${busyMessage}...`, "info");
    this._render();

    try {
      await this._hass.callService("choreops", serviceName, payload);

      if (this._mode === "edit") {
        this._selectedChoreId = "";
        this._resetDraft();
        this._setMessage(
          this._t(
            translations,
            "quick_chore_editor_updated",
            "Chore updated",
          ),
          "success",
        );
      } else {
        this._resetDraft();
        this._setMessage(
          this._t(
            translations,
            "quick_chore_editor_created",
            "Chore created",
          ),
          "success",
        );
      }
    } catch (error) {
      const message =
        error?.body?.message ||
        error?.message ||
        this._t(
          translations,
          "quick_chore_editor_request_failed",
          "Chore request failed",
        );
      this._setMessage(message, "error");
    } finally {
      this._busy = false;
      this._render();
    }
  }

  _render() {
    if (!this.shadowRoot || !this._config) {
      return;
    }

    const resolution = this._resolveSystemHelper();
    const systemHelperState = resolution.state;
    const translations = this._getTranslations(systemHelperState);
    const userOptions = this._getUserOptions(systemHelperState);
    const selectedUserOption = userOptions.find(
      (option) => option.userId === this._selectedUserId,
    );
    const choreOptions = this._getChoreOptions(selectedUserOption);
    this._syncLocalSelections(userOptions, choreOptions);

    const helperEntityId = systemHelperState?.entity_id || "";
    const hasHelper = Boolean(systemHelperState);
    const canSubmit = hasHelper && userOptions.length > 0 && !this._busy;
    const createModeActive = this._mode === "create";
    const editModeActive = this._mode === "edit";
    const messageClass = this._message ? `message ${this._messageType}` : "message";

    const title = this._config.title || this._t(translations, "management", "Management");
    const helperHint = hasHelper
      ? this._escapeHtml(helperEntityId)
      : this._t(
          translations,
          "quick_chore_editor_missing_helper",
          resolution.error || "No ChoreOps system dashboard helper resolved",
        );

    const userOptionsMarkup = userOptions
      .map((option) => {
        const selected = option.userId === this._selectedUserId ? "selected" : "";
        return `<option value="${this._escapeHtml(option.userId)}" ${selected}>${this._escapeHtml(option.name)}</option>`;
      })
      .join("");

    const choreOptionsMarkup = choreOptions
      .map((option) => {
        const selected = option.choreId === this._selectedChoreId ? "selected" : "";
        return `<option value="${this._escapeHtml(option.choreId)}" ${selected}>${this._escapeHtml(option.name)}</option>`;
      })
      .join("");

    const assigneeOptionsMarkup = userOptions
      .map((option) => {
        const selected = this._draft.assignedUserNames.includes(option.name)
          ? "selected"
          : "";
        return `<option value="${this._escapeHtml(option.name)}" ${selected}>${this._escapeHtml(option.name)}</option>`;
      })
      .join("");

    const completionCriteriaOptionsMarkup = this._getCompletionCriteriaOptions()
      .map((value) => {
        const selected = this._draft.completionCriteria === value ? "selected" : "";
        return `<option value="${this._escapeHtml(value)}" ${selected}>${this._escapeHtml(this._t(translations, value, value))}</option>`;
      })
      .join("");

    const supportedFrequencyOptions = this._getSupportedFrequencyOptions();
    const frequencyOptions = [...supportedFrequencyOptions];
    if (
      this._draft.frequency &&
      !supportedFrequencyOptions.includes(this._draft.frequency)
    ) {
      frequencyOptions.unshift(this._draft.frequency);
    }

    const frequencyOptionsMarkup = frequencyOptions
      .map((value, index) => {
        const selected = this._draft.frequency === value ? "selected" : "";
        const unsupported =
          index === 0 && !supportedFrequencyOptions.includes(value) ? "disabled" : "";
        return `<option value="${this._escapeHtml(value)}" ${selected} ${unsupported}>${this._escapeHtml(this._t(translations, value, value))}</option>`;
      })
      .join("");

    const modeSummary = createModeActive
      ? this._t(
          translations,
          "quick_chore_editor_create",
          "Create chore",
        )
      : this._t(translations, "quick_chore_editor_edit", "Edit chore");

    const editHint = !this._selectedUserId
      ? this._t(translations, "select_user_to_manage_chores_first", "Choose a user above to manage chores.")
      : choreOptions.length === 0
        ? this._t(
            translations,
            "chore_selector_unavailable",
            "Chore selector unavailable for this profile.",
          )
        : "";

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
        }

        ha-card {
          padding: 18px;
          background: linear-gradient(
            180deg,
            color-mix(in srgb, var(--card-background-color) 86%, var(--primary-color) 14%),
            var(--card-background-color)
          );
        }

        .header {
          display: flex;
          justify-content: space-between;
          align-items: start;
          gap: 12px;
          margin-bottom: 14px;
        }

        .title-block {
          display: grid;
          gap: 4px;
        }

        .title {
          font-size: 1.05rem;
          font-weight: 700;
          color: var(--primary-text-color);
        }

        .subtitle,
        .hint,
        .message {
          color: var(--secondary-text-color);
          font-size: 0.84rem;
        }

        .mode-switch {
          display: inline-grid;
          grid-auto-flow: column;
          gap: 8px;
          padding: 4px;
          border-radius: 999px;
          background: color-mix(in srgb, var(--card-background-color) 80%, var(--primary-color) 20%);
        }

        .mode-switch button,
        .actions button {
          font: inherit;
          border: 0;
          border-radius: 999px;
          padding: 10px 14px;
          cursor: pointer;
          transition: opacity 120ms ease;
        }

        .mode-switch button {
          background: transparent;
          color: var(--secondary-text-color);
          font-weight: 600;
        }

        .mode-switch button.active {
          background: var(--primary-color);
          color: var(--text-primary-color, var(--primary-background-color));
        }

        .layout {
          display: grid;
          gap: 14px;
        }

        .panel {
          display: grid;
          gap: 12px;
          padding: 14px;
          border-radius: 16px;
          background: color-mix(in srgb, var(--card-background-color) 88%, var(--primary-color) 12%);
          border: 1px solid color-mix(in srgb, var(--divider-color) 74%, var(--primary-color) 26%);
        }

        label {
          display: grid;
          gap: 6px;
          color: var(--primary-text-color);
          font-size: 0.9rem;
          font-weight: 600;
        }

        input,
        select,
        textarea {
          width: 100%;
          box-sizing: border-box;
          border: 1px solid var(--divider-color);
          border-radius: 12px;
          background: var(--card-background-color);
          color: var(--primary-text-color);
          padding: 10px 12px;
          font: inherit;
        }

        select[multiple] {
          min-height: 124px;
        }

        textarea {
          min-height: 88px;
          resize: vertical;
        }

        input:focus,
        select:focus,
        textarea:focus {
          outline: 2px solid var(--primary-color);
          outline-offset: 1px;
        }

        .actions {
          display: flex;
          justify-content: space-between;
          gap: 10px;
          flex-wrap: wrap;
        }

        .actions button.primary {
          background: var(--primary-color);
          color: var(--text-primary-color, var(--primary-background-color));
          font-weight: 700;
        }

        .actions button.secondary {
          background: color-mix(in srgb, var(--card-background-color) 70%, var(--primary-color) 30%);
          color: var(--primary-text-color);
        }

        button[disabled] {
          cursor: default;
          opacity: 0.55;
        }

        .message {
          min-height: 1.2rem;
        }

        .message.success {
          color: var(--success-color);
        }

        .message.warning {
          color: var(--warning-color);
        }

        .message.error {
          color: var(--error-color);
        }
      </style>
      <ha-card>
        <div class="header">
          <div class="title-block">
            <div class="title">${this._escapeHtml(title)}</div>
            <div class="subtitle">${this._escapeHtml(modeSummary)}</div>
            <div class="hint">${helperHint}</div>
          </div>
          <div class="mode-switch">
            <button type="button" data-mode="create" class="${createModeActive ? "active" : ""}" ${this._busy ? "disabled" : ""}>${this._escapeHtml(this._t(translations, "quick_chore_editor_create", "Create"))}</button>
            <button type="button" data-mode="edit" class="${editModeActive ? "active" : ""}" ${this._busy ? "disabled" : ""}>${this._escapeHtml(this._t(translations, "quick_chore_editor_edit", "Edit"))}</button>
          </div>
        </div>
        <div class="layout">
          ${editModeActive ? `
            <div class="panel">
              <label>
                <span>${this._escapeHtml(this._t(translations, "manage_for", "Manage for"))}</span>
                <select id="manage-user" ${!hasHelper || this._busy ? "disabled" : ""}>
                  <option value="">${this._escapeHtml(this._t(translations, "select_user_first", "Select a user first"))}</option>
                  ${userOptionsMarkup}
                </select>
              </label>
              <label>
                <span>${this._escapeHtml(this._t(translations, "select_chore_to_manage", "Select a chore to manage"))}</span>
                <select id="selected-chore" ${!this._selectedUserId || this._busy ? "disabled" : ""}>
                  <option value="">${this._escapeHtml(this._t(translations, "select_chore_to_manage", "Select a chore to manage"))}</option>
                  ${choreOptionsMarkup}
                </select>
              </label>
              <div class="hint">${this._escapeHtml(editHint)}</div>
            </div>
          ` : ""}
          <div class="panel">
            <label>
              <span>${this._escapeHtml(this._t(translations, "quick_chore_editor_chore_name", "Chore name"))}</span>
              <input id="chore-name" type="text" value="${this._escapeHtml(this._draft.name)}" placeholder="${this._escapeHtml(this._t(translations, "quick_chore_editor_chore_name", "Chore name"))}" ${!hasHelper || this._busy ? "disabled" : ""}>
            </label>
            <label>
              <span>${this._escapeHtml(this._t(translations, "quick_chore_editor_points", "Points"))}</span>
              <input id="chore-points" type="number" min="0" step="0.01" value="${this._escapeHtml(this._draft.points)}" placeholder="0" ${!hasHelper || this._busy ? "disabled" : ""}>
            </label>
            <label>
              <span>${this._escapeHtml(this._t(translations, "assigned_to", "Assigned To"))}</span>
              <select id="chore-assignees" multiple ${!hasHelper || this._busy ? "disabled" : ""}>
                ${assigneeOptionsMarkup}
              </select>
            </label>
            <label>
              <span>${this._escapeHtml(this._t(translations, "completion_criteria", "Completion Type"))}</span>
              <select id="chore-completion-criteria" ${!hasHelper || this._busy ? "disabled" : ""}>
                ${completionCriteriaOptionsMarkup}
              </select>
            </label>
            <label>
              <span>${this._escapeHtml(this._t(translations, "quick_chore_editor_description", "Description"))}</span>
              <textarea id="chore-description" ${!hasHelper || this._busy ? "disabled" : ""}>${this._escapeHtml(this._draft.description)}</textarea>
            </label>
            <label>
              <span>${this._escapeHtml(this._t(translations, "quick_chore_editor_icon", "Icon"))}</span>
              <input id="chore-icon" type="text" value="${this._escapeHtml(this._draft.icon)}" ${!hasHelper || this._busy ? "disabled" : ""}>
            </label>
            <label>
              <span>${this._escapeHtml(this._t(translations, "due_date", "Due Date"))}</span>
              <input id="chore-due-date" type="datetime-local" value="${this._escapeHtml(this._draft.dueDate)}" ${!hasHelper || this._busy ? "disabled" : ""}>
            </label>
            <label>
              <span>${this._escapeHtml(this._t(translations, "quick_chore_editor_frequency", "Frequency"))}</span>
              <select id="chore-frequency" ${!hasHelper || this._busy ? "disabled" : ""}>
                ${frequencyOptionsMarkup}
              </select>
            </label>
            <div class="actions">
              <button id="reset" type="button" class="secondary" ${!canSubmit ? "disabled" : ""}>${this._escapeHtml(this._t(translations, "clear_selection", "Clear selection"))}</button>
              <button id="submit" type="button" class="primary" ${canSubmit ? "" : "disabled"}>${this._escapeHtml(this._busy ? `${this._t(translations, this._mode === "edit" ? "quick_chore_editor_update_action" : "quick_chore_editor_create_action", this._mode === "edit" ? "Update chore" : "Create chore")}...` : this._t(translations, this._mode === "edit" ? "quick_chore_editor_update_action" : "quick_chore_editor_create_action", this._mode === "edit" ? "Update chore" : "Create chore"))}</button>
            </div>
            <div class="${messageClass}">${this._escapeHtml(this._message)}</div>
          </div>
        </div>
      </ha-card>
    `;

    this._bindEvents(systemHelperState, translations);
  }
}

class ChoreOpsCreateChorePocAliasCard extends ChoreOpsQuickChoreEditorPocCard {}

const registrationState =
  window.__choreopsQuickChoreEditorPocRegistration ||
  (window.__choreopsQuickChoreEditorPocRegistration = {
    elementsDefined: false,
    cardsRegistered: false,
  });

if (!registrationState.elementsDefined) {
  if (!customElements.get("choreops-quick-chore-editor-poc")) {
    customElements.define(
      "choreops-quick-chore-editor-poc",
      ChoreOpsQuickChoreEditorPocCard,
    );
  }

  if (!customElements.get("choreops-create-chore-poc")) {
    customElements.define(
      "choreops-create-chore-poc",
      ChoreOpsCreateChorePocAliasCard,
    );
  }

  registrationState.elementsDefined = true;
}

window.customCards = window.customCards || [];

if (!registrationState.cardsRegistered) {
  window.customCards.push({
    type: "choreops-create-chore-poc",
    name: "ChoreOps Create Chore POC",
    description: "Temporary sandbox alias for the quick chore editor POC.",
  });
  window.customCards.push({
    type: "choreops-quick-chore-editor-poc",
    name: "ChoreOps Quick Chore Editor POC",
    description: "Temporary sandbox card that creates and edits chores through direct ChoreOps service calls.",
  });

  registrationState.cardsRegistered = true;
}
