const GIORNI = ["lunedi", "martedi", "mercoledi", "giovedi", "venerdi", "sabato", "domenica"];
const GIORNI_BREVI = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"];
const MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
              "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"];
const STATI = ["Pianificata", "Confermata", "Svolta", "Rinviata", "Annullata"];
const STATI_MAIL = {
  inviata: "INVIATA",
  invio_disattivato: "INVIO_DISATTIVATO",
  errore: "ERRORE",
  senza_destinatari: "SENZA_DESTINATARI",
};
const MODALITA = ["Spiegazione", "Affiancamento", "Autoapprendimento"];
const MOTIVI = ["Nuova funzione", "Cambio funzione", "Addestramento", "Formazione"];
const COLORI = {
  "Svolta": "#C6EFCE", "Completata": "#C6EFCE", "In corso": "#BDD7EE",
  "Rinviata": "#FCE4D6", "Da pianificare": "#FCE4D6", "Annullata": "#F2DCDB",
  "N.A.": "#D9D9D9", "Pianificata": "#FFFFFF", "Confermata": "#FFFFFF",
};
const ORA_PRIMA = 8, ORA_ULTIMA = 19, ALTEZZA_ORA = 46;

// Stessa palette del backend (regole.PALETTE_AREE): serve solo a proporre un
// colore libero quando si crea una nuova area.
const PALETTE_AREE = [
  "#F5C9C9", "#F5DCC0", "#F0EEBE", "#DBEEBE", "#C6EFCE", "#C0EFD6",
  "#BEEFEF", "#C0DCF5", "#C9C9F5", "#DCC0F5", "#F0BEEF", "#F5C0DC",
];


/* Icone disegnate qui invece che prese da una libreria: sono una decina di
   forme geometriche, e cosi' non c'e' un pacchetto in piu' da aggiornare. */
const FORME = {
  agenda: '<line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><circle cx="3.5" cy="6" r="1.2"/><circle cx="3.5" cy="12" r="1.2"/><circle cx="3.5" cy="18" r="1.2"/>',
  settimana: '<rect x="3" y="4" width="18" height="17" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="9" x2="9" y2="21"/><line x1="15" y1="9" x2="15" y2="21"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="16" y1="2" x2="16" y2="6"/>',
  piano: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="13" y2="17"/>',
  moduli: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  persone: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
  mail: '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m2 7 10 6 10-6"/>',
  piu: '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',
  stampa: '<path d="M6 9V2h12v7"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8" rx="1"/>',
  sposta: '<path d="M8 3 4 7l4 4"/><path d="M4 7h16"/><path d="m16 21 4-4-4-4"/><path d="M20 17H4"/>',
  fatto: '<path d="M20 6 9 17l-5-5"/>',
  annulla: '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
  avviso: '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><line x1="12" y1="9" x2="12" y2="13"/><circle cx="12" cy="17" r=".6" fill="currentColor"/>',
};

FORME.sole = '<circle cx="12" cy="12" r="4"/><line x1="12" y1="2" x2="12" y2="4.2"/><line x1="12" y1="19.8" x2="12" y2="22"/><line x1="4.2" y1="4.2" x2="5.8" y2="5.8"/><line x1="18.2" y1="18.2" x2="19.8" y2="19.8"/><line x1="2" y1="12" x2="4.2" y2="12"/><line x1="19.8" y1="12" x2="22" y2="12"/><line x1="4.2" y1="19.8" x2="5.8" y2="18.2"/><line x1="18.2" y1="5.8" x2="19.8" y2="4.2"/>';
FORME.luna = '<path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z"/>';

