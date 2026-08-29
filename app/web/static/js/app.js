"use strict";

const form = document.querySelector("#consultation-form");
const query = document.querySelector("#query");
const fiscalYear = document.querySelector("#fiscal-year");
const mode = document.querySelector("#mode");
const submitButton = document.querySelector("#submit-button");
const statusMessage = document.querySelector("#status-message");
const resultContent = document.querySelector("#result-content");
const queryError = document.querySelector("#query-error");
const characterCount = document.querySelector("#character-count");

const roleTargets = {
  normative: {
    group: document.querySelector("#normative-evidence-group"),
    list: document.querySelector("#result-evidence-normative"),
  },
  supporting: {
    group: document.querySelector("#supporting-evidence-group"),
    list: document.querySelector("#result-evidence-supporting"),
  },
  jurisprudence: {
    group: document.querySelector("#jurisprudence-evidence-group"),
    list: document.querySelector("#result-evidence-jurisprudence"),
  },
  other: {
    group: document.querySelector("#other-evidence-group"),
    list: document.querySelector("#result-evidence-other"),
  },
};

function setStatus(kind, message) {
  statusMessage.className = `status ${kind}`;
  statusMessage.textContent = message;
}

function validateQuery() {
  const value = query.value.trim();
  characterCount.textContent = `${query.value.length} / 4000`;
  if (value.length < 3) {
    queryError.textContent = "Escribe una consulta de al menos 3 caracteres.";
    query.setAttribute("aria-invalid", "true");
    return false;
  }
  queryError.textContent = "";
  query.removeAttribute("aria-invalid");
  return true;
}

function appendTextItem(list, text) {
  const item = document.createElement("li");
  item.textContent = text;
  list.append(item);
}

function displayValue(value, fallback = "No disponible") {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  return String(value);
}

function formatScore(score) {
  if (typeof score !== "number" || !Number.isFinite(score)) {
    return null;
  }
  return `${Math.round(score * 100)}%`;
}

function formatPages(item) {
  if (!item.page_start) {
    return null;
  }
  if (!item.page_end || item.page_end === item.page_start) {
    return `p. ${item.page_start}`;
  }
  return `pp. ${item.page_start}–${item.page_end}`;
}

function appendMeta(container, label, value) {
  if (value === null || value === undefined || value === "") {
    return;
  }
  const pair = document.createElement("span");
  pair.className = "evidence-meta-item";
  const strong = document.createElement("strong");
  strong.textContent = `${label}: `;
  pair.append(strong, document.createTextNode(String(value)));
  container.append(pair);
}

function renderEvidenceCard(item) {
  const article = document.createElement("article");
  article.className = "evidence-card";

  const header = document.createElement("div");
  header.className = "evidence-card-header";

  const heading = document.createElement("h5");
  heading.textContent = (
    item.title
    || item.unit
    || item.source_reference
    || item.ref_id
    || "Evidencia"
  );

  const sourceBadge = document.createElement("span");
  sourceBadge.className = `source-badge ${item.role || "other"}`;
  sourceBadge.textContent = item.source_label || "Otra evidencia";
  header.append(heading, sourceBadge);

  const meta = document.createElement("div");
  meta.className = "evidence-meta";
  appendMeta(meta, "Unidad", item.unit);
  appendMeta(meta, "Versión", item.version);
  appendMeta(meta, "Ejercicio", item.fiscal_year);
  appendMeta(meta, "Páginas", formatPages(item));
  appendMeta(meta, "Score", formatScore(item.score));

  article.append(header);
  if (meta.childElementCount > 0) {
    article.append(meta);
  }

  if (item.snippet) {
    const excerpt = document.createElement("p");
    excerpt.className = "evidence-snippet";
    excerpt.textContent = item.snippet;
    article.append(excerpt);
  }

  const technical = document.createElement("details");
  technical.className = "evidence-technical";
  const summary = document.createElement("summary");
  summary.textContent = "Detalles de referencia";
  const reference = document.createElement("dl");
  reference.className = "technical-trace";
  const pairs = [
    ["Referencia", item.ref_id],
    ["Archivo", item.source_reference],
    ["Documento", item.document_id],
    ["Publicación", item.publication_date],
    ["Vigente desde", item.effective_from],
    ["Vigente hasta", item.effective_to],
  ];
  pairs.forEach(([label, value]) => {
    if (value === null || value === undefined || value === "") {
      return;
    }
    const row = document.createElement("div");
    const dt = document.createElement("dt");
    const dd = document.createElement("dd");
    dt.textContent = label;
    dd.textContent = String(value);
    row.append(dt, dd);
    reference.append(row);
  });
  technical.append(summary, reference);
  article.append(technical);

  return article;
}

function resetEvidenceGroups() {
  Object.values(roleTargets).forEach(({group, list}) => {
    list.replaceChildren();
    group.hidden = true;
  });
}

function renderEvidence(items) {
  resetEvidenceGroups();
  const evidenceCount = document.querySelector("#evidence-count");
  evidenceCount.textContent = `${items.length} evidencia${items.length === 1 ? "" : "s"}`;

  items.forEach((item) => {
    const target = roleTargets[item.role] || roleTargets.other;
    target.list.append(renderEvidenceCard(item));
    target.group.hidden = false;
  });
}

