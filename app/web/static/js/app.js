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
  const evidence = document.querySelector("#result-evidence");
  const folio = document.querySelector("#result-folio");
  const uncertaintyBlock = document.querySelector("#uncertainty-block");
  const uncertainties = document.querySelector("#result-uncertainties");

  norms.replaceChildren();
  evidence.replaceChildren();
  uncertainties.replaceChildren();

  explanation.textContent = result.explanation || "Sin explicación disponible.";
  explanationBlock.hidden = !result.explanation;

  const normativeRefs = Array.isArray(result.applicable_normative_refs)
    ? result.applicable_normative_refs
    : [];
  normativeRefs.forEach((ref) => appendTextItem(norms, ref));
  normsBlock.hidden = normativeRefs.length === 0;

  folio.textContent = `Folio: ${result.folio || "no disponible"}`;
  const evidenceItems = Array.isArray(result.evidence) ? result.evidence : [];
  evidenceItems.forEach((item) => {
    appendTextItem(
      evidence,
      `${item.kind}: ${item.ref_id}${item.version ? ` · ${item.version}` : ""}`
    );
  });
  evidenceBlock.hidden = evidenceItems.length === 0;

  const uncertaintyItems = Array.isArray(result.uncertainties)
    ? result.uncertainties
    : [];
  uncertaintyItems.forEach((item) => appendTextItem(uncertainties, item.message));
  if (result.requires_human_review) {
    appendTextItem(uncertainties, "El resultado requiere revisión humana.");
  }
  uncertaintyBlock.hidden = (
    uncertaintyItems.length === 0 && !result.requires_human_review
  );

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
