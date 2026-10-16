import { useId, useState, type ReactNode } from "react";

import "./components.css";

export interface TooltipProps {
  label: string;
  children: ReactNode;
  placement?: "top" | "bottom";
}

/** Accessible tooltip: shown on hover and keyboard focus. */
export function Tooltip({ label, children, placement = "top" }: TooltipProps) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <span
      className="tooltip-wrap"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      <span aria-describedby={open ? id : undefined}>{children}</span>
      {open && (
        <span role="tooltip" id={id} className={`tooltip tooltip-${placement}`}>
          {label}
        </span>
      )}
    </span>
  );
}
