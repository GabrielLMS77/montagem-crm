(() => {
  const q = (selector) => document.querySelector(selector);
  const app = document.createElement("div");
  app.id = "agenda-app";
  app.innerHTML = '<div id="auth-screen"></div>';
  document.body.append(app);
  const state = { user: null, staff: [], items: [], focus: new Date(), filter: "all" };
  const localDate = (date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
  const plusDays = (date, count) => { const copy = new Date(date); copy.setDate(copy.getDate() + count); return copy; };
  const monday = (date) => { const copy = new Date(date); copy.setHours(0, 0, 0, 0); copy.setDate(copy.getDate() - ((copy.getDay() + 6) % 7)); return copy; };
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
  const request = async (url, options = {}) => {
    const response = await fetch(url, { credentials: "same-origin", ...options, headers: { ...(options.body ? { "Content-Type": "application/json" } : {}), ...(options.headers || {}) } });
    if (response.status === 204) return null;
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || "Não foi possível concluir a operação.");
    return data;
  };
  const styles = document.createElement("style");
  styles.textContent = `
    #agenda-app{font:inherit;color:#202720}#auth-screen{position:fixed;inset:0;z-index:9999;display:grid;place-items:center;padding:20px;background:#f5f7f4}.auth-card{width:min(440px,100%);padding:30px;background:#fff;border:1px solid #e6ebe6;border-radius:16px;box-shadow:0 16px 48px #173e3418}.auth-card h1{margin:0 0 8px;font-size:24px}.auth-card p{color:#718078}.auth-card form{display:grid;gap:13px}.auth-card label,.agenda-form label{font-size:13px;color:#59665e}.auth-card input,.agenda-form input,.agenda-form select,.agenda-form textarea{display:block;width:100%;margin-top:5px;padding:10px;border:1px solid #dce3dc;border-radius:8px;font:inherit}.auth-error,.agenda-message{padding:10px;background:#fbe8e5;color:#92483f;border-radius:8px;font-size:13px}.auth-error:empty,.agenda-message:empty{display:none}.auth-submit{width:100%;margin-top:4px}.auth-note{font-size:12px;line-height:1.5}.agenda-layout{display:grid;grid-template-columns:minmax(0,1fr);gap:18px;margin-top:18px}.agenda-tools{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.agenda-tools select,.agenda-tools input{padding:9px;border:1px solid #dce3dc;border-radius:8px;background:white;font:inherit}.agenda-week{display:grid;grid-template-columns:52px repeat(7,minmax(110px,1fr));overflow:auto;border:1px solid #e6ebe6;border-radius:12px;background:white}.agenda-dayhead,.agenda-time,.agenda-slot{min-height:54px;border-bottom:1px solid #edf0ed;border-right:1px solid #edf0ed;padding:6px}.agenda-dayhead{position:sticky;top:0;background:#f7faf7;z-index:1;text-align:center;font-size:12px;font-weight:700}.agenda-dayhead.today{color:#236846}.agenda-time{font-size:11px;color:#78837c;text-align:right}.agenda-slot{min-width:110px}.agenda-slot.dragover{background:#e9f1eb}.agenda-event{display:block;width:100%;margin:2px 0;padding:5px 6px;border:0;border-left:3px solid #236846;border-radius:5px;background:#e9f1eb;color:#1d4d34;text-align:left;font-size:11px;cursor:grab}.agenda-event[draggable=true]:active{cursor:grabbing}.agenda-event.done{border-color:#8ea998;background:#edf1ee;color:#66736a}.agenda-checklist{display:grid;gap:9px}.agenda-item{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px;background:white;border:1px solid #e6ebe6;border-radius:11px}.agenda-item p{margin:3px 0;color:#718078;font-size:13px}.agenda-item .btn{padding:8px 10px}.agenda-item.done{opacity:.65}.agenda-form{display:grid;grid-template-columns:1fr 1fr;gap:12px}.agenda-form .full{grid-column:1/-1}.agenda-form textarea{min-height:65px}.agenda-dialog{width:min(560px,calc(100% - 24px));border:1px solid #e6ebe6;border-radius:14px;padding:22px}.agenda-dialog::backdrop{background:#15251dcc}.agenda-dialog h2{margin:0 0 16px}.agenda-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:16px}.admin-tools{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}.staff-list{display:grid;gap:8px}.staff-row{display:flex;justify-content:space-between;align-items:center;padding:10px;border-bottom:1px solid #edf0ed}.session-actions{display:flex;justify-content:flex-end;margin-bottom:8px}.session-actions button{border:0;background:transparent;color:#236846;cursor:pointer}.role-chip{display:inline-block;padding:4px 8px;border-radius:20px;background:#e9f1eb;color:#25543a;font-size:11px}
    @media(max-width:760px){.agenda-week{grid-template-columns:42px repeat(7,minmax(95px,1fr))}.agenda-item{align-items:flex-start;flex-direction:column}.agenda-form{grid-template-columns:1fr}.agenda-form .full{grid-column:auto}}
  `;
  document.head.append(styles);
  const rootLayout = document.querySelector(".layout");
  rootLayout.style.visibility = "hidden";
  const nav = document.querySelector(".nav");
  nav.insertAdjacentHTML("beforeend", '<button data-view="agenda">Agenda</button>');
  const main = document.querySelector("main.main");
  main.insertAdjacentHTML("beforeend", `<section id="agenda" class="view"><div class="session-actions"><span id="session-label" class="muted"></span><button id="logout-button">Sair</button></div><div class="head"><div><h2>Agenda de atendimentos</h2><p>Calendário semanal e lista de execução do dia.</p></div><button class="btn" id="new-intake">Novo formulário</button></div><div class="panel"><div class="agenda-tools"><button class="btn light" id="week-prev">‹ Semana anterior</button><button class="btn light" id="week-current">Hoje</button><button class="btn light" id="week-next">Próxima semana ›</button><input id="agenda-date" type="date"><label id="employee-filter-label">Funcionário <select id="employee-filter"></select></label><button class="btn" id="load-day">Carregar agenda do dia</button><button class="btn light" id="new-employee">Gerenciar funcionários</button></div><p id="agenda-message" class="agenda-message"></p></div><div class="head"><div><h2>Calendário</h2><p>Arraste um atendimento para outro dia e horário.</p></div></div><div class="agenda-week" id="agenda-calendar"></div><div class="head"><div><h2>Lista do dia</h2><p id="day-heading"></p></div></div><div id="agenda-list" class="agenda-checklist"></div></section>`);
  document.querySelector('[data-view="agenda"]').addEventListener("click", () => openAgenda());

  function authForm(setup = false) {
    const screen = q("#auth-screen");
    let recovery = false;
    screen.innerHTML = `<div class="auth-card"><p class="eyebrow">Clinicaflow · acesso seguro</p><h1>${setup ? "Configurar administrador" : "Entrar no CRM"}</h1><p>${setup ? "Crie a conta principal. Esta configuração só pode ser feita uma vez neste computador." : "Entre com seu e-mail e senha para abrir sua área de trabalho."}</p><form id="auth-form">${setup ? '<label>Nome do administrador<input name="name" required minlength="2" autocomplete="name"></label>' : ""}<label>E-mail<input name="email" type="email" required autocomplete="username"></label><label>Senha<input name="password" type="password" required minlength="${setup ? 12 : 1}" autocomplete="${setup ? "new-password" : "current-password"}"></label>${setup ? '<p class="auth-note">Use uma senha exclusiva com pelo menos 12 caracteres. Ela será armazenada como hash no banco.</p>' : ""}<div class="auth-error" id="auth-error"></div><button class="btn auth-submit">${setup ? "Criar administrador" : "Entrar"}</button></form></div>`;
    q("#auth-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const values = Object.fromEntries(new FormData(event.currentTarget));
      try {
        const endpoint = setup ? "/auth/bootstrap" : recovery ? "/auth/recover-admin" : "/auth/login";
        await request(endpoint, { method: "POST", body: JSON.stringify(values) });
        await startApp();
      } catch (error) { q("#auth-error").textContent = error.message; }
    });
    if (!setup) {
      const recoveryButton = document.createElement("button");
      recoveryButton.type = "button";
      recoveryButton.textContent = "Esqueci o acesso do administrador";
      recoveryButton.style.cssText = "display:block;margin:12px auto 0;border:0;background:none;color:#236846;text-decoration:underline;cursor:pointer";
      screen.querySelector(".auth-card").append(recoveryButton);
      recoveryButton.onclick = () => {
        if (recovery) return authForm(false);
        recovery = true;
        const card = screen.querySelector(".auth-card");
        card.querySelector("h1").textContent = "Recuperar acesso do administrador";
        card.querySelectorAll("p")[1].textContent = "Defina um novo nome, e-mail e senha. Atendimentos, clientes e vendas serão preservados.";
        const form = q("#auth-form");
        const name = document.createElement("label");
        name.innerHTML = 'Nome do administrador<input name="name" required minlength="2" autocomplete="name">';
        form.insertBefore(name, form.firstChild);
        const passwordLabel = form.querySelector('input[name="password"]').parentElement;
        passwordLabel.firstChild.textContent = "Nova senha";
        passwordLabel.querySelector("input").minLength = 12;
        passwordLabel.querySelector("input").autocomplete = "new-password";
        form.querySelector(".auth-submit").textContent = "Redefinir acesso";
        recoveryButton.textContent = "Voltar para login";
      };
    }
  }

  async function startApp() {
    const session = await request("/auth/status");
    if (!session.authenticated) { authForm(session.needs_setup); return; }
    state.user = session.user;
    q("#auth-screen").style.display = "none";
    rootLayout.style.visibility = "visible";
    const admin = state.user.role === "admin";
    window.crmAdminReady = admin;
    if (admin) window.fetch = window.__crmRealFetch;
    document.querySelectorAll(".nav button").forEach(button => {
      if (button.dataset.view !== "agenda" && !admin) button.hidden = true;
    });
    q("#session-label").textContent = `${state.user.name} · ${admin ? "Administrador" : "Funcionário"}`;
    q("#employee-filter-label").hidden = !admin;
    q("#new-employee").hidden = !admin;
    if (admin) {
      state.staff = await request("/agenda/employees");
      q("#employee-filter").innerHTML = '<option value="all">Todos os funcionários</option>' + state.staff.filter(e => e.role === "employee").map(e => `<option value="${e.id}">${esc(e.name)}</option>`).join("");
    } else {
      state.staff = [{ id: state.user.id, name: state.user.name, role: "employee" }];
      q("#employee-filter").innerHTML = `<option value="${state.user.id}">${esc(state.user.name)}</option>`;
    }
    q("#agenda-date").value = localDate(state.focus);
    bindAgendaControls();
    await loadAppointments();
    if (admin) { await load(); }
    openAgenda();
  }

  function bindAgendaControls() {
    q("#logout-button").onclick = async () => { await request("/auth/logout", { method: "POST" }); location.reload(); };
    q("#agenda-date").onchange = async event => { state.focus = new Date(`${event.target.value}T12:00:00`); await loadAppointments(); };
    q("#employee-filter").onchange = async event => { state.filter = event.target.value; await loadAppointments(); };
    q("#week-prev").onclick = async () => { state.focus = plusDays(state.focus, -7); syncAndLoad(); };
    q("#week-next").onclick = async () => { state.focus = plusDays(state.focus, 7); syncAndLoad(); };
    q("#week-current").onclick = async () => { state.focus = new Date(); syncAndLoad(); };
    q("#load-day").onclick = async () => {
      try {
        const employee = state.user.role === "employee" ? state.user.id : state.filter;
        if (employee === "all") throw new Error("Escolha um funcionário para carregar a agenda em lote.");
        const result = await request(`/agenda/load-day?date=${q("#agenda-date").value}&employee_id=${employee}`, { method: "POST" });
        message(`${result.created} atendimento(s) carregado(s). Pedidos já carregados não são duplicados.`);
        await loadAppointments();
      } catch (error) { message(error.message, true); }
    };
    q("#new-intake").onclick = showIntakeForm;
    q("#new-employee").onclick = showEmployeeManager;
  }

  async function syncAndLoad() { q("#agenda-date").value = localDate(state.focus); await loadAppointments(); }
  function message(text, error = false) { const el = q("#agenda-message"); el.textContent = text; el.style.background = error ? "#fbe8e5" : "#e9f1eb"; el.style.color = error ? "#92483f" : "#25543a"; }
  function openAgenda() {
    if (!state.user) return;
    if (typeof navigate === "function") navigate("agenda");
    q("#page-title").textContent = state.user.role === "admin" ? "Painel de trabalho" : "Minha agenda";
  }

  async function loadAppointments() {
    if (!state.user) return;
    const weekStart = monday(state.focus), weekEnd = plusDays(weekStart, 6);
    const selected = state.user.role === "employee" ? state.user.id : state.filter;
    const params = new URLSearchParams({ start: localDate(weekStart), end: localDate(weekEnd) });
    if (selected !== "all") params.set("employee_id", selected);
    try {
      state.items = await request(`/agenda/appointments?${params}`);
      renderCalendar(weekStart);
      renderDayList();
    } catch (error) { message(error.message, true); }
  }

  function renderCalendar(weekStart) {
    const calendar = q("#agenda-calendar");
    const days = Array.from({ length: 7 }, (_, index) => plusDays(weekStart, index));
    const weekDays = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"];
    let html = '<div class="agenda-dayhead"></div>' + days.map((day, index) => `<div class="agenda-dayhead ${localDate(day) === localDate(new Date()) ? "today" : ""}">${weekDays[index]}<br>${day.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" })}</div>`).join("");
    for (let hour = 7; hour <= 19; hour++) {
      html += `<div class="agenda-time">${String(hour).padStart(2, "0")}:00</div>`;
      for (const day of days) {
        const date = localDate(day);
        const events = state.items.filter(item => item.starts_at.slice(0, 10) === date && Number(item.starts_at.slice(11, 13)) === hour);
        html += `<div class="agenda-slot" data-date="${date}" data-hour="${hour}">${events.map(event => `<button class="agenda-event ${event.status === "completed" ? "done" : ""}" draggable="${event.status === "scheduled"}" data-event-id="${event.id}" title="${esc(event.service)} · ${esc(event.employee_name)}">${event.starts_at.slice(11, 16)} ${esc(event.customer_name)}${state.user.role === "admin" && state.filter === "all" ? `<br><span>${esc(event.employee_name)}</span>` : ""}</button>`).join("")}</div>`;
      }
    }
    calendar.innerHTML = html;
    calendar.querySelectorAll(".agenda-event[draggable=true]").forEach(button => {
      button.addEventListener("dragstart", event => { event.dataTransfer.setData("text/plain", button.dataset.eventId); });
    });
    calendar.querySelectorAll(".agenda-slot").forEach(slot => {
      slot.addEventListener("dragover", event => { event.preventDefault(); slot.classList.add("dragover"); });
      slot.addEventListener("dragleave", () => slot.classList.remove("dragover"));
      slot.addEventListener("drop", async event => {
        event.preventDefault(); slot.classList.remove("dragover");
        const id = event.dataTransfer.getData("text/plain");
        try {
          await request(`/agenda/appointments/${id}`, { method: "PATCH", body: JSON.stringify({ starts_at: `${slot.dataset.date}T${String(slot.dataset.hour).padStart(2, "0")}:00` }) });
          await loadAppointments();
        } catch (error) { message(error.message, true); }
      });
    });
  }

  function renderDayList() {
    const key = q("#agenda-date").value;
    q("#day-heading").textContent = new Date(`${key}T12:00:00`).toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
    const todayItems = state.items.filter(item => item.starts_at.slice(0, 10) === key).sort((a, b) => a.starts_at.localeCompare(b.starts_at));
    q("#agenda-list").innerHTML = todayItems.length ? todayItems.map(item => `<article class="agenda-item ${item.status === "completed" ? "done" : ""}"><div><strong>${item.starts_at.slice(11, 16)} · ${esc(item.customer_name)}</strong><p>${esc(item.service)}${item.customer_phone ? ` · ${esc(item.customer_phone)}` : ""}${state.user.role === "admin" && state.filter === "all" ? ` · ${esc(item.employee_name)}` : ""}</p><span class="role-chip">${item.status === "completed" ? "Concluído" : item.status === "cancelled" ? "Cancelado" : item.status === "no_show" ? "Não compareceu" : "Agendado"}</span></div>${item.status === "scheduled" ? `<div class="row-actions"><button class="btn light" data-complete="${item.id}">Concluir</button><button class="btn" data-reschedule="${item.id}">Reagendar</button></div>` : ""}</article>`).join("") : '<div class="panel muted">Nenhum atendimento para este dia. Use “Carregar agenda do dia” para importar os formulários pendentes.</div>';
    q("#agenda-list").querySelectorAll("[data-complete]").forEach(button => button.onclick = async () => {
      try { await request(`/agenda/appointments/${button.dataset.complete}`, { method: "PATCH", body: JSON.stringify({ status: "completed" }) }); await loadAppointments(); }
      catch (error) { message(error.message, true); }
    });
    q("#agenda-list").querySelectorAll("[data-reschedule]").forEach(button => button.onclick = () => showReschedule(button.dataset.reschedule));
  }

  function showDialog(title, content, submitText, onSubmit) {
    const dialog = document.createElement("dialog"); dialog.className = "agenda-dialog";
    dialog.innerHTML = `<form><h2>${title}</h2>${content}<p class="agenda-message"></p><div class="agenda-actions"><button type="button" class="btn light" data-close>Cancelar</button><button class="btn">${submitText}</button></div></form>`;
    document.body.append(dialog); dialog.showModal();
    dialog.querySelector("[data-close]").onclick = () => dialog.close();
    dialog.addEventListener("close", () => dialog.remove());
    dialog.querySelector("form").addEventListener("submit", async event => {
      event.preventDefault();
      try { await onSubmit(Object.fromEntries(new FormData(event.currentTarget))); dialog.close(); await loadAppointments(); }
      catch (error) { const note = dialog.querySelector(".agenda-message"); note.textContent = error.message; note.style.display = "block"; }
    });
    return dialog;
  }

  function showReschedule(id) {
    const item = state.items.find(record => record.id === Number(id));
    const next = new Date(item.starts_at); next.setHours(next.getHours() + 1);
    const value = `${localDate(next)}T${String(next.getHours()).padStart(2, "0")}:${String(next.getMinutes()).padStart(2, "0")}`;
    showDialog("Reagendar atendimento", `<p>Escolha o novo dia e horário. O atendimento sairá da lista atual e aparecerá na data escolhida.</p><label>Nova data e horário<input name="starts_at" type="datetime-local" value="${value}" required></label>`, "Salvar novo horário", async data => request(`/agenda/appointments/${id}`, { method: "PATCH", body: JSON.stringify({ starts_at: data.starts_at }) }));
  }

  function showIntakeForm() {
    const admin = state.user.role === "admin";
    const employees = state.staff.filter(person => person.role === "employee");
    if (admin && !employees.length) { message("Cadastre um funcionário antes de distribuir formulários.", true); return; }
    const date = q("#agenda-date").value || localDate(new Date());
    showDialog("Formulário interno de atendimento", `<div class="agenda-form"><label class="full">Nome do cliente<input name="customer_name" required minlength="2"></label><label>CPF/CNPJ (opcional)<input name="customer_document" maxlength="14"></label><label>Telefone<input name="customer_phone" maxlength="20"></label><label class="full">E-mail<input name="customer_email" type="email"></label>${admin ? `<label class="full">Funcionário responsável<select name="employee_id" required>${employees.map(person => `<option value="${person.id}">${esc(person.name)}</option>`).join("")}</select></label>` : ""}<label class="full">Serviço<input name="service" required maxlength="200" placeholder="Ex.: Consulta clínica"></label><label class="full">Data e horário solicitado<input name="requested_at" type="datetime-local" value="${date}T09:00" required></label><label class="full">Observações operacionais<textarea name="notes" maxlength="1000"></textarea></label></div><p>Evite incluir diagnósticos ou informações clínicas nas observações.</p>`, "Salvar formulário", async data => {
      if (data.employee_id) data.employee_id = Number(data.employee_id);
      for (const key of ["customer_document", "customer_phone", "customer_email", "notes"]) if (!data[key]) data[key] = null;
      await request("/agenda/intakes", { method: "POST", body: JSON.stringify(data) });
      message("Formulário salvo. Carregue a agenda do funcionário e da data para criar o atendimento.");
    });
  }

  async function showEmployeeManager() {
    const allEmployees = await request("/auth/employees");
    const dialog = showDialog("Funcionários", `<div class="staff-list" id="staff-list">${allEmployees.map(person => `<div class="staff-row"><span>${esc(person.name)} · ${esc(person.email)} ${person.active ? "" : "(inativo)"}</span><button type="button" class="btn light" data-toggle-user="${person.id}" data-active="${person.active}">${person.active ? "Desativar" : "Ativar"}</button></div>`).join("") || "Nenhum funcionário cadastrado."}</div><hr><div class="agenda-form"><label>Nome<input name="name" required minlength="2"></label><label>E-mail<input name="email" type="email" required></label><label class="full">Senha inicial (mínimo 12 caracteres)<input name="password" type="password" required minlength="12" autocomplete="new-password"></label></div>`, "Criar funcionário", async data => {
      await request("/auth/employees", { method: "POST", body: JSON.stringify(data) });
      state.staff = await request("/agenda/employees");
      q("#employee-filter").innerHTML = '<option value="all">Todos os funcionários</option>' + state.staff.filter(e => e.role === "employee").map(e => `<option value="${e.id}">${esc(e.name)}</option>`).join("");
    });
    dialog.querySelectorAll("[data-toggle-user]").forEach(button => button.onclick = async () => {
      try {
        await request(`/auth/employees/${button.dataset.toggleUser}`, { method: "PATCH", body: JSON.stringify({ active: button.dataset.active !== "true" }) });
        state.staff = await request("/agenda/employees"); dialog.close(); showEmployeeManager();
      } catch (error) { message(error.message, true); }
    });
  }

  startApp().catch(error => { q("#auth-screen").innerHTML = `<div class="auth-card"><h1>Não foi possível abrir o CRM</h1><p>${esc(error.message)}</p></div>`; });
})();
