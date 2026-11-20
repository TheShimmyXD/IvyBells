// La cuenta de Claude arriba de la pestana: el correo (se guarda al salir del campo o con
// Enter), su estado como insignia, Comprobar y, si hace falta, la orden para iniciar sesion
// que el autor pega en una terminal (como en Qt, config_page.py).
import { useState } from "react";
import type { AccountStatus } from "../../api/types";
import Icon from "../../shared/Icon";
import type { IconName } from "../../shared/phosphor";
import { accountBadge, accountChanged, accountInitial, type BadgeTone } from "./settingsView";

const BADGE_ICONS: Record<BadgeTone, IconName> = {
  info: "info",
  ok: "check-circle",
  warning: "warning-circle",
  error: "x-circle",
};

const LOGIN_HINT =
  "Pega esta orden en una terminal: abre el navegador y luego pide pegar un código. " +
  "Después vuelve y pulsa Comprobar.";

interface AccountCardProps {
  account: string;
  status: AccountStatus;
  onAccount: (account: string) => void;
  onCheck: () => void;
}

export default function AccountCard({ account, status, onAccount, onCheck }: AccountCardProps) {
  // Lo escrito parte de la cuenta guardada: quien pinta la tarjeta le pone `key={account}`.
  const [typed, setTyped] = useState(account);
  // La orden que se copio; "Copiada" solo mientras sea la que se muestra.
  const [copiedLogin, setCopiedLogin] = useState("");
  const copied = copiedLogin !== "" && copiedLogin === status.login;
  const badge = accountBadge(status);

  const commit = () => {
    if (accountChanged(typed, account)) {
      onAccount(typed);
    }
  };
  const check = () => (accountChanged(typed, account) ? onAccount(typed) : onCheck());
  const copy = () => {
    void navigator.clipboard
      ?.writeText(status.login)
      .then(() => setCopiedLogin(status.login))
      .catch(() => setCopiedLogin(""));
  };

  return (
    <section className="settings-account" aria-label="Cuenta de Claude">
      <div className="settings-account-row">
        <span className="settings-avatar" aria-hidden="true">
          {accountInitial(typed)}
        </span>
        <label className="settings-account-field">
          <span className="settings-caption">Cuenta de Claude</span>
          <input
            className="settings-account-input"
            data-tone={badge.tone}
            value={typed}
            placeholder="Correo de la cuenta; vacío = la sesión de siempre"
            spellCheck={false}
            onChange={(event) => setTyped(event.target.value)}
            onBlur={commit}
            onKeyDown={(event) => event.key === "Enter" && commit()}
          />
        </label>
        <span className="settings-badge" data-tone={badge.tone} role="status">
          <Icon name={badge.busy ? "circle-notch" : BADGE_ICONS[badge.tone]} size={14} />
          {badge.text}
        </span>
        <button type="button" className="settings-button" disabled={badge.busy} onClick={check}>
          <Icon name="arrows-clockwise" size={14} />
          Comprobar
        </button>
      </div>
      {status.login !== "" && (
        <div className="settings-login">
          <div className="settings-login-row">
            <code aria-label="Orden para iniciar sesión">{status.login}</code>
            <button type="button" className="settings-button" onClick={copy}>
              <Icon name="copy" size={14} />
              {copied ? "Copiada" : "Copiar"}
            </button>
          </div>
          <p className="settings-help">{LOGIN_HINT}</p>
        </div>
      )}
    </section>
  );
}