function renderTraceability(result) {
  const trace = result.traceability;
  const traceBlock = document.querySelector("#trace-block");
  if (!trace || typeof trace !== "object") {
    traceBlock.hidden = true;
    return;
  }

  document.querySelector("#result-folio").textContent = displayValue(result.folio);
  document.querySelector("#result-intent").textContent = displayValue(trace.primary_intent);
  document.querySelector("#result-trace-year").textContent = displayValue(
    trace.query_fiscal_year,
    "No especificado"
  );
  document.querySelector("#result-created-at").textContent = displayValue(
    trace.created_at_utc
  );
  document.querySelector("#result-execution-id").textContent = displayValue(
    trace.execution_id
  );
  document.querySelector("#result-result-hash").textContent = displayValue(
    trace.canonical_result_sha256
  );

  const reviewBadge = document.querySelector("#review-badge");
  if (result.requires_human_review) {
    reviewBadge.textContent = "Revisión humana requerida";
    reviewBadge.hidden = false;
  } else {
    reviewBadge.hidden = true;
  }

  const events = document.querySelector("#result-trace-events");
  events.replaceChildren();
  const traceEvents = Array.isArray(trace.events) ? trace.events : [];
  traceEvents.forEach((event) => {
    const item = document.createElement("li");
    item.className = "trace-event";

    const top = document.createElement("div");
    top.className = "trace-event-heading";
    const stage = document.createElement("strong");
    stage.textContent = `${event.sequence}. ${event.stage}`;
    const status = document.createElement("span");
    status.className = `trace-status ${event.status || "unknown"}`;
    status.textContent = event.status || "unknown";
    top.append(stage, status);

    const summary = document.createElement("p");
    summary.textContent = event.summary || "Sin resumen.";
    item.append(top, summary);

    if (event.requires_human_review) {
      const note = document.createElement("small");
      note.textContent = "Esta etapa requiere revisión humana.";
      item.append(note);
    }
    events.append(item);
  });

  traceBlock.hidden = false;
}

function renderResult(payload) {
  const result = payload.result;
  if (!result) {
    resultContent.hidden = true;
    return;
  }

  const explanationBlock = document.querySelector("#summary-block");
  const explanation = document.querySelector("#result-explanation");
  const normsBlock = document.querySelector("#norms-block");
  const norms = document.querySelector("#result-norms");
  const evidenceBlock = document.querySelector("#evidence-block");
  const uncertaintyBlock = document.querySelector("#uncertainty-block");
  const uncertainties = document.querySelector("#result-uncertainties");

  norms.replaceChildren();
  uncertainties.replaceChildren();

  explanation.textContent = result.explanation || "Sin explicación disponible.";
  explanationBlock.hidden = !result.explanation;

  const normativeRefs = Array.isArray(result.applicable_normative_refs)
    ? result.applicable_normative_refs
    : [];
  normativeRefs.forEach((ref) => appendTextItem(norms, ref));
  normsBlock.hidden = normativeRefs.length === 0;

  const evidenceItems = Array.isArray(result.evidence) ? result.evidence : [];
  renderEvidence(evidenceItems);
  evidenceBlock.hidden = evidenceItems.length === 0;

  const uncertaintyItems = Array.isArray(result.uncertainties)
    ? result.uncertainties
    : [];
  uncertaintyItems.forEach((item) => {
    appendTextItem(
      uncertainties,
      item.message || "Incertidumbre registrada sin descripción."
    );
  });
  if (result.requires_human_review) {
    appendTextItem(uncertainties, "El resultado requiere revisión humana.");
  }
  uncertaintyBlock.hidden = (
    uncertaintyItems.length === 0 && !result.requires_human_review
  );

  renderTraceability(result);
  resultContent.hidden = false;
}

async function submitConsultation(event) {
  event.preventDefault();
  if (!validateQuery()) {
    query.focus();
    return;
  }

  const yearValue = fiscalYear.value.trim();
  const payload = {
    query: query.value.trim(),
    mode: mode.value,
    fiscal_year: yearValue ? Number(yearValue) : null,
  };

  submitButton.disabled = true;
  submitButton.textContent = "Analizando…";
  setStatus("loading", "Procesando la consulta de forma segura.");
  resultContent.hidden = true;

  try {
    const response = await fetch("/api/v1/consultations", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      setStatus("error", "La entrada no pudo validarse.");
      return;
    }
    if (data.status === "ready") {
      setStatus("success", data.message);
      renderResult(data);
    } else if (data.status === "not_configured") {
      setStatus("warning", data.message);
      renderResult(data);
    } else {
      setStatus("error", data.message);
    }
  } catch {
    setStatus(
      "error",
      "No fue posible contactar el servidor. Verifica la conexión e inténtalo de nuevo."
    );
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = "Analizar consulta";
  }
}

query.addEventListener("input", validateQuery);
form.addEventListener("submit", submitConsultation);
characterCount.textContent = `${query.value.length} / 4000`;
