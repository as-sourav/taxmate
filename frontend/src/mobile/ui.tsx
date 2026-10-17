/** Native screen primitives (`mob-*` CSS). */
import { useEffect, useRef, type ReactNode } from "react";

import { t } from "../i18n/strings";
import { useSwitchLang } from "../lib/useSwitchLang";
import TaxMateMark from "./TaxMateMark";
import type { BioKind } from "./biometric";
import { PIN_LENGTH } from "./pin";

export function tf(key: string, vars: Record<string, string | number>): string {
  return t(key).replace(/\{(\w+)\}/g, (_, k: string) => String(vars[k] ?? ""));
}

export function bioName(kind: BioKind): string {
  return t(`mob.bio.${kind === "none" ? "finger" : kind}`);
}

export function LangToggle() {
  const { lang, toggle } = useSwitchLang();
  return (
    <button
      type="button"
      className="langbtn mob-lang"
      aria-label={t("mob.lang.label")}
      lang={lang === "ar" ? "en" : "ar"}
      onClick={() => {
        void toggle();
      }}
    >
      {t("mob.lang.toggle")}
    </button>
  );
}

export function Frame({
  title, sub, children, foot, onBack, brand = false, lang = true, notice,
}: {
  title: string;
  sub?: ReactNode;
  children?: ReactNode;
  foot?: ReactNode;
  onBack?: () => void;
  /** Show the TaxMate wordmark beside the star (first-run screens). */
  brand?: boolean;
  lang?: boolean;
  notice?: ReactNode;
}) {
  const h1 = useRef<HTMLHeadingElement>(null);
  useEffect(() => { h1.current?.focus(); }, [title]);
  return (
    <div className="mob-screen">
      <div className="mob-top">
        {onBack ? (
          <button type="button" className="iconbtn mob-back" onClick={onBack} aria-label={t("mob.back")}>
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
              <path d="M12.5 4.5L7 10l5.5 5.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        ) : <span />}
        {lang && <LangToggle />}
      </div>
      <main className="mob-body">
        <div className="mob-brand">
          <TaxMateMark size={brand ? 64 : 52} />
          {brand && <span className="mob-word" dir="ltr"><span>Tax</span><span>Mate</span></span>}
        </div>
        <h1 className="mob-title" tabIndex={-1} ref={h1}>{title}</h1>
        {sub && <p className="mob-sub">{sub}</p>}
        {notice}
        {children}
      </main>
      {foot && <div className="mob-foot">{foot}</div>}
    </div>
  );
}

export function Alert({ kind = "bad", children }: { kind?: "bad" | "ok" | "info"; children: ReactNode }) {
  return (
    <div className={`mob-alert ${kind}`} role={kind === "bad" ? "alert" : "status"}>
      {children}
    </div>
  );
}

export function PinPad({
  value, onChange, disabled, extraKey, label,
}: {
  value: string;
  onChange: (next: string) => void;
  disabled?: boolean;
  /** Optional bottom-start key (e.g. biometrics). */
  extraKey?: ReactNode;
  label: string;
}) {
  const valueRef = useRef(value);
  valueRef.current = value;
  const changeRef = useRef(onChange);
  changeRef.current = onChange;

  useEffect(() => {
    if (disabled) return;
    function onKey(e: KeyboardEvent) {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const v = valueRef.current;
      if (/^[0-9]$/.test(e.key)) {
        e.preventDefault();
        if (v.length < PIN_LENGTH) changeRef.current(v + e.key);
      } else if (e.key === "Backspace") {
        e.preventDefault();
        changeRef.current(v.slice(0, -1));
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [disabled]);

  const press = (d: string) => {
    if (disabled || value.length >= PIN_LENGTH) return;
    onChange(value + d);
  };

  return (
    <div className="mob-pin" aria-label={label} role="group">
      <div className="mob-dots" aria-live="polite" aria-label={tf("mob.pin.progress", { n: value.length })} role="status">
        {Array.from({ length: PIN_LENGTH }, (_, i) => (
          <span key={i} className={`mob-dot${i < value.length ? " on" : ""}`} />
        ))}
      </div>
      <div className="mob-keys" dir="ltr">
        {["1", "2", "3", "4", "5", "6", "7", "8", "9"].map((d) => (
          <button key={d} type="button" className="mob-key" disabled={disabled} onClick={() => press(d)}>{d}</button>
        ))}
        <div className="mob-key-slot">{extraKey}</div>
        <button type="button" className="mob-key" disabled={disabled} onClick={() => press("0")}>0</button>
        <button
          type="button"
          className="mob-key mob-key-ic"
          disabled={disabled || value.length === 0}
          onClick={() => onChange(value.slice(0, -1))}
          aria-label={t("mob.pin.delete")}
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
            <path d="M9 5h10a2 2 0 012 2v10a2 2 0 01-2 2H9l-6-7 6-7z" strokeLinejoin="round" />
            <path d="M12.5 9.5l5 5M17.5 9.5l-5 5" strokeLinecap="round" />
          </svg>
        </button>
      </div>
    </div>
  );
}

export function BioIcon({ kind }: { kind: BioKind }) {
  if (kind === "faceid" || kind === "face") {
    return (
      <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
        <path d="M4 8V6a2 2 0 012-2h2M16 4h2a2 2 0 012 2v2M20 16v2a2 2 0 01-2 2h-2M8 20H6a2 2 0 01-2-2v-2" strokeLinecap="round" />
        <path d="M9 9.5v1M15 9.5v1M12 9.5v3.5h-1M9.5 16c1.4 1 3.6 1 5 0" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  return (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
      <path d="M7.5 4.8A8 8 0 0120 11.5v1M4.5 9a8 8 0 00-.5 2.8v1.7" strokeLinecap="round" />
      <path d="M8 18.5c.6-1.6.9-3.4.9-5.2a3.1 3.1 0 016.2 0c0 2.4-.3 4.6-1 6.7M12 13.3c0 2.8-.5 5.3-1.6 7.2M17.6 15.5c-.1 1.8-.4 3.4-.9 4.8" strokeLinecap="round" />
    </svg>
  );
}
