const searchInput = document.getElementById("guildSearch");
const filterSelect = document.getElementById("guildFilter");
const clearBtn = document.getElementById("clearFilterBtn");
const cards = Array.from(document.querySelectorAll(".guild-card"));
const emptyState = document.getElementById("emptyState");
const inviteHubSelect = document.getElementById("inviteHubSelect");
const copyInviteHubBtn = document.getElementById("copyInviteHubBtn");

function applyGuildFilters() {
  const term = (searchInput?.value || "").trim().toLowerCase();
  const mode = filterSelect?.value || "all";
  let visibleCount = 0;

  for (const card of cards) {
    const name = card.dataset.guildName || "";
    const gid = card.dataset.guildId || "";
    const hasNotify = card.dataset.hasNotify === "1";
    const exemptOn = card.dataset.exemptGuild === "1";

    let visible = !term || name.includes(term) || gid.includes(term);
    if (visible && mode === "has-notify") visible = hasNotify;
    if (visible && mode === "exempt-on") visible = exemptOn;
    if (visible && mode === "need-setup") visible = !hasNotify;

    card.style.display = visible ? "block" : "none";
    if (visible) visibleCount += 1;
  }
  if (emptyState) emptyState.style.display = visibleCount ? "none" : "block";
}

function copyInviteHubId() {
  if (!inviteHubSelect) return;
  const value = inviteHubSelect.value;
  if (!value) return alert("กรุณาเลือกชื่อห้องก่อนคัดลอก ID");
  navigator.clipboard.writeText(value)
    .then(() => alert("คัดลอก Invite Hub Channel ID แล้ว: " + value))
    .catch(() => alert("คัดลอกไม่สำเร็จ ลองคัดลอกด้วยตนเอง: " + value));
}

function updateSelectedCount(card) {
  const checks = Array.from(card.querySelectorAll('input[name="exempt_channel_ids"]'));
  const selected = checks.filter((el) => el.checked).length;
  const countEl = card.querySelector(".selected-count");
  if (countEl) countEl.textContent = String(selected);
}

for (const card of cards) {
  const checks = Array.from(card.querySelectorAll('input[name="exempt_channel_ids"]'));
  const selectAllBtn = card.querySelector(".select-all-btn");
  const clearAllBtn = card.querySelector(".clear-all-btn");

  if (selectAllBtn) {
    selectAllBtn.addEventListener("click", () => {
      for (const check of checks) check.checked = true;
      updateSelectedCount(card);
    });
  }
  if (clearAllBtn) {
    clearAllBtn.addEventListener("click", () => {
      for (const check of checks) check.checked = false;
      updateSelectedCount(card);
    });
  }
  for (const check of checks) {
    check.addEventListener("change", () => updateSelectedCount(card));
  }
  updateSelectedCount(card);
}

searchInput?.addEventListener("input", applyGuildFilters);
filterSelect?.addEventListener("change", applyGuildFilters);
clearBtn?.addEventListener("click", () => {
  if (searchInput) searchInput.value = "";
  if (filterSelect) filterSelect.value = "all";
  applyGuildFilters();
});
copyInviteHubBtn?.addEventListener("click", copyInviteHubId);
applyGuildFilters();