const icona = (nome) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
  stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"
  aria-hidden="true">${FORME[nome] ?? ""}</svg>`;

let stato = {}, piano = null, persone = [], catalogo = [];
let registroMail = [];        // ultimo registro caricato, per rileggere una notifica
let listaAree = [];           // [{nome, colore, ordine}]
let aree = {};                // nome -> colore, per lettura rapida
let vistaCorrente = "agenda";
let lunediCorrente = inizioSettimana(new Date());

const COLORE_AREA_NEUTRO = "#E9ECF0";
const coloreArea = (nome) => aree[nome] || COLORE_AREA_NEUTRO;

const el = (id) => document.getElementById(id);
const api = async (percorso, opzioni = {}) => {
  const risposta = await fetch(`/api${percorso}`, {
    headers: { "Content-Type": "application/json" }, ...opzioni,
  });
  if (!risposta.ok) throw new Error((await risposta.text()) || risposta.status);
  return risposta.json();
};
const esc = (t) => (t ?? "").toString().replace(/[<>&"]/g, (c) =>
  ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" }[c]));

const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const daIso = (s) => new Date(s + "T00:00:00");
const minuti = (ora) => Number(ora.slice(0, 2)) * 60 + Number(ora.slice(3, 5));

function dataEstesa(s) {
  const d = daIso(s);
  return `${GIORNI[(d.getDay() + 6) % 7]} ${d.getDate()} ${MESI[d.getMonth()]} ${d.getFullYear()}`;
}
function inizioSettimana(d) {
  const l = new Date(d);
  l.setHours(0, 0, 0, 0);
  l.setDate(l.getDate() - ((l.getDay() + 6) % 7));
  return l;
}

/* ---------- avvio ---------- */

async function avvia() {
  stato = await api("/stato");
  persone = await api("/persone");
  catalogo = await api("/catalogo");
  await caricaAree();

  const scelta = el("scelta-piano");
  scelta.innerHTML = stato.piani.map((p) =>
    `<option value="${p.id}">${esc(p.risorsa)}</option>`).join("")
    || '<option value="">nessuna risorsa</option>';

  if (stato.piani.length) await caricaPiano(stato.piani[0].id);
  mostraAvvisi();
  disegna();
  // Al primo avvio su un computer nuovo si chiede subito da dove spedire:
  // e' la cosa che manca perche' l'app faccia il suo mestiere.
  if (!stato.mail_configurata) apriConfigurazioneMail();
}

async function caricaAree() {
  listaAree = await api("/aree");
  aree = Object.fromEntries(listaAree.map((a) => [a.nome, a.colore]));
}

async function caricaPiano(id) {
  piano = await api(`/piano/${id}`);
  el("scelta-piano").value = id;
  const t = piano.testata;
  el("sottotitolo").textContent =
    [t.mansione, t.reparto, t.data_inizio ? `dal ${dataEstesa(t.data_inizio)}` : null]
      .filter(Boolean).join(" · ");
  // Il calendario si apre sulla settimana di oggi, non sulla prima sessione:
  // e' inutile ripartire da mesi fa quando quelle sessioni sono gia' svolte.
  lunediCorrente = inizioSettimana(new Date());
}

el("scelta-piano").addEventListener("change", async (e) => {
  await caricaPiano(Number(e.target.value));
  disegna();
});
el("nuova-risorsa").addEventListener("click", apriNuovaRisorsa);

/* Tema chiaro/scuro. L'attributo e' gia' impostato in <head> per non far
   lampeggiare la pagina; qui aggiorniamo l'icona e gestiamo il clic. */
function applicaTema(tema) {
  const scuro = tema === "scuro";
  document.documentElement.setAttribute("data-theme", scuro ? "scuro" : "chiaro");
  try { localStorage.setItem("tema", scuro ? "scuro" : "chiaro"); } catch (e) {}
  const b = el("toggle-tema");
  b.innerHTML = icona(scuro ? "sole" : "luna");
  b.title = scuro ? "Passa al tema chiaro" : "Passa al tema scuro";
}
(function iniziaTema() {
  let tema;
  try { tema = localStorage.getItem("tema"); } catch (e) {}
  if (!tema) tema = matchMedia("(prefers-color-scheme: dark)").matches ? "scuro" : "chiaro";
  applicaTema(tema);
  el("toggle-tema").addEventListener("click", () => {
    const attuale = document.documentElement.getAttribute("data-theme");
    applicaTema(attuale === "scuro" ? "chiaro" : "scuro");
  });
})();

document.querySelectorAll("nav button").forEach((b) => {
  b.insertAdjacentHTML("afterbegin", icona(b.dataset.vista === "mail" ? "mail" : b.dataset.vista));
});

document.querySelectorAll("nav button").forEach((b) =>
  b.addEventListener("click", () => {
    document.querySelectorAll("nav button").forEach((x) => x.classList.remove("attiva"));
    b.classList.add("attiva");
    vistaCorrente = b.dataset.vista;
    disegna();
  }));

function vaiA(vista) {
  const b = document.querySelector(`nav button[data-vista="${vista}"]`);
  if (b) b.click();
}

// Ogni avviso ha una X a destra per nasconderlo: compaiono all'apertura, poi
// l'utente li chiude quando li ha letti. Ricompaiono al prossimo avvio se la
// situazione che segnalano e' ancora in piedi.
const avviso = (titolo, corpo) =>
  `<div class="avviso">${icona("avviso")}<div><strong>${titolo}</strong>${corpo}</div>
    <button class="chiudi-avviso" title="Nascondi" aria-label="Nascondi"
      onclick="this.closest('.avviso').remove()">${icona("annulla")}</button></div>`;

function mostraAvvisi() {
  const avvisi = [];
  // Prima di tutto: senza questa scelta l'app non sa da dove spedire.
  if (!stato.mail_configurata) {
    avvisi.push(avviso("L'invio delle email non e' ancora configurato",
      ` L'app non sa da quale programma di posta far partire le notifiche. <a href="#" onclick="apriConfigurazioneMail();return false">Configuralo adesso</a>.`));
  }
  if (stato.chiuse_all_avvio?.length) {
    avvisi.push(avviso(`Chiuse automaticamente ${stato.chiuse_all_avvio.length} sessioni passate`,
      ` Segnate svolte con esito OK. Correggile dall'agenda se qualcuna non si e' tenuta.`));
  }
  if (stato.persone_senza_email) {
    const q = stato.persone_senza_email;
    avvisi.push(avviso(q === 1 ? "Una persona non ha l'email" : `${q} persone non hanno l'email`,
      ` Senza email non ricevono le notifiche. <a href="#" onclick="vaiA('persone');return false">Completa la rubrica</a>.`));
  }
  // Con l'invio spento l'app funziona ma non avvisa nessuno, e senza questo
  // riquadro la cosa si scoprirebbe solo aprendo il registro delle mail.
  if (!stato.invio_email_automatico) {
    avvisi.push(avviso("L'invio automatico delle email e' spento",
      ` Le notifiche vengono preparate e registrate, ma non partono. <a href="#" onclick="vaiA('mail');return false">Accendilo da Mail inviate</a>.`));
  }
  if (stato.canale_mail === "file") {
    avvisi.push(avviso("Su questo computer non c'e' un client di posta",
      ` Senza Outlook ogni notifica viene salvata come file invece di essere spedita.`));
  }
  el("avvisi").innerHTML = avvisi.join("");
}

function disegna() {
  if (!piano && !["persone", "moduli"].includes(vistaCorrente)) {
    el("vista").innerHTML = `<p class="vuoto">Nessuna risorsa in formazione.<br><br>
      <button class="azione primario" onclick="apriNuovaRisorsa()">Crea la prima</button></p>`;
    return;
  }
  ({ agenda: vistaAgenda, settimana: vistaSettimana, piano: vistaPiano,
     moduli: vistaModuli, persone: vistaPersone, mail: vistaMail })[vistaCorrente]();
}

/* ---------- Agenda ---------- */

