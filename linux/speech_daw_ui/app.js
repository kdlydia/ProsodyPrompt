/**
 * Speech DAW Frontend Application
 *
 * Communicates with FastAPI backend via REST API.
 * Manages project state, syllable editing, and synthesis.
 */

const API_BASE = "/api";

// Global state
let projectLoaded = false;
let syllables = [];
let selectedSyllableIndex = -1;
let currentProject = null;

// ── Project Loading ──────────────────────────────────────────────────────

async function loadProject() {
    const textgridPath = document.getElementById("textgrid-path").value;
    const audioPath = document.getElementById("audio-path").value;
    const speakerName = document.getElementById("speaker-name").value || "speaker";

    if (!textgridPath) {
        showStatus("project-status", "Please enter TextGrid path", "error");
        return;
    }

    try {
        showStatus("project-status", "Loading project...", "info");

        const response = await fetch(`${API_BASE}/project/new`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                textgrid_path: textgridPath,
                audio_path: audioPath || null,
                speaker_name: speakerName,
            }),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || "Failed to load project");
        }

        const data = await response.json();
        currentProject = data.project;
        projectLoaded = true;

        showStatus("project-status", `Project loaded: ${data.syllables_count} syllables`, "success");

        // Load syllables
        await loadSyllables();

        // Show editor section
        document.getElementById("editor-section").style.display = "block";
        document.getElementById("project-section").style.display = "none";

    } catch (error) {
        showStatus("project-status", `Error: ${error.message}`, "error");
    }
}

async function loadSyllables() {
    try {
        const response = await fetch(`${API_BASE}/syllables`);
        if (!response.ok) throw new Error("Failed to load syllables");

        syllables = await response.json();
        renderTimeline();
        updateSummary();

    } catch (error) {
        showStatus("synthesis-status", `Error loading syllables: ${error.message}`, "error");
    }
}

// ── Timeline Rendering ───────────────────────────────────────────────────

function renderTimeline() {
    const timeline = document.getElementById("timeline");
    timeline.innerHTML = "";

    syllables.forEach((syl, idx) => {
        const tile = document.createElement("div");
        tile.className = "syllable-tile";
        if (syl.is_modified) tile.classList.add("modified");
        if (idx === selectedSyllableIndex) tile.classList.add("selected");

        tile.innerHTML = `
            <span class="text">${syl.text}</span>
            <span class="symbol">${escapeHtml(syl.current_symbol)}</span>
        `;

        tile.onclick = () => selectSyllable(idx);
        timeline.appendChild(tile);
    });
}

function selectSyllable(index) {
    selectedSyllableIndex = index;
    renderTimeline();
    showSyllableEditor();
}

function showSyllableEditor() {
    if (selectedSyllableIndex < 0 || selectedSyllableIndex >= syllables.length) {
        document.getElementById("syllable-editor").style.display = "none";
        return;
    }

    const syl = syllables[selectedSyllableIndex];
    document.getElementById("syl-text").textContent = syl.text;
    document.getElementById("symbol-input").value = syl.current_symbol;

    // Update toggle buttons
    document.querySelectorAll(".control-group .toggle-btn").forEach(btn => {
        btn.classList.remove("active");
    });

    const comp = syl.components;
    if (comp.height) {
        document.querySelector(`[data-value="${comp.height}"]`)?.classList.add("active");
    }
    if (comp.direction) {
        document.querySelector(`[data-value="${comp.direction}"]`)?.classList.add("active");
    }
    if (comp.has_accent) {
        document.getElementById("accent-btn")?.classList.add("active");
    }

    document.getElementById("syllable-editor").style.display = "block";
}

// ── Editing Commands ─────────────────────────────────────────────────────

async function editSyllable(changes) {
    if (selectedSyllableIndex < 0) return;

    try {
        const response = await fetch(`${API_BASE}/syllable/${selectedSyllableIndex}/edit`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(changes),
        });

        if (!response.ok) throw new Error("Edit failed");

        // Reload and re-render
        await loadSyllables();
        selectSyllable(selectedSyllableIndex);
        updateSummary();

    } catch (error) {
        showStatus("synthesis-status", `Error: ${error.message}`, "error");
    }
}

