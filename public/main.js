const DEFAULT_ISSUES = [
  "LGBTQ+ equity",
  "Housing",
  "Public safety",
  "Transportation",
  "Public health",
  "Budget/funding",
  "Accessibility",
  "Immigrant communities",
  "Youth services",
  "Senior services",
  "Nonprofit grants",
  "Community engagement",
  "Civil rights",
  "Environmental justice",
  "Fare policy",
  "Homelessness services",
];

const HOSTED_MAX_UPLOAD_BYTES = 4 * 1024 * 1024;

const state = {
  file: null,
  fileTooLarge: false,
  customIssues: [],
  selectedIssues: new Set(["Housing", "Transportation", "Accessibility", "Budget/funding"]),
  metadata: null,
  relevance: null,
  result: null,
  error: "",
  topicError: "",
  loading: false,
  parsing: false,
};

const app = document.querySelector("#app");

function flagIcon() {
  return `
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M6 21V4.5" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>
      <path d="M7 5.2c3.5-2 5.6 1.8 9.8-.2v8.1c-4.2 2-6.3-1.8-9.8.2V5.2Z" fill="currentColor"/>
      <path d="M3.7 20.5c1.8 1 4.5 1 6.3 0" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>
    </svg>
  `;
}

function documentIcon() {
  return `
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M6 3h8l4 4v14H6V3Z" stroke="currentColor" stroke-width="2" />
      <path d="M14 3v5h5" stroke="currentColor" stroke-width="2" />
      <path d="M9 12h6M9 16h6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
    </svg>
  `;
}

function render() {
  app.innerHTML = `
    <div class="app-shell">
      ${Header()}
      <main>
        ${Hero()}
        <section class="section workflow">
          <div class="review-flow">
            ${UploadBox()}
            ${DocumentInsights()}
            ${ResultsSection()}
          </div>
        </section>
      </main>
    </div>
  `;
  bindEvents();
}

function Header() {
  return `
    <header class="topbar">
      <div class="topbar-inner">
        <div class="brand"><span class="flag-mark">${flagIcon()}</span><span>Civic Flag</span></div>
        <div class="tagline">FLAG WHAT MATTERS</div>
      </div>
    </header>
  `;
}

function Hero() {
  return `
    <section class="section hero">
      <div class="hero-grid">
        <div class="hero-copy">
          <h1>Civic Flag</h1>
          <p>Review civic documents, surface relevant issues, and organize what needs attention.</p>
        </div>
      </div>
    </section>
  `;
}

function UploadBox() {
  const fileName = state.file ? escapeHtml(state.file.name) : "No file selected";
  const noIssuesSelected = state.selectedIssues.size === 0;
  const reviewDisabled = !state.file || state.fileTooLarge || noIssuesSelected || state.loading || state.parsing;
  return `
    <section class="panel upload-card" id="upload-panel">
      <div class="upload-card-head">
        <span class="upload-icon">${documentIcon()}</span>
        <div>
          <h2>Document Upload</h2>
          <p class="helper">Choose a public agenda, staff report, board packet, policy memo, planning document, or other civic material.</p>
        </div>
      </div>
      <label class="upload-box" id="drop-zone">
        <strong>Drop a document here or click to browse</strong>
        <span class="helper">PDF, DOC, DOCX, and TXT files supported. Hosted uploads must be ${formatBytes(HOSTED_MAX_UPLOAD_BYTES)} or smaller. TXT files preferred for best text extraction accuracy.</span>
        <input class="hidden" id="file-input" type="file" accept=".pdf,.doc,.docx,.txt" />
      </label>
      <div class="selected-file">
        <span>Uploaded file</span>
        <strong>${fileName}</strong>
      </div>
      ${IssuesOfInterest()}
      <button class="button primary upload-action" data-action="analyze" ${reviewDisabled ? "disabled" : ""}>
        ${flagIcon()} ${state.loading ? "Reviewing..." : "Start Reviewing"}
      </button>
      ${noIssuesSelected ? `<p class="helper action-note">Select at least one issue of interest to start reviewing.</p>` : ""}
      ${state.parsing ? `<p class="helper">Reading document text and metadata...</p>` : ""}
      ${state.error ? `<div class="error">${escapeHtml(state.error)}</div>` : ""}
    </section>
  `;
}

function IssuesOfInterest() {
  const issues = allIssues();
  return `
    <div class="issue-section">
      <div class="subsection-head">
        <h3>Issues of Interest</h3>
        <p class="helper">Select the issues you want Civic Flag to look for.</p>
      </div>
      <div class="topics">
        ${issues.map((issue) => TopicChip(issue)).join("")}
      </div>
      <form class="custom-topic" id="custom-topic-form">
        <input id="custom-topic" placeholder="Add a custom issue" />
        <button class="button secondary" type="submit">Add</button>
      </form>
      ${state.topicError ? `<p class="helper topic-error">${escapeHtml(state.topicError)}</p>` : ""}
    </div>
  `;
}

function allIssues() {
  return [...DEFAULT_ISSUES, ...state.customIssues];
}

