import { useState, useRef, useEffect, type FC, type ReactNode } from "react";

interface TooltipProps {
  content: ReactNode;
  children: ReactNode;
}

const Tooltip: FC<TooltipProps> = ({ content, children }) => {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  return (
    <span className="tp-wrapper" ref={ref}>
      <span className="tp-trigger" onClick={() => setOpen(!open)}>
        {children}
      </span>
      {open && <div className="tp-popover">{content}</div>}
    </span>
  );
};

export default Tooltip;
