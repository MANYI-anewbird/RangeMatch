import { useState } from "react";

export async function copyTextToClipboard(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    /* use fallback */
  }
  try {
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "true");
    area.style.position = "fixed";
    area.style.left = "-9999px";
    document.body.appendChild(area);
    area.focus();
    area.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(area);
    return ok;
  } catch {
    return false;
  }
}

export function AdvisorCopyButton({
  label,
  text,
}: {
  label: string;
  text: string;
}) {
  const [status, setStatus] = useState<"idle" | "copied" | "failed">("idle");

  async function copy() {
    const ok = await copyTextToClipboard(text);
    setStatus(ok ? "copied" : "failed");
    window.setTimeout(() => setStatus("idle"), 2200);
  }

  const caption =
    status === "copied"
      ? "Copied"
      : status === "failed"
        ? "Copy failed — select the message and copy"
        : label;

  return (
    <button
      type="button"
      className={`advisor-copy${status === "failed" ? " advisor-copy-failed" : ""}`}
      onClick={() => void copy()}
    >
      {caption}
    </button>
  );
}
