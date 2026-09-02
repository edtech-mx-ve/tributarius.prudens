"use strict";

const form = document.querySelector("#consultation-form");
const query = document.querySelector("#query");
const fiscalYear = document.querySelector("#fiscal-year");
const mode = document.querySelector("#mode");
const jurisprudencePdf = document.querySelector("#jurisprudence-pdf");
const jurisprudenceStatus = document.querySelector("#jurisprudence-status");
const submitButton = document.querySelector("#submit-button");
const statusMessage = document.querySelector("#status-message");
const resultContent = document.querySelector("#result-content");
const queryError = document.querySelector("#query-error");
const characterCount = document.querySelector("#character-count");

let jurisprudenceSession = null;

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

async function uploadJurisprudencePdf() {
  jurisprudenceSession = null;
  const file = jurisprudencePdf.files[0];
  if (!file) {
    jurisprudenceStatus.textContent = "";
    return;
  }
  if (!file.name.toLowerCase().endsWith(".pdf")) {
    jurisprudenceStatus.textContent = "Selecciona un archivo PDF.";
    jurisprudencePdf.value = "";
    return;
  }

  jurisprudencePdf.disabled = true;
  jurisprudenceStatus.textContent = "Procesando PDF jurisprudencial…";
  try {
    const response = await fetch("/api/v1/jurisprudence/session", {
      method: "POST",
      headers: {
        "Content-Type": "application/pdf",
        "X-Filename": file.name,
      },
      body: await file.arrayBuffer(),
    });
    const data = await response.json();
    if (!response.ok || data.status !== "ready") {
      jurisprudenceStatus.textContent = data.message || "No fue posible procesar el PDF.";
      return;
    }
    jurisprudenceSession = {
      sessionId: data.session_id,
      documentId: data.document_id,
    };
    jurisprudenceStatus.textContent = (
      `${data.filename}: ${data.page_count} página(s) procesada(s).`
    );
  } catch {
    jurisprudenceStatus.textContent = "No fue posible cargar el PDF jurisprudencial.";
  } finally {
    jurisprudencePdf.disabled = false;
  }
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
  appendMeta(meta, "Score", formatScore(item));

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

const analyzerStatusLabels = {
  ready: "Listo",
  needs_clarification: "Requiere aclaración",
  review_required: "Revisión requerida",
  insufficient_evidence: "Evidencia insuficiente",
};

const analyzerDimensionLabels = {
  facts: "Hechos",
  normative_basis: "Fundamento normativo",
  rule_reasoning: "Razonamiento por reglas",
  calculation: "Cálculo",
};

const analyzerStateLabels = {
  complete: "Completo",
  partial: "Parcial",
  missing: "Faltante",
  not_applicable: "No aplica",
};

const analyzerChannelLabels = {
  normative: "Normativa",
  rbs: "RBS",
  cbr: "CBR",
  jurisprudence: "Jurisprudencia",
  calculation: "Cálculo",
};

const analyzerIntentLabels = {
  understand_tax_system: "Comprender el sistema fiscal",
  identify_obligations: "Identificar obligaciones",
  know_rights: "Conocer derechos",
  calculate_isr: "Calcular ISR",
  calculate_iva: "Calcular IVA",
  analyze_authority_act: "Analizar acto de autoridad",
  review_debt_noncompliance: "Revisar adeudo o incumplimiento",
  defense_options: "Opciones de defensa",
  interpret_provision: "Interpretar disposición",
  related_jurisprudence: "Jurisprudencia relacionada",
  similar_cases: "Casos semejantes",
  learn_tax_law: "Aprender derecho fiscal",
  unknown: "Por determinar",
};

function labelFromMap(value, labels) {
  if (value === null || value === undefined || value === "") {
    return "No disponible";
  }
  return labels[value] || String(value).replaceAll("_", " ");
}

function clearNode(selector) {
  const node = document.querySelector(selector);
  node.replaceChildren();
  return node;
}

function createAnalyzerCard(title, value, state = "") {
  const article = document.createElement("article");
  article.className = `analyzer-card ${state}`.trim();

  const heading = document.createElement("strong");
  heading.textContent = title;
  const detail = document.createElement("span");
  detail.textContent = value;

  article.append(heading, detail);
  return article;
}

function renderAnalyzerFacts(analysis) {
  const block = document.querySelector("#analyzer-facts-block");
  const container = clearNode("#analyzer-facts");
  const facts = Array.isArray(analysis.facts) ? analysis.facts : [];

  facts.forEach((fact) => {
    const article = document.createElement("article");
    article.className = "fact-card";

    const name = document.createElement("strong");
    name.textContent = displayValue(fact.name, "Hecho");
    const value = document.createElement("p");
    value.textContent = displayValue(fact.value);
    const origin = document.createElement("small");
    origin.textContent = fact.origin === "inferred" ? "Inferido" : "Expreso";

    article.append(name, value, origin);
    container.append(article);
  });

  document.querySelector("#analyzer-facts-count").textContent = String(facts.length);
  block.hidden = facts.length === 0;
}

function renderAnalyzerReadiness(analysis) {
  const container = clearNode("#analyzer-readiness");
  const readiness = analysis.readiness || {};
  const items = Array.isArray(readiness.completeness)
    ? readiness.completeness
    : [];

  items.forEach((item) => {
    const dimension = labelFromMap(item.dimension, analyzerDimensionLabels);
    const state = labelFromMap(item.state, analyzerStateLabels);
    const card = createAnalyzerCard(dimension, state, item.state || "");
    if (item.reason) {
      card.title = item.reason;
    }
    container.append(card);
  });

  document.querySelector("#analyzer-sufficiency").textContent = labelFromMap(
    readiness.evidentiary_sufficiency,
    {
      sufficient: "Suficiente",
      limited: "Limitada",
      insufficient: "Insuficiente",
    }
  );
  document.querySelector("#analyzer-auto-close").textContent = (
    readiness.can_close_automatically ? "Sí" : "No"
  );
}

function renderAnalyzerEvidenceMap(analysis) {
  const container = clearNode("#analyzer-evidence-map");
  const evidenceMap = analysis.evidence_map || {};
  const items = Array.isArray(evidenceMap.items) ? evidenceMap.items : [];

  items.forEach((item) => {
    const article = document.createElement("article");
    article.className = `analyzer-evidence-card ${item.present ? "present" : "absent"}`;

    const top = document.createElement("div");
    top.className = "analyzer-evidence-heading";
    const title = document.createElement("strong");
    title.textContent = labelFromMap(item.channel, analyzerChannelLabels);
    const badge = document.createElement("span");
    badge.className = `presence-badge ${item.present ? "present" : "absent"}`;
    badge.textContent = item.present ? "Presente" : "No aportada";
    top.append(title, badge);
    article.append(top);

    const refs = Array.isArray(item.references) ? item.references : [];
    if (refs.length > 0) {
      const list = document.createElement("ul");
      refs.forEach((ref) => appendTextItem(list, ref));
      article.append(list);
    } else {
      const empty = document.createElement("small");
      empty.textContent = "Sin referencias para esta consulta.";
      article.append(empty);
    }

    if (item.requires_human_review) {
      const review = document.createElement("small");
      review.className = "analyzer-review-note";
      review.textContent = "Requiere revisión humana.";
      article.append(review);
    }

    container.append(article);
  });
}

function renderAnalyzerPriorities(analysis) {
  const block = document.querySelector("#analyzer-priority-block");
  const list = clearNode("#analyzer-priorities");
  const priorities = Array.isArray(analysis.analysis_priority)
    ? analysis.analysis_priority
    : [];

  priorities.forEach((priority) => appendTextItem(list, priority));
  block.hidden = priorities.length === 0;
}

function renderAnalyzerPending(analysis) {
  const block = document.querySelector("#analyzer-pending-block");
  const list = clearNode("#analyzer-pending");
  const pending = [];

  const missingFields = Array.isArray(analysis.missing_fields)
    ? analysis.missing_fields
    : [];
  missingFields.forEach((item) => {
    pending.push(`${displayValue(item.name, "Dato faltante")}: ${displayValue(item.reason)}`);
  });

  const ambiguities = Array.isArray(analysis.ambiguities) ? analysis.ambiguities : [];
  ambiguities.forEach((item) => pending.push(`Ambigüedad: ${item}`));

  const readiness = analysis.readiness || {};
  const missingRequirements = Array.isArray(readiness.missing_requirements)
    ? readiness.missing_requirements
    : [];
  missingRequirements.forEach((item) => {
    if (!pending.includes(item)) {
      pending.push(item);
    }
  });

  if (analysis.requires_human_review) {
    pending.push("El Analyzer 1.0 requiere revisión humana.");
  }

  pending.forEach((item) => appendTextItem(list, item));
  block.hidden = pending.length === 0;
}

function renderLegalAnalysis(result) {
  const block = document.querySelector("#analyzer-block");
  const analysis = result.legal_analysis;

  if (!analysis || typeof analysis !== "object") {
    block.hidden = true;
    return;
  }

  const status = analysis.status || "unknown";
  const statusBadge = document.querySelector("#analyzer-status-badge");
  statusBadge.className = `analyzer-status ${status}`;
  statusBadge.textContent = labelFromMap(status, analyzerStatusLabels);

  const issue = analysis.issue || {};
  document.querySelector("#analyzer-primary-intent").textContent = labelFromMap(
    issue.primary_intent,
    analyzerIntentLabels
  );
  document.querySelector("#analyzer-controlling-source").textContent = displayValue(
    analysis.controlling_source,
    "Sin fuente controladora"
  ).toUpperCase();

  const profile = result.explanation_profile || {};
  document.querySelector("#analyzer-audience").textContent = displayValue(
    profile.audience_label,
    displayValue(result.mode, "No especificado")
  );

  const conclusionBlock = document.querySelector("#analyzer-conclusion-block");
  const conclusion = analysis.canonical_conclusion;
  document.querySelector("#analyzer-conclusion").textContent = displayValue(
    conclusion,
    ""
  );
  conclusionBlock.hidden = !conclusion;

  renderAnalyzerFacts(analysis);
  renderAnalyzerReadiness(analysis);
  renderAnalyzerEvidenceMap(analysis);
  renderAnalyzerPriorities(analysis);
  renderAnalyzerPending(analysis);

  document.querySelector("#analyzer-schema-version").textContent = displayValue(
    analysis.schema_version
  );
  document.querySelector("#analyzer-integrity-hash").textContent = displayValue(
    analysis.integrity_sha256
  );

  block.hidden = false;
}

const legalDecisionStatusLabels = {
  determined: "Determinada",
  conditionally_determined: "Determinación condicionada",
  insufficient_evidence: "Evidencia insuficiente",
  human_review_required: "Revisión humana requerida",
};

const legalFactStatusLabels = {
  supplied: "Aportado",
  inferred: "Inferido",
  accredited: "Acreditado",
  contested: "Controvertido",
  missing: "Faltante",
};

const legalConsequenceKindLabels = {
  obligation: "Obligación",
  right: "Derecho",
  action: "Acción",
  risk: "Riesgo",
  deadline: "Plazo",
};

function renderLegalDecision(result) {
  const block = document.querySelector("#legal-decision-block");
  const decision = result.legal_decision;

  if (!decision || typeof decision !== "object") {
    block.hidden = true;
    return;
  }

  document.querySelector("#legal-decision-status").textContent = labelFromMap(
    decision.status,
    legalDecisionStatusLabels
  );
  document.querySelector("#legal-decision-controller").textContent = displayValue(
    decision.controlling_source,
    "Sin fuente controladora"
  ).toUpperCase();

  const conclusion = decision.conclusion;
  document.querySelector("#legal-decision-conclusion").textContent = displayValue(
    conclusion,
    ""
  );
  document.querySelector("#legal-decision-conclusion-block").hidden = !conclusion;

  const factAssessments = Array.isArray(decision.fact_assessments)
    ? decision.fact_assessments
    : [];
  const facts = clearNode("#legal-decision-facts");
  factAssessments.forEach((fact) => {
    const article = document.createElement("article");
    article.className = "fact-card";
    const name = document.createElement("strong");
    name.textContent = displayValue(fact.name, "Hecho");
    const value = document.createElement("p");
    value.textContent = displayValue(fact.value, "Dato pendiente");
    const status = document.createElement("small");
    status.textContent = `${labelFromMap(fact.status, legalFactStatusLabels)} · ${
      displayValue(fact.materiality, "relevancia no determinada")
    }`;
    article.append(name, value, status);
    facts.append(article);
  });

  const reasoningSteps = decision.reasoning_chain
    && Array.isArray(decision.reasoning_chain.steps)
      ? decision.reasoning_chain.steps
      : [];
  const reasoning = clearNode("#legal-decision-reasoning");
  reasoningSteps.forEach((step) => {
    const rule = step.rule_ref ? ` [${step.rule_ref}]` : "";
    const conclusionText = displayValue(step.conclusion, "Sin conclusión");
    appendTextItem(
      reasoning,
      `${step.sequence}. ${String(step.kind).replaceAll("_", " ")}${rule}: ${conclusionText}`
    );
  });

  const consequences = decision.consequences
    && Array.isArray(decision.consequences.items)
      ? decision.consequences.items
      : [];
  const consequenceList = clearNode("#legal-decision-consequences");
  consequences.forEach((item) => {
    appendTextItem(
      consequenceList,
      `${labelFromMap(item.kind, legalConsequenceKindLabels)}: ${item.description}`
    );
  });
  if (consequences.length === 0) {
    appendTextItem(
      consequenceList,
      "No existen consecuencias jurídicas tipificadas explícitamente para esta consulta."
    );
  }

  document.querySelector("#legal-decision-fact-count").textContent = String(
    factAssessments.length
  );
  document.querySelector("#legal-decision-step-count").textContent = String(
    reasoningSteps.length
  );
  document.querySelector("#legal-decision-consequence-count").textContent = String(
    consequences.length
  );
  document.querySelector("#legal-decision-schema-version").textContent = displayValue(
    decision.schema_version
  );
  document.querySelector("#legal-decision-integrity-hash").textContent = displayValue(
    decision.integrity_sha256
  );

  block.hidden = false;
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

  renderLegalAnalysis(result);
  renderLegalDecision(result);

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
    jurisprudence_session_id: jurisprudenceSession
      ? jurisprudenceSession.sessionId
      : null,
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
jurisprudencePdf.addEventListener("change", uploadJurisprudencePdf);
form.addEventListener("submit", submitConsultation);
characterCount.textContent = `${query.value.length} / 4000`;