function TopicChip(issue) {
  const selected = state.selectedIssues.has(issue);
  return `<button class="chip ${selected ? "selected" : ""}" data-action="toggle-topic" data-issue="${escapeHtml(issue)}">${escapeHtml(issue)}</button>`;
}

function DocumentInsights() {
  if (!state.file && !state.metadata) {
    return `
      <section class="panel">
        <h2>Document Insights</h2>
        <div class="empty-state">Upload a civic document to begin.</div>
      </section>
    `;
  }
  const metadata = state.metadata || {};
  const relevance = state.relevance;
  return `
    <section class="panel">
      <h2>Document Insights</h2>
      ${state.result ? AnalysisMode(state.result) : ""}
      <div class="metadata">
        ${MetadataRow("Uploaded file", metadata.uploaded_file_name)}
        ${MetadataRow("Document type", metadata.document_type)}
        ${MetadataRow("Agency/body", metadata.agency_or_governing_body)}
        ${MetadataRow("Jurisdiction", metadata.jurisdiction)}
        ${MetadataRow("Meeting/event date", metadata.event_or_meeting_date)}
      </div>
      ${relevance ? `
        <div style="height:14px"></div>
        <div class="status ${relevance.document_is_policy_related ? "good" : "warning"}">
          <strong>Policy Relevance Check</strong><br />
          ${escapeHtml(relevance.document_relevance_explanation)}
          ${relevance.document_warning ? `<br /><br />${escapeHtml(relevance.document_warning)}` : ""}
        </div>
      ` : ""}
    </section>
  `;
}

function AnalysisMode(result) {
  const fallback = result.analysis_mode === "Fallback keyword mode";
  return `
    <div class="mode-indicator ${fallback ? "fallback" : "ai"}">
      <strong>${escapeHtml(result.analysis_mode || "Analysis mode unavailable")}</strong>
      <span>${escapeHtml(result.analysis_mode_explanation || "")}</span>
    </div>
  `;
}

function MetadataRow(label, value) {
  return `
    <div class="metadata-row">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value || "Not detected")}</strong>
    </div>
  `;
}

function ResultsSection() {
  if (!state.result) {
    return "";
  }
  const result = state.result;
  const nonPolicyEmpty = !result.document_is_policy_related && result.flagged_items.length === 0;
  return `
    ${result.document_warning ? `<div class="status warning">${escapeHtml(result.document_warning)}</div>` : ""}
    <section class="results packet-section">
      <h2>Civic Flags</h2>
      ${result.flagged_items.length
        ? result.flagged_items.map(FlagCard).join("")
        : `<div class="empty-state">${nonPolicyEmpty
          ? "No Civic Flags were generated because this upload does not appear to be policy-related. Civic Flag works best with public agendas, staff reports, board packets, policy memos, planning documents, and other civic or nonprofit materials."
          : "No strong Civic Flags found for these issues. Try adding broader issues or uploading a different document."}</div>`}
    </section>
    ${CivicBrief(result.civic_brief)}
    ${PreparedDeliverables(result.prepared_deliverables)}
  `;
}

function FlagCard(flag) {
  return `
    <article class="card flag-card">
      <div class="flag-head">
        <div class="flag-title">
          <span class="flag-pin">${flagIcon()}</span>
          <div>
            <h3>${escapeHtml(flag.title)}</h3>
            <p class="muted">Identifier: ${escapeHtml(flag.item_number_or_identifier)}</p>
          </div>
        </div>
        <span class="label ${flag.urgency_level.toLowerCase()}">${escapeHtml(flag.urgency_level)} priority</span>
      </div>
      <div class="topics">${flag.related_issues.map((issue) => `<span class="chip selected">${escapeHtml(issue)}</span>`).join("")}</div>
      <div class="flag-grid" style="margin-top:16px">
        ${Field("Relevance Summary", flag.relevance_summary)}
        ${Field("Community Impact", flag.community_impact)}
        ${Field("Suggested Action", Array.isArray(flag.suggested_follow_up) ? flag.suggested_follow_up.join("; ") : flag.suggested_follow_up)}
        ${Field("Confidence Level", flag.confidence)}
      </div>
      <div class="field">
        <strong>Supporting Excerpt</strong>
        <div class="excerpt">${escapeHtml(flag.source_excerpt)}</div>
      </div>
      ${flag.possible_public_comment_angle ? Field("Possible Public Comment Angle", flag.possible_public_comment_angle) : ""}
    </article>
  `;
}

function Field(label, value) {
  return `<div class="field"><strong>${escapeHtml(label)}</strong>${escapeHtml(value || "Not detected")}</div>`;
}

function CivicBrief(brief) {
  if (!brief) return "";
  return `
    <section class="card brief">
      <h2>Civic Brief</h2>
      ${Field("Overall document summary", brief.overall_document_summary)}
      ${ListField("Main issues found", brief.main_issues_found)}
      ${Field("Document Relevance", brief.policy_relevance)}
      ${Field("Top 3 flags to review", brief.top_3_flags_to_review?.length ? brief.top_3_flags_to_review.join("; ") : "No strong flags found")}
      ${Field("Recommended next action", brief.recommended_next_action)}
      ${Field("Suggested audience to notify", brief.suggested_audience_to_notify)}
      ${Field("Important caveats", brief.important_caveats)}
    </section>
  `;
}