function setHeight(btn) {
    const height = btn.dataset.value;
    editSyllable({ height });
}

function setDirection(btn) {
    const direction = btn.dataset.value;
    editSyllable({ direction });
}

function toggleAccent(btn) {
    const shouldAdd = !btn.classList.contains("active");
    editSyllable({ add_accent: shouldAdd });
}

async function resetSyllable() {
    if (selectedSyllableIndex < 0) return;

    try {
        const response = await fetch(`${API_BASE}/syllable/${selectedSyllableIndex}/reset`, {
            method: "POST",
        });

        if (!response.ok) throw new Error("Reset failed");

        await loadSyllables();
        selectSyllable(selectedSyllableIndex);

    } catch (error) {
        showStatus("synthesis-status", `Error: ${error.message}`, "error");
    }
}

function nextSyllable() {
    if (selectedSyllableIndex < syllables.length - 1) {
        selectSyllable(selectedSyllableIndex + 1);
    }
}

function prevSyllable() {
    if (selectedSyllableIndex > 0) {
        selectSyllable(selectedSyllableIndex - 1);
    }
}

// ── Synthesis ────────────────────────────────────────────────────────────

async function synthesize() {
    if (!projectLoaded) {
        showStatus("synthesis-status", "No project loaded", "error");
        return;
    }

    const f0Floor = parseFloat(document.getElementById("f0-floor").value) || null;
    const f0Ceiling = parseFloat(document.getElementById("f0-ceiling").value) || null;

    try {
        showStatus("synthesis-status", "Synthesizing...", "info");

        const response = await fetch(`${API_BASE}/synthesize`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                f0_floor: f0Floor,
                f0_ceiling: f0Ceiling,
            }),
        });

        if (!response.ok) throw new Error("Synthesis failed");

        const data = await response.json();
        const msg = `Synthesis complete: ${data.modified_count} modified syllables, ` +
                    `F0 range: ${data.f0_range.floor.toFixed(1)}-${data.f0_range.ceiling.toFixed(1)} Hz`;
        showStatus("synthesis-status", msg, "success");

    } catch (error) {
        showStatus("synthesis-status", `Error: ${error.message}`, "error");
    }
}

async function exportTextGrid() {
    if (!projectLoaded) {
        showStatus("synthesis-status", "No project loaded", "error");
        return;
    }

    try {
        showStatus("synthesis-status", "Exporting...", "info");

        const response = await fetch(`${API_BASE}/export`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ output_filename: "prosody_resynthesized.TextGrid" }),
        });

        if (!response.ok) throw new Error("Export failed");

        const data = await response.json();
        showStatus("synthesis-status", `Exported to: ${data.output_path}`, "success");

        // Optional: trigger download
        setTimeout(() => {
            window.location.href = `${API_BASE}/export/download`;
        }, 500);

    } catch (error) {
        showStatus("synthesis-status", `Error: ${error.message}`, "error");
    }
}

// ── Summary ──────────────────────────────────────────────────────────────

function updateSummary() {
    if (!syllables.length) return;

    const modified = syllables.filter(s => s.is_modified).length;
    const total = syllables.length;

    let text = `Summary:\n${modified}/${total} syllables modified\n\nModified:\n`;

    syllables.forEach((syl, idx) => {
        if (syl.is_modified) {
            text += `[${idx}] ${syl.text}: ${syl.original_symbol} → ${syl.current_symbol}\n`;
        }
    });

    document.getElementById("summary").textContent = text;
}

// ── UI Helpers ───────────────────────────────────────────────────────────

function showStatus(elementId, message, type) {
    const el = document.getElementById(elementId);
    el.textContent = message;
    el.className = `status show ${type}`;

    if (type !== "error") {
        setTimeout(() => {
            el.classList.remove("show");
        }, 5000);
    }
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

// ── Init ─────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
    // Check server health
    fetch(`${API_BASE}/health`)
        .then(r => r.json())
        .then(d => {
            if (!d.status === "ok") {
                showStatus("project-status", "Warning: Server may be offline", "error");
            }
        })
        .catch(() => {
            showStatus("project-status", "Warning: Cannot reach server", "error");
        });
});
