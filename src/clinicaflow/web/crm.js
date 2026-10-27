(() => {
  const $ = (selector) => document.querySelector(selector);
  const currency = (value) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value || 0));
  const customerBody = $("#customer-rows");
  const saleBody = $("#sale-rows");
  customerBody.closest("table").querySelector("thead tr").insertAdjacentHTML("beforeend", "<th>Ações</th>");
  saleBody.closest("table").querySelector("thead tr").insertAdjacentHTML("beforeend", "<th>Ações</th>");

  const style = document.createElement("style");
  style.textContent = ".row-actions{display:flex;gap:6px;white-space:nowrap}.btn.small{padding:7px 9px;font-size:12px}.btn.danger{background:#fbe8e5;color:#9b382e}.btn.danger:hover{background:#f5d7d2}.cards{grid-template-columns:repeat(4,minmax(0,1fr))}@media(max-width:760px){.cards{grid-template-columns:repeat(2,minmax(0,1fr))}}";
  document.head.append(style);

  const dialog = document.createElement("dialog");
  dialog.id = "record-editor";
  dialog.innerHTML = '<form id="record-editor-form"><h2 id="editor-title">Editar registro</h2><div id="editor-fields" class="formgrid"></div><div id="editor-error" class="error"></div><div class="actions"><button type="button" class="btn light" id="editor-cancel">Cancelar</button><button class="btn">Salvar alterações</button></div></form>';
  document.body.append(dialog);
  const form = $("#record-editor-form");
  let editing = null;

  function field(label, name, value, type = "text", extra = "") {
    const safe = String(value ?? "").replaceAll("&", "&amp;").replaceAll('"', "&quot;").replaceAll("<", "&lt;");
    return `<div class="field ${extra}"><label for="edit-${name}">${label}</label><input id="edit-${name}" name="${name}" type="${type}" value="${safe}" ${name === "amount" ? 'min="0.01" step="0.01"' : ""}></div>`;
  }

  function openEditor(kind, record) {
    editing = { kind, id: record.id };
    const fields = $("#editor-fields");
    if (kind === "customer") {
      $("#editor-title").textContent = "Editar cliente";
      fields.innerHTML = field("Nome completo", "name", record.name, "text", "full") + field("CPF ou CNPJ", "document", record.document) + field("Telefone", "phone", record.phone) + field("E-mail", "email", record.email, "email", "full");
      ["name"].forEach((name) => $("#edit-" + name).required = true);
    } else {
      $("#editor-title").textContent = "Editar venda";
      fields.innerHTML = `<div class="field full"><label for="edit-customer_id">Cliente</label><select id="edit-customer_id" name="customer_id">${state.customers.map(c => `<option value="${c.id}" ${c.id === record.customer_id ? "selected" : ""}>${c.name.replaceAll("&", "&amp;").replaceAll("<", "&lt;")}</option>`).join("")}</select></div>` + field("Serviço", "description", record.description, "text", "full") + field("Valor (R$)", "amount", record.amount, "number") + field("Data", "sale_date", record.sale_date, "date") + '<div class="field"><label for="edit-status">Status</label><select id="edit-status" name="status"><option value="pending">Pendente</option><option value="paid">Paga</option><option value="cancelled">Cancelada</option></select></div>' + `<div class="field full"><label for="edit-notes">Observações</label><textarea id="edit-notes" name="notes">${String(record.notes ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;")}</textarea></div>`;
      $("#edit-status").value = record.status;
      $("#edit-description").required = true;
      $("#edit-amount").required = true;
    }
    $("#editor-error").classList.remove("show");
    dialog.showModal();
  }

  function decorateRows() {
    customerBody.querySelectorAll("tr").forEach((row, index) => {
      const customer = state.customers[index];
      if (!customer || row.querySelector(".row-actions")) return;
      const cell = row.insertCell();
      cell.className = "row-actions";
      cell.innerHTML = '<button class="btn light small" data-action="edit">Editar</button><button class="btn danger small" data-action="delete">Remover</button>';
      cell.dataset.kind = "customer";
      cell.dataset.id = customer.id;
    });
    saleBody.querySelectorAll("tr").forEach((row, index) => {
      const sale = state.sales[index];
      if (!sale || row.querySelector(".row-actions")) return;
      const cell = row.insertCell();
      cell.className = "row-actions";
      cell.innerHTML = '<button class="btn light small" data-action="edit">Editar</button><button class="btn danger small" data-action="delete">Remover</button>';
      cell.dataset.kind = "sale";
      cell.dataset.id = sale.id;
    });
  }

  function updateOverview() {
    const cards = $("#dashboard .cards");
    if (!cards || !state.customers || !state.sales) return;
    const paid = state.sales.filter(s => s.status === "paid").reduce((sum, s) => sum + Number(s.amount), 0);
    const pending = state.sales.filter(s => s.status === "pending").length;
    cards.innerHTML = `<article class="card"><p>Clientes cadastrados</p><strong>${state.customers.length}</strong></article><article class="card"><p>Vendas registradas</p><strong>${state.sales.length}</strong></article><article class="card"><p>Vendas pendentes</p><strong>${pending}</strong></article><article class="card"><p>Total recebido</p><strong>${currency(paid)}</strong></article>`;
  }

  const observer = new MutationObserver(() => { decorateRows(); updateOverview(); });
  observer.observe(customerBody, { childList: true });
  observer.observe(saleBody, { childList: true });
  decorateRows();

  document.body.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-action]");
    if (!button) return;
    const cell = button.closest(".row-actions");
    const kind = cell.dataset.kind;
    const id = Number(cell.dataset.id);
    const collection = kind === "customer" ? state.customers : state.sales;
    const record = collection.find(item => item.id === id);
    if (!record) return;
    if (button.dataset.action === "edit") return openEditor(kind, record);
    const subject = kind === "customer" ? `o cliente ${record.name}` : `a venda “${record.description}”`;
    if (!window.confirm(`Remover ${subject}? Esta ação não pode ser desfeita.`)) return;
    try {
      const response = await fetch(`/${kind === "customer" ? "customers" : "sales"}/${id}`, { method: "DELETE" });
      const result = response.status === 204 ? null : await response.json();
      if (!response.ok) throw new Error(result?.detail || "Não foi possível remover o registro.");
      await load();
    } catch (error) {
      window.alert(error.message);
    }
  });

  $("#editor-cancel").addEventListener("click", () => dialog.close());
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = Object.fromEntries(new FormData(form));
    if (editing.kind === "customer") {
      for (const key of ["document", "phone", "email"]) if (!payload[key]) payload[key] = null;
    } else {
      payload.customer_id = Number(payload.customer_id);
      payload.amount = Number(payload.amount);
      if (!payload.notes) payload.notes = null;
    }
    try {
      const endpoint = editing.kind === "customer" ? "customers" : "sales";
      const response = await fetch(`/${endpoint}/${editing.id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Confira os dados informados.");
      dialog.close();
      await load();
    } catch (error) {
      const message = $("#editor-error");
      message.textContent = error.message;
      message.classList.add("show");
    }
  });
})();