function PreparedDeliverables(deliverables) {
  if (!deliverables) return "";
  return `
    <section class="card deliverables">
      <h2>Prepared Deliverables</h2>
      ${Field("Executive summary", deliverables.executive_summary)}
      <div class="deliverable-grid">
        ${ListField("Priority review list", deliverables.priority_review_list)}
        ${ListField("Suggested follow-up questions", deliverables.suggested_follow_up_questions)}
        ${ListField("Possible public comment talking points", deliverables.possible_public_comment_talking_points)}
        ${ListField("Suggested outreach or notification list", deliverables.suggested_outreach_or_notification_list)}
      </div>
      ${Field("Notes for future monitoring", deliverables.notes_for_future_monitoring)}
    </section>
  `;
}

function ListField(label, values) {
  const items = Array.isArray(values) ? values.filter(Boolean) : [];
  if (!items.length) {
    return Field(label, "Not detected");
  }
  return `
    <div class="field">
      <strong>${escapeHtml(label)}</strong>
      <ul class="clean-list">
        ${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
      </ul>
    </div>
  `;
}

function bindEvents() {
  document.querySelector("#file-input")?.addEventListener("change", async (event) => {
    const file = event.target.files[0];
    if (file) await setFile(file);
  });

  const dropZone = document.querySelector("#drop-zone");
  dropZone?.addEventListener("dragover", (event) => {
    event.preventDefault();
    dropZone.classList.add("dragging");
  });
  dropZone?.addEventListener("dragleave", () => {
    dropZone.classList.remove("dragging");
  });
  dropZone?.addEventListener("drop", async (event) => {
    event.preventDefault();
    dropZone.classList.remove("dragging");
    const file = event.dataTransfer.files[0];
    if (file) await setFile(file);
  });

  document.querySelector("#custom-topic-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    const input = document.querySelector("#custom-topic");
    const value = input.value.trim();
    const duplicate = allIssues().some((issue) => issue.toLowerCase() === value.toLowerCase());
    if (!value) {
      state.topicError = "Enter an issue before adding it.";
      render();
      return;
    }
    if (duplicate) {
      state.topicError = "That issue is already in the list.";
      render();
      return;
    }
    state.customIssues.push(value);
    state.selectedIssues.add(value);
    state.topicError = "";
    input.value = "";
    render();
  });

  document.querySelectorAll("[data-action]").forEach((element) => {
    element.addEventListener("click", async (event) => {
      const action = element.dataset.action;
      if (action === "toggle-topic") {
        event.preventDefault();
        const issue = element.dataset.issue;
        state.selectedIssues.has(issue) ? state.selectedIssues.delete(issue) : state.selectedIssues.add(issue);
        render();
      }
      if (action === "analyze") {
        await analyze();
      }
    });
  });
}

async function setFile(file) {
  state.file = file;
  state.result = null;
  state.error = "";
  state.fileTooLarge = false;
  if (file.size > HOSTED_MAX_UPLOAD_BYTES) {
    state.metadata = null;
    state.relevance = null;
    state.fileTooLarge = true;
    state.error = `${file.name} is ${formatBytes(file.size)}, which is too large for the hosted version. Vercel Functions accept request bodies up to about 4.5 MB, so please upload a smaller file or export/convert the agenda to TXT before reviewing.`;
    state.parsing = false;
    render();
    return;
  }
  state.parsing = true;
  render();
  try {
    const data = await postFile("/api/parse", file);
    state.metadata = data.metadata;
    state.relevance = data.relevance;
  } catch (error) {
    state.metadata = null;
    state.relevance = null;
    state.error = error.message;
  } finally {
    state.parsing = false;
    render();
  }
}

async function analyze() {
  if (!state.file || state.fileTooLarge) return;
  state.loading = true;
  state.error = "";
  render();
  try {
    state.result = await postFile("/api/analyze", state.file, [...state.selectedIssues]);
    state.metadata = state.result.metadata;
    state.relevance = {
      document_is_policy_related: state.result.document_is_policy_related,
      document_relevance_explanation: state.result.document_relevance_explanation,
      document_warning: state.result.document_warning,
    };
  } catch (error) {
    state.error = error.message;
  } finally {
    state.loading = false;
    render();
  }
}

async function postFile(url, file, issues = []) {
  const form = new FormData();
  form.append("file", file);
  form.append("issues", JSON.stringify(issues));
  const response = await fetch(url, { method: "POST", body: form });
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json")
    ? await response.json()
    : { error: await response.text() };
  if (!response.ok) {
    throw new Error(data.error || `The request failed with status ${response.status}.`);
  }
  return data;
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes)) return "0 MB";
  return `${(bytes / (1024 * 1024)).toFixed(bytes >= 10 * 1024 * 1024 ? 1 : 2)} MB`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

render();