function vistaAgenda() {
  const oggi = iso(new Date());
  const perGiorno = {};
  piano.sessioni.forEach((s) => (perGiorno[s.data] ??= []).push(s));

  const disegnaGiorno = (data) => {
    const righe = perGiorno[data].map((s) => `
      <div class="sessione" style="border-left-color:${s.colore_area || COLORE_AREA_NEUTRO}">
        <div class="orario">${s.ora_inizio} – ${s.ora_fine}</div>
        <div class="durata">${s.durata} h</div>
        <div><div class="titolo">${esc(s.dettaglio) || "(senza titolo)"}</div>
          <div class="modulo">${s.codice ? `${s.codice} · ${esc(s.modulo_titolo)}`
            : "<span class='mancante'>modulo da assegnare</span>"}</div></div>
        <div class="tutor">${s.tutor.map((t) => esc(t.nome)).join(", ")
          || "<span class='mancante'>tutor da assegnare</span>"}</div>
        <div><span class="pastiglia" style="background:${COLORI[s.stato]}">${s.stato}</span>${
          s.chiusa_automaticamente ? '<span class="auto">auto</span>' : ""}</div>
        <div class="azioni">
          <button class="azione" onclick="apriModifica(${s.id})" title="Sposta">${icona("sposta")}</button>
          <button class="azione" onclick="segnaSvolta(${s.id})" title="Segna svolta">${icona("fatto")}</button>
          <button class="azione" onclick="annulla(${s.id})" title="Annulla">${icona("annulla")}</button>
        </div>
      </div>`).join("");
    return `<div class="giorno ${data < oggi ? "passato" : ""}">
      <h3>${dataEstesa(data)}</h3>${righe}</div>`;
  };

  // I giorni passati stanno sotto, richiusi: col tempo diventano la maggior
  // parte dell'agenda e coprirebbero quello che deve ancora succedere.
  const date = Object.keys(perGiorno).sort();
  const passate = date.filter((d) => d < oggi);
  const prossime = date.filter((d) => d >= oggi);

  const giorni = (passate.length
    ? `<details class="giorni-passati">
         <summary>${passate.length === 1 ? "1 giorno gia' passato" : `${passate.length} giorni gia' passati`}</summary>
         ${passate.map(disegnaGiorno).join("")}
       </details>`
    : "") + prossime.map(disegnaGiorno).join("");

  // Legenda: le aree effettivamente presenti nel piano, col loro colore.
  const areeUsate = {};
  piano.sessioni.forEach((s) => { if (s.area) areeUsate[s.area] = s.colore_area; });
  const legenda = Object.entries(areeUsate).sort()
    .map(([a, c]) => `<span><i style="background:${c}"></i>${esc(a)}</span>`).join("");

  el("vista").innerHTML = `
    <div class="barra">
      <div class="legenda">${legenda || '<span class="tenue-nota">Il colore a sinistra indica l\'area del modulo</span>'}</div>
      <button class="azione primario" onclick="apriNuova()">${icona("piu")}Nuova sessione</button>
    </div>
    ${giorni || '<p class="vuoto">Nessuna sessione. Creane una.</p>'}`;
}

/* ---------- Calendario settimanale ---------- */

function vistaSettimana() {
  const giorniSettimana = [...Array(7)].map((_, i) => {
    const d = new Date(lunediCorrente);
    d.setDate(d.getDate() + i);
    return d;
  });
  // il fine settimana compare solo se ci sono sessioni
  const conSessioni = new Set(piano.sessioni.map((s) => s.data));
  const visibili = giorniSettimana.filter((d, i) => i < 5 || conSessioni.has(iso(d)));
  const oggi = iso(new Date());

  const intestazioni = visibili.map((d) => `
    <div class="testa ${iso(d) === oggi ? "oggi" : ""}">
      ${GIORNI_BREVI[(d.getDay() + 6) % 7]}<span class="numero">${d.getDate()}</span>
    </div>`).join("");

  const altezza = (ORA_ULTIMA - ORA_PRIMA) * ALTEZZA_ORA;
  const scala = [...Array(ORA_ULTIMA - ORA_PRIMA + 1)].map((_, i) =>
    `<span style="top:${i * ALTEZZA_ORA}px">${String(ORA_PRIMA + i).padStart(2, "0")}:00</span>`).join("");

  const colonne = visibili.map((d) => {
    const delGiorno = piano.sessioni.filter((s) => s.data === iso(d));
    const blocchi = delGiorno.map((s, indice) => {
      const cima = ((minuti(s.ora_inizio) - ORA_PRIMA * 60) / 60) * ALTEZZA_ORA;
      const alto = Math.max(((minuti(s.ora_fine) - minuti(s.ora_inizio)) / 60) * ALTEZZA_ORA, 20);
      // sessioni contemporanee affiancate, invece che sovrapposte
      const insieme = delGiorno.filter((a) =>
        minuti(a.ora_inizio) < minuti(s.ora_fine) && minuti(a.ora_fine) > minuti(s.ora_inizio));
      const quante = insieme.length, quale = insieme.indexOf(s);
      const larghezza = 100 / quante;
      const corto = alto < 34;
      const classeStato = s.stato === "Annullata" ? "annullata" : "";
      const descr = [esc(s.dettaglio) || "(senza titolo)", s.area, s.stato,
        s.tutor.map((t) => esc(t.nome)).join(", ")].filter(Boolean).join(" · ");
      return `<div class="blocco ${corto ? "corto" : ""} ${classeStato}" style="
          --i:${indice};
          top:${cima}px; height:${alto}px;
          left:calc(${quale * larghezza}% + 3px); width:calc(${larghezza}% - 6px);
          background:${s.colore_area || COLORE_AREA_NEUTRO}"
        onclick="apriModifica(${s.id})" title="${descr}">
        ${corto
          ? `<div class="cosa">${s.ora_inizio} ${esc(s.dettaglio) || ""}</div>`
          : `<div class="quando">${s.ora_inizio}</div>
             <div class="cosa">${esc(s.dettaglio) || "(senza titolo)"}</div>`}
      </div>`;
    }).join("");
    return `<div class="colonna" style="height:${altezza}px">${blocchi}</div>`;
  }).join("");

  const fine = new Date(lunediCorrente);
  fine.setDate(fine.getDate() + 6);

  el("vista").innerHTML = `
    <div class="barra-settimana">
      <button class="azione" onclick="cambiaSettimana(-7)">← precedente</button>
      <span class="periodo">${lunediCorrente.getDate()} ${MESI[lunediCorrente.getMonth()]}
        – ${fine.getDate()} ${MESI[fine.getMonth()]} ${fine.getFullYear()}</span>
      <button class="azione" onclick="cambiaSettimana(7)">successiva →</button>
      <button class="azione" onclick="vaiAOggi()">oggi</button>
      <button class="azione primario" style="margin-left:auto" onclick="apriNuova()">${icona("piu")}Nuova sessione</button>
    </div>
    <div class="settimana" style="--giorni:${visibili.length}; --altezza-ora:${ALTEZZA_ORA}px">
      <div class="angolo"></div>${intestazioni}
      <div class="ore" style="height:${altezza}px">${scala}</div>${colonne}
    </div>`;
}

function cambiaSettimana(giorni) {
  lunediCorrente.setDate(lunediCorrente.getDate() + giorni);
  vistaSettimana();
}
function vaiAOggi() {
  lunediCorrente = inizioSettimana(new Date());
  vistaSettimana();
}

/* ---------- Piano ISO ---------- */

function vistaPiano() {
  const righe = piano.moduli.map((m) => `
    <tr>
      <td>${m.codice}</td><td>${esc(m.area)}</td><td>${esc(m.titolo)}</td>
      <td>${esc(m.modalita) ?? ""}</td><td>${esc(m.tutor_referente) ?? ""}</td>
      <td>${m.dal ? m.dal.slice(8) + "/" + m.dal.slice(5, 7) : ""}</td>
      <td>${m.al ? m.al.slice(8) + "/" + m.al.slice(5, 7) : ""}</td>
      <td class="num">${m.sessioni_pianificate}</td>
      <td class="num">${m.sessioni_svolte}</td>
      <td class="num">${m.ore_svolte}</td>
      <td><span class="pastiglia" style="background:${COLORI[m.stato]}">${m.stato}</span></td>
      <td class="modificabile"><input type="date" value="${m.entro_il ?? ""}"
          onchange="salvaModulo(${m.id},'entro_il',this.value)"></td>
      <td class="modificabile"><input value="${esc(m.verifica_chiusura) ?? ""}"
          onchange="salvaModulo(${m.id},'verifica_chiusura',this.value)"></td>
      <td class="modificabile"><select onchange="salvaModulo(${m.id},'verifica_efficacia',this.value)">
        ${["", "Superata", "Da ripetere", "N.A."].map((v) =>
          `<option ${v === m.verifica_efficacia ? "selected" : ""}>${v}</option>`).join("")}</select></td>
      <td class="modificabile"><input type="date" value="${m.data_verifica ?? ""}"
          onchange="salvaModulo(${m.id},'data_verifica',this.value)"></td>
      <td class="modificabile"><select onchange="salvaModulo(${m.id},'esito',this.value)">
        ${["", "OK", "KO"].map((v) => `<option ${v === m.esito ? "selected" : ""}>${v}</option>`).join("")}</select></td>
    </tr>`).join("");

  el("vista").innerHTML = `
    <div class="barra">
      <p class="nota">Le colonne bianche si calcolano dalle sessioni. Quelle gialle sono del responsabile qualita'.</p>
      <label class="codice-modulo" title="Compare in alto a sinistra sul modulo stampato">
        Codice del modulo
        <input id="c-codice-modulo" value="${esc(stato.codice_modulo || "")}"
          onchange="salvaCodiceModulo(this.value)">
      </label>
      <button class="azione primario" onclick="stampaPiano()">${icona("stampa")}Stampa il modulo firmabile</button>
    </div>
    <div style="overflow-x:auto"><table>
      <thead><tr>
        <th>Cod.</th><th>Area</th><th>Formazione</th><th>Modalita</th><th>Tutor</th>
        <th>Dal</th><th>Al</th><th>Pian.</th><th>Svolte</th><th>Ore</th><th>Stato</th>
        <th>Entro il</th><th>Verifica chiusura</th><th>Verifica efficacia</th><th>Data verifica</th><th>Esito</th>
      </tr></thead><tbody>${righe}</tbody>
    </table></div>`;
}

async function salvaModulo(id, campo, valore) {
  await api(`/moduli/${id}`, { method: "PATCH", body: JSON.stringify({ [campo]: valore || null }) });
}

/* Il codice del modulo e' quello del sistema qualita' dell'azienda: cambia da
   una all'altra, quindi sta nell'archivio e non nel programma. */
async function salvaCodiceModulo(valore) {
  const codice = valore.trim();
  if (!codice) return;
  await api("/documento/codice", {
    method: "PUT",
    body: JSON.stringify({ codice }),
  });
  stato.codice_modulo = codice;
}

async function stampaPiano() {
  const r = await api(`/piano/${piano.testata.id}/stampa`, { method: "POST" });
  el("avvisi").insertAdjacentHTML("afterbegin",
    `<div class="avviso">${icona("avviso")}<div><strong>Modulo PDF generato</strong>${esc(r.percorso)}</div>`);
}

/* ---------- Catalogo moduli ---------- */

function vistaModuli() {
  const opzioniTutor = (scelto) => persone.filter((p) => !p.e_risorsa).map((p) =>
    `<option value="${p.id}" ${p.id === scelto ? "selected" : ""}>${esc(p.cognome)} ${esc(p.nome)}</option>`).join("");

  const righe = catalogo.map((m) => `
    <tr>
      <td><b>${m.codice}</b></td>
      <td><div class="cella-area">
        <input type="color" class="colore-area" value="${m.colore || coloreArea(m.area)}"
          data-area="${esc(m.area)}" title="Colore dell'area — vale per tutti i suoi moduli"
          onchange="cambiaColoreArea(this.dataset.area, this.value)">
        <input value="${esc(m.area)}" onchange="salvaCatalogo('${m.codice}','area',this.value)">
      </div></td>
      <td><input value="${esc(m.titolo)}" onchange="salvaCatalogo('${m.codice}','titolo',this.value)"></td>
      <td><select onchange="salvaCatalogo('${m.codice}','modalita_default',this.value)">
        ${["", ...MODALITA].map((v) => `<option ${v === m.modalita_default ? "selected" : ""}>${v}</option>`).join("")}</select></td>
      <td><select onchange="salvaCatalogo('${m.codice}','tutor_referente_default_id',this.value)">
        <option value="">—</option>${opzioniTutor(m.tutor_referente_default_id)}</select></td>
      <td class="num">${m.usato_in}</td>
      <td><button class="azione" onclick="eliminaModulo('${m.codice}')">Elimina</button></td>
    </tr>`).join("");

  el("vista").innerHTML = `
    <div class="barra">
      <p class="nota">Il modello da cui nasce il piano di ogni nuova risorsa.
        Modificarlo non tocca i piani gia' creati.</p>
      <button class="azione primario" onclick="apriNuovoModulo()">${icona("piu")}Nuovo modulo</button>
    </div>
    <table><thead><tr><th>Cod.</th><th>Area</th><th>Formazione</th><th>Modalita</th>
      <th>Tutor predefinito</th><th>Usato in</th><th></th></tr></thead>
      <tbody>${righe}</tbody></table>`;
}

async function salvaCatalogo(codice, campo, valore) {
  const m = catalogo.find((x) => x.codice === codice);
  m[campo] = campo.endsWith("_id") ? (valore ? Number(valore) : null) : valore;
  await api(`/catalogo/${codice}`, {
    method: "PATCH",
    body: JSON.stringify({
      codice, area: m.area, titolo: m.titolo,
      modalita_default: m.modalita_default || null,
      tutor_referente_default_id: m.tutor_referente_default_id,
    }),
  });
}

async function eliminaModulo(codice) {
  if (!confirm(`Togliere ${codice} dal catalogo? I piani gia' creati non cambiano.`)) return;
  await api(`/catalogo/${codice}`, { method: "DELETE" });
  catalogo = await api("/catalogo");
  vistaModuli();
}

async function cambiaColoreArea(nome, colore) {
  await api("/aree", { method: "PUT", body: JSON.stringify({ nome, colore }) });
  await caricaAree();
  catalogo = await api("/catalogo");
  const id = Number(el("scelta-piano").value);
  if (piano && id) await caricaPiano(id);   // aggiorna i colori nelle sessioni
  disegna();
}

function apriNuovoModulo() {
  const prossimo = "M" + String(catalogo.length + 1).padStart(2, "0");
  const coloriUsati = [...new Set(listaAree.map((a) => a.colore))];
  const liberi = PALETTE_AREE.filter((c) => !coloriUsati.includes(c));
  const coloreDefault = liberi[0] || PALETTE_AREE[0];
  const campioni = coloriUsati.map((c) =>
    `<button type="button" class="campione" style="background:${c}" title="Usa questo colore"
       onclick="el('c-colore').value='${c}'"></button>`).join("");

  el("finestra-titolo").textContent = "Nuovo modulo del catalogo";
  el("finestra-contenuto").innerHTML = `
    <div class="affiancati">
      <div class="campo"><label>Codice</label><input id="c-codice" value="${prossimo}"></div>
      <div class="campo"><label>Area <span class="sub">esistente o nuova</span></label>
        <input id="c-area" list="aree-esistenti" autocomplete="off" placeholder="es. Ufficio Tecnico">
        <datalist id="aree-esistenti">${listaAree.map((a) =>
          `<option value="${esc(a.nome)}">`).join("")}</datalist></div>
    </div>
    <div class="campo"><label>Colore dell'area</label>
      <div class="scelta-colore">
        <input type="color" id="c-colore" value="${coloreDefault}">
        <div class="campioni">${campioni}</div>
      </div>
      <span class="sub">Scegli un colore gia' usato o creane uno nuovo. Se l'area esiste gia', prende il suo.</span>
    </div>
    <div class="campo"><label>Formazione / addestramento</label><input id="c-titolo"></div>
    <div class="campo"><label>Modalita</label><select id="c-modalita">
      ${["", ...MODALITA].map((v) => `<option>${v}</option>`).join("")}</select></div>
    <div class="campo"><label>Tutor predefinito</label><select id="c-tutor-mod"><option value="">—</option>
      ${persone.filter((p) => !p.e_risorsa).map((p) =>
        `<option value="${p.id}">${esc(p.cognome)} ${esc(p.nome)}</option>`).join("")}</select></div>`;

  // Se si digita un'area gia' esistente, il colore si allinea al suo.
  el("c-area").addEventListener("input", () => {
    const a = listaAree.find((x) => x.nome.toLowerCase() === el("c-area").value.trim().toLowerCase());
    if (a) el("c-colore").value = a.colore;
  });

  el("finestra-conferma").onclick = async () => {
    try {
      await api("/catalogo", {
        method: "POST",
        body: JSON.stringify({
          codice: el("c-codice").value.trim(),
          area: el("c-area").value.trim(),
          titolo: el("c-titolo").value.trim(),
          modalita_default: el("c-modalita").value || null,
          tutor_referente_default_id: el("c-tutor-mod").value ? Number(el("c-tutor-mod").value) : null,
          colore: el("c-colore").value,
        }),
      });
    } catch (errore) {
      alert(errore.message);
      return;
    }
    el("finestra").close();
    catalogo = await api("/catalogo");
    await caricaAree();
    vistaModuli();
  };
  el("finestra").showModal();
}

/* ---------- Persone ---------- */

function vistaPersone() {
  const righe = persone.map((p) => `
    <tr>
      <td><input value="${esc(p.nome)}" onchange="salvaPersona(${p.id},'nome',this.value)"></td>
      <td><input value="${esc(p.cognome)}" onchange="salvaPersona(${p.id},'cognome',this.value)"></td>
      <td class="${p.email ? "" : "modificabile"}">
        <input type="email" placeholder="manca" value="${esc(p.email) ?? ""}"
               onchange="salvaPersona(${p.id},'email',this.value)"></td>
      <td><input value="${esc(p.reparto) ?? ""}" onchange="salvaPersona(${p.id},'reparto',this.value)"></td>
    </tr>`).join("");
  el("vista").innerHTML = `
    <div class="barra">
      <p class="nota">Rubrica di tutor e dipendenti. Rinominare una persona non altera i piani:
        le sessioni la riferiscono per identita', non per nome.</p>
      <button class="azione primario" onclick="apriNuovaPersona()">${icona("piu")}Nuova persona</button>
    </div>
    <table><thead><tr><th>Nome</th><th>Cognome</th><th>Email</th><th>Reparto</th></tr></thead>
    <tbody>${righe}</tbody></table>`;
}

function apriNuovaPersona() {
  el("finestra-titolo").textContent = "Nuova persona";
  el("finestra-contenuto").innerHTML = `
    <div class="affiancati">
      <div class="campo"><label>Nome</label><input id="np-nome"></div>
      <div class="campo"><label>Cognome</label><input id="np-cognome"></div>
    </div>
    <div class="campo"><label>Email</label><input type="email" id="np-email"
      placeholder="serve per ricevere le notifiche"></div>
    <p class="nota">Vale sia per un tutor sia per un dipendente: un profilo solo.
      Senza email la persona non ricevera' le mail di modifica del piano.</p>`;
  el("finestra-conferma").onclick = creaPersona;
  el("finestra").showModal();
}

async function creaPersona() {
  const nome = el("np-nome").value.trim(), cognome = el("np-cognome").value.trim();
  if (!nome || !cognome) { alert("Nome e cognome sono obbligatori."); return; }
  await api("/persone", {
    method: "POST",
    body: JSON.stringify({ nome, cognome, email: el("np-email").value.trim() || null }),
  });
  persone = await api("/persone");
  stato = await api("/stato");
  el("finestra").close();
  mostraAvvisi();
  if (vistaCorrente === "persone") vistaPersone();
}

async function salvaPersona(id, campo, valore) {
  const p = persone.find((x) => x.id === id);
  p[campo] = valore;
  await api(`/persone/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ nome: p.nome, cognome: p.cognome,
                           email: p.email || null, reparto: p.reparto || null }),
  });
  stato = await api("/stato");
  mostraAvvisi();
}

/* ---------- Mail ---------- */

/* ---------- Configurazione dell'invio email ----------

   Il programma di posta non si indovina: su un computer possono esserci
   Outlook e Mail, uno configurato e l'altro no, e da fuori non si distinguono.
   Quindi al primo avvio si chiede, si prova davvero, e poi si ricorda. */

async function apriConfigurazioneMail() {
  el("finestra-titolo").textContent = "Da dove partono le email";
  el("finestra-contenuto").innerHTML =
    `<p class="nota">Cerco i programmi di posta su questo computer. Puo' richiedere qualche secondo, e potrebbero aprirsi.</p>`;
  el("finestra-conferma").textContent = "Salva";
  el("finestra-conferma").onclick = null;
  el("finestra").showModal();

  let dati;
  try {
    dati = await api("/mail/canali");
  } catch (errore) {
    el("finestra-contenuto").innerHTML =
      `<p class="mancante">Non riesco a leggere i programmi di posta: ${esc(errore.message)}</p>`;
    return;
  }
  disegnaConfigurazioneMail(dati);
}

function disegnaConfigurazioneMail(dati) {
  const scelte = dati.canali.map((c) => {
    const dettaglio = c.account.length
      ? `${c.account.length === 1 ? "1 indirizzo" : c.account.length + " indirizzi"}: ${esc(c.account.join(", "))}`
      : (c.nome === "file"
          ? "le notifiche restano su disco, non vengono spedite"
          : "nessun indirizzo configurato: da qui non partirebbe niente");
    return `<label class="riga-scelta">
      <input type="radio" name="canale-mail" value="${c.nome}" ${c.nome === dati.scelto ? "checked" : ""}>
      <span><b>${esc(c.etichetta)}</b><br><em class="${c.pronto ? "" : "mancante"}">${dettaglio}</em></span>
    </label>`;
  }).join("");

  el("finestra-contenuto").innerHTML = `
    <div class="campo">
      <label>Programma di posta <span class="sub">quello con l'indirizzo di lavoro</span></label>
      <div class="scelta-multipla">${scelte || '<span class="nota" style="padding:6px">Nessun programma di posta trovato.</span>'}</div>
    </div>
    <div class="campo" id="campo-mittente"></div>
    <div class="campo">
      <label>Prova l'invio <span class="sub">consigliata: conferma che le mail partano davvero</span></label>
      <div class="scelta-colore">
        <input id="c-prova" placeholder="indirizzo a cui mandare la prova" value="${esc(dati.mittente || "")}">
        <button class="azione" id="c-invia-prova" type="button">Invia prova</button>
      </div>
      <div id="esito-prova"></div>
    </div>`;

  const aggiornaMittenti = () => {
    const scelto = document.querySelector('input[name="canale-mail"]:checked');
    const canale = dati.canali.find((c) => c.nome === scelto?.value);
    const campo = el("campo-mittente");
    if (!canale || !canale.account.length) {
      campo.innerHTML = "";
      return;
    }
    campo.innerHTML = `<label>Indirizzo mittente</label>
      <select id="c-mittente">${canale.account.map((a) =>
        `<option ${a === dati.mittente ? "selected" : ""}>${esc(a)}</option>`).join("")}</select>`;
  };
  document.querySelectorAll('input[name="canale-mail"]').forEach((r) =>
    r.addEventListener("change", aggiornaMittenti));
  aggiornaMittenti();

  el("c-invia-prova").onclick = async () => {
    const scelto = document.querySelector('input[name="canale-mail"]:checked');
    const destinatario = el("c-prova").value.trim();
    if (!scelto || !destinatario) {
      el("esito-prova").innerHTML = `<p class="mancante">Scegli il programma e scrivi un indirizzo.</p>`;
      return;
    }
    el("esito-prova").innerHTML = `<p class="nota">Invio in corso, attendo che parta davvero...</p>`;
    try {
      const esito = await api("/mail/prova", {
        method: "POST",
        body: JSON.stringify({
          destinatario,
          canale: scelto.value,
          mittente: el("c-mittente")?.value || null,
        }),
      });
      el("esito-prova").innerHTML = esito.esito === "inviata"
        ? `<p class="esito-ok">Partita. Controlla di averla ricevuta prima di salvare.</p>`
        : `<p class="mancante">Non e' partita: ${esc(esito.errore || "motivo sconosciuto")}</p>`;
    } catch (errore) {
      el("esito-prova").innerHTML = `<p class="mancante">Non e' partita: ${esc(errore.message)}</p>`;
    }
  };

  el("finestra-conferma").onclick = async () => {
    const scelto = document.querySelector('input[name="canale-mail"]:checked');
    if (!scelto) {
      alert("Scegli da quale programma partono le email.");
      return;
    }
    await api("/mail/canale", {
      method: "PUT",
      body: JSON.stringify({
        canale: scelto.value,
        mittente: el("c-mittente")?.value || null,
      }),
    });
    el("finestra").close();
    stato = await api("/stato");
    mostraAvvisi();
    if (vistaCorrente === "mail") await vistaMail();
  };
}

async function vistaMail() {
  const [registro, impostazioni] = await Promise.all([
    api("/mail"), api("/mail/impostazioni"),
  ]);
  stato.invio_email_automatico = impostazioni.invio_email_automatico;
  const attivo = impostazioni.invio_email_automatico;
  const righe = registro.map((m) => {
    const statoMail = STATI_MAIL[m.esito] || m.esito;
    const riprova = ["invio_disattivato", "errore"].includes(m.esito)
      ? `<button class="azione piccolo" data-riprova-mail="${m.id}">Riprova</button>` : "";
    const senzaEmail = (m.senza_email ?? []).length
      ? `<div class="nota">Senza email: ${esc(m.senza_email.join(", "))}</div>` : "";
    return `<tr>
      <td>${esc((m.registrata_il || m.inviata_il || "-").replace("T", " "))}</td>
      <td>${esc(m.tipo)}</td>
      <td>${esc(m.destinatari) || "<span class='mancante'>nessuno</span>"}${senzaEmail}</td>
      <td>${esc(m.oggetto)}</td>
      <td><span class="stato-mail ${m.esito === "inviata" ? "positivo" : "attenzione"}">${esc(statoMail)}</span></td>
      <td class="azioni-mail"><button class="azione piccolo" data-vedi-mail="${m.id}">Vedi</button>${riprova}<button class="azione piccolo" data-elimina-mail="${m.id}">Elimina</button></td>
    </tr>`;
  }).join("");
  registroMail = registro;
  const riprovabili = registro.filter((m) =>
    ["invio_disattivato", "errore"].includes(m.esito)).length;
  el("vista").innerHTML = `<section class="impostazioni-mail">
      <div>
        <strong>Invio automatico email</strong>
        <p class="nota">${attivo
          ? "Le notifiche vengono consegnate tramite il programma di posta configurato."
          : "Le notifiche vengono registrate ma non inviate."}
          ${stato.mail_configurata
            ? `Partono da <b>${esc(stato.mittente_mail || stato.canale_mail)}</b>.`
            : "<b>Programma di posta non ancora scelto.</b>"}
          <a href="#" onclick="apriConfigurazioneMail();return false">Configura l'invio</a>.</p>
      </div>
      <div class="azioni-registro">
        ${riprovabili ? `<button class="azione" id="riprova-tutte">Riprova tutte (${riprovabili})</button>` : ""}
        <label class="interruttore-mail">
          <input type="checkbox" id="toggle-invio-email" ${attivo ? "checked" : ""}>
          <span class="interruttore-pallino"></span>
          <span>${attivo ? "ON" : "OFF"}</span>
        </label>
      </div>
    </section>
    ${registro.length ? `<table>
      <thead><tr><th>Quando</th><th>Tipo</th><th>Destinatari</th><th>Oggetto</th><th>Stato</th><th>Azioni</th></tr></thead>
      <tbody>${righe}</tbody></table>` : '<p class="vuoto">Nessuna notifica ancora registrata.</p>'}`;

  el("toggle-invio-email").addEventListener("change", async (evento) => {
    const valore = evento.target.checked;
    const controllo = evento.target;
    controllo.disabled = true;
    try {
      const confermato = await api("/mail/impostazioni", {
        method: "PUT",
        body: JSON.stringify({ invio_email_automatico: valore }),
      });
      const statoConfermato = Boolean(confermato.invio_email_automatico);
      stato.invio_email_automatico = statoConfermato;
      controllo.checked = statoConfermato;
      mostraAvvisi();   // l'avviso in cima segue il toggle
    } catch (errore) {
      try {
        const reale = await api("/mail/impostazioni");
        stato.invio_email_automatico = Boolean(reale.invio_email_automatico);
        controllo.checked = stato.invio_email_automatico;
        mostraAvvisi();
      } catch (_) {
        controllo.checked = !valore;
      }
      alert(`Impossibile aggiornare l'impostazione: ${errore.message}`);
      controllo.disabled = false;
      return;
    }
    try {
      await vistaMail();
    } catch (errore) {
      alert(`Impostazione aggiornata, ma impossibile aggiornare la lista: ${errore.message}`);
      controllo.disabled = false;
    }
  });
  document.querySelectorAll("[data-riprova-mail]").forEach((bottone) =>
    bottone.addEventListener("click", () => riprovaMail(Number(bottone.dataset.riprovaMail), bottone)));
  document.querySelectorAll("[data-elimina-mail]").forEach((bottone) =>
    bottone.addEventListener("click", () => eliminaMail(Number(bottone.dataset.eliminaMail), bottone)));
  document.querySelectorAll("[data-vedi-mail]").forEach((bottone) =>
    bottone.addEventListener("click", () => mostraMail(Number(bottone.dataset.vediMail))));
  el("riprova-tutte")?.addEventListener("click", riprovaTutte);
}

/* Il testo della notifica com'e' stato spedito: serve a controllare cosa e'
   arrivato davvero alle persone, non solo che sia partito qualcosa. */
function mostraMail(id) {
  const voce = registroMail.find((m) => m.id === id);
  if (!voce) return;
  el("finestra-titolo").textContent = "Notifica inviata";
  el("finestra-contenuto").innerHTML = `
    <div class="campo"><label>Quando</label>
      <p class="nota">${esc((voce.registrata_il || voce.inviata_il || "-").replace("T", " "))}
        · ${esc(STATI_MAIL[voce.esito] || voce.esito)}</p></div>
    <div class="campo"><label>Destinatari</label>
      <p class="nota">${esc(voce.destinatari) || "<span class='mancante'>nessuno</span>"}</p></div>
    ${(voce.senza_email ?? []).length
      ? `<div class="campo"><label>Senza indirizzo</label>
           <p class="nota mancante">${esc(voce.senza_email.join(", "))}</p></div>` : ""}
    <div class="campo"><label>Oggetto</label><p class="nota">${esc(voce.oggetto)}</p></div>
    <div class="campo"><label>Testo</label><pre class="corpo-mail">${esc(voce.corpo)}</pre></div>
    ${voce.errore ? `<div class="campo"><label>Errore</label>
        <p class="nota mancante">${esc(voce.errore)}</p></div>` : ""}`;
  // qui non si modifica niente: il pulsante di conferma serve solo a chiudere
  el("finestra-conferma").textContent = "Chiudi";
  el("finestra-conferma").onclick = () => {
    el("finestra-conferma").textContent = "Salva";
    el("finestra").close();
  };
  el("finestra").showModal();
}

async function riprovaTutte() {
  const bottone = el("riprova-tutte");
  bottone.disabled = true;
  bottone.textContent = "Invio in corso...";
  try {
    const esito = await api("/mail/riprova-tutte", { method: "POST" });
    const parti = [];
    if (esito.inviate) parti.push(`${esito.inviate} inviate`);
    if (esito.errori) parti.push(`${esito.errori} non partite`);
    if (esito.bloccate) parti.push(`${esito.bloccate} ancora ferme (invio spento)`);
    alert(parti.length ? parti.join(", ") : "Non c'era niente da riprovare.");
  } catch (errore) {
    alert(`Non sono riuscito a riprovare: ${errore.message}`);
  }
  await vistaMail();
}

async function riprovaMail(id, bottone) {
  if (bottone.disabled) return;
  bottone.disabled = true;
  try {
    const risposta = await api(`/mail/${id}/riprova`, { method: "POST" });
    if (risposta.esito === "invio_disattivato") {
      alert("Invio email disattivato. Attivalo per poter riprovare.");
    } else if (risposta.esito === "errore") {
      alert(`Invio non riuscito: ${risposta.errore || "errore non specificato"}`);
    } else {
      alert("Email inviata.");
    }
    await vistaMail();
  } catch (errore) {
    bottone.disabled = false;
    alert(`Impossibile riprovare l'invio: ${errore.message}`);
  }
}

async function eliminaMail(id, bottone) {
  if (!confirm("Eliminare questa voce dal registro email?")) return;
  if (bottone.disabled) return;
  bottone.disabled = true;
  try {
    await api(`/mail/${id}`, { method: "DELETE" });
    await vistaMail();
  } catch (errore) {
    bottone.disabled = false;
    alert(`Impossibile eliminare la voce: ${errore.message}`);
  }
}

/* ---------- Nuova risorsa ---------- */

function apriNuovaRisorsa() {
  const elencoPersone = persone.map((p) =>
    `<option value="${p.id}">${esc(p.cognome)} ${esc(p.nome)}</option>`).join("");
  el("finestra-titolo").textContent = "Nuova risorsa in formazione";
  el("finestra-contenuto").innerHTML = `
    <div class="affiancati">
      <div class="campo"><label>Nome</label><input id="r-nome"></div>
      <div class="campo"><label>Cognome</label><input id="r-cognome"></div>
    </div>
    <div class="campo"><label>Email</label><input type="email" id="r-email"></div>
    <div class="affiancati">
      <div class="campo"><label>Reparto</label><input id="r-reparto"></div>
      <div class="campo"><label>Mansione</label><input id="r-mansione"></div>
    </div>
    <div class="affiancati">
      <div class="campo"><label>Responsabile</label>
        <select id="r-responsabile"><option value="">—</option>${elencoPersone}</select></div>
      <div class="campo"><label>Tutor principale</label>
        <select id="r-tutor"><option value="">—</option>${elencoPersone}</select></div>
    </div>
    <div class="affiancati">
      <div class="campo"><label>Data inizio</label><input type="date" id="r-inizio" value="${iso(new Date())}"></div>
      <div class="campo"><label>Motivo</label><select id="r-motivo">
        ${MOTIVI.map((m) => `<option>${m}</option>`).join("")}</select></div>
    </div>
    <p class="nota">
      Il piano nasce con i ${catalogo.length} moduli del catalogo. Le sessioni si aggiungono dopo.</p>`;
  el("finestra-conferma").onclick = async () => {
    const nome = el("r-nome").value.trim(), cognome = el("r-cognome").value.trim();
    if (!nome || !cognome) { alert("Nome e cognome sono obbligatori."); return; }
    const r = await api("/risorse", {
      method: "POST",
      body: JSON.stringify({
        nome, cognome,
        email: el("r-email").value.trim() || null,
        reparto: el("r-reparto").value.trim() || null,
        mansione: el("r-mansione").value.trim() || null,
        responsabile_id: el("r-responsabile").value ? Number(el("r-responsabile").value) : null,
        tutor_principale_id: el("r-tutor").value ? Number(el("r-tutor").value) : null,
        data_inizio: el("r-inizio").value,
        motivo: el("r-motivo").value,
      }),
    });
    el("finestra").close();
    await avvia();
    await caricaPiano(r.piano_id);
    disegna();
  };
  el("finestra").showModal();
}

/* ---------- Finestra sessione ---------- */

function campiSessione(s = {}) {
  const opzioniModuli = piano.moduli.map((m) =>
    `<option value="${m.id}" ${m.id === s.piano_modulo_id ? "selected" : ""}>${m.codice} – ${esc(m.titolo)}</option>`).join("");
  const opzioniTutor = persone.filter((p) => !p.e_risorsa).map((p) => {
    const scelto = (s.tutor ?? []).some((t) => t.id === p.id);
    return `<label class="riga-scelta">
      <input type="checkbox" value="${p.id}" ${scelto ? "checked" : ""}>
      <span>${esc(p.cognome)} ${esc(p.nome)}${p.email ? "" : ` <em class="mancante">senza email</em>`}</span>
    </label>`;
  }).join("");

  return `
    <div class="campo"><label>Data</label><input type="date" id="c-data" value="${s.data ?? iso(new Date())}"></div>
    <div class="affiancati">
      <div class="campo"><label>Inizio</label><input type="time" id="c-inizio" value="${s.ora_inizio ?? "09:00"}"></div>
      <div class="campo"><label>Fine</label><input type="time" id="c-fine" value="${s.ora_fine ?? "12:30"}"></div>
    </div>
    <div class="campo"><label>Modulo</label><select id="c-modulo"><option value="">— nessuno —</option>${opzioniModuli}</select></div>
    <div class="campo"><label>Dettaglio</label><input id="c-dettaglio" value="${esc(s.dettaglio) ?? ""}"></div>
    <div class="campo"><label>Tutor <span class="sub">chi tiene la sessione &middot; puoi sceglierne piu' di uno</span></label>
      <div class="scelta-multipla" id="c-tutor">${opzioniTutor || `<span class="nota" style="padding:6px">Nessuna persona in rubrica. Aggiungine da <b>Persone</b>.</span>`}</div></div>
    <div class="campo"><label>Note</label><input id="c-note" value="${esc(s.note) ?? ""}"></div>
    <div id="c-conflitti"></div>`;
}

function leggiCampi() {
  return {
    data: el("c-data").value,
    ora_inizio: el("c-inizio").value,
    ora_fine: el("c-fine").value,
    piano_modulo_id: el("c-modulo").value ? Number(el("c-modulo").value) : null,
    dettaglio: el("c-dettaglio").value || null,
    note: el("c-note").value || null,
    tutor: [...el("c-tutor").querySelectorAll("input:checked")].map((o) => Number(o.value)),
  };
}

/** Avverte se l'orario si accavalla, senza impedire: a volte e' voluto. */
async function controllaConflitti(escludi = null) {
  const c = leggiCampi();
  if (!c.data || !c.ora_inizio || !c.ora_fine) return [];
  const q = new URLSearchParams({
    piano_id: piano.testata.id, data: c.data,
    ora_inizio: c.ora_inizio, ora_fine: c.ora_fine, tutor: c.tutor.join(","),
  });
  if (escludi) q.set("escludi", escludi);
  const conflitti = await api(`/conflitti?${q}`);
  el("c-conflitti").innerHTML = conflitti.length ? `
    <div class="conflitto">${icona("avviso")}<div><strong>${conflitti.length === 1 ? "Si accavalla con un altro impegno"
      : `Si accavalla con ${conflitti.length} impegni`}</strong>
      ${conflitti.map((x) => `${x.motivo === "risorsa" ? "La risorsa ha" : `${esc(x.chi)} ha`}
        gia' un impegno ${x.ora_inizio}–${x.ora_fine}: ${esc(x.dettaglio) || "sessione"}${
        x.motivo === "tutor" ? ` (${esc(x.risorsa)})` : ""}`).join("<br>")}
      <br><br>Puoi salvare lo stesso, se e' voluto.</div></div>` : "";
  return conflitti;
}

function collegaControlli(escludi = null) {
  ["c-data", "c-inizio", "c-fine", "c-tutor"].forEach((id) =>
    el(id).addEventListener("change", () => controllaConflitti(escludi)));
  controllaConflitti(escludi);
}

function apriNuova() {
  el("finestra-titolo").textContent = "Nuova sessione";
  el("finestra-contenuto").innerHTML = campiSessione();
  collegaControlli();
  el("finestra-conferma").onclick = async () => {
    const risposta = await api("/sessioni", {
      method: "POST",
      body: JSON.stringify({ piano_id: piano.testata.id, stato: "Pianificata", ...leggiCampi() }),
    });
    el("finestra").close();
    await ricarica(risposta.mail, "Sessione creata");
  };
  el("finestra").showModal();
}

function apriModifica(id) {
  const s = piano.sessioni.find((x) => x.id === id);
  el("finestra-titolo").textContent = "Sposta sessione";
  el("finestra-contenuto").innerHTML = campiSessione(s) + `
    <div class="campo"><label>Stato</label><select id="c-stato">
      ${STATI.map((v) => `<option ${v === s.stato ? "selected" : ""}>${v}</option>`).join("")}</select></div>
    <p class="nota">
      Cambiando data od orario parte una mail a tutor e risorsa con il vecchio e il nuovo appuntamento.</p>`;
  collegaControlli(id);
  el("finestra-conferma").onclick = async () => {
    const risposta = await api(`/sessioni/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ ...leggiCampi(), stato: el("c-stato").value }),
    });
    el("finestra").close();
    await ricarica(risposta.mail, risposta.spostata ? "Sessione spostata" : "Sessione aggiornata");
  };
  el("finestra").showModal();
}

async function segnaSvolta(id) {
  await api(`/sessioni/${id}`, { method: "PATCH", body: JSON.stringify({ stato: "Svolta" }) });
  await ricarica(null, "Segnata come svolta");
}

async function annulla(id) {
  if (!confirm("Annullare la sessione? Parte una mail a tutor e risorsa.")) return;
  const risposta = await api(`/sessioni/${id}`, { method: "DELETE" });
  await ricarica(risposta.mail, "Sessione annullata");
}

async function ricarica(mail, messaggio) {
  await caricaPiano(piano.testata.id);
  stato = await api("/stato");
  stato.chiuse_all_avvio = [];
  mostraAvvisi();
  if (mail && mail.senza_email?.length) {
    const parziale = mail.esito === "inviata";
    el("avvisi").insertAdjacentHTML("afterbegin",
      `<div class="avviso">${icona("avviso")}<div><strong>${messaggio}, ${parziale
        ? "ma la mail non ha raggiunto tutti" : "ma la mail non e' partita"}</strong>
       Manca l'indirizzo di: ${esc(mail.senza_email.join(", "))}.</div></div>`);
  }
  disegna();
}

avvia();
