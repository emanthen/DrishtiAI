export const KIND_STYLES: Record<string, { label: string; cls: string }> = {
  plate_read:       { label: "Plate read",    cls: "bg-confirm/15 text-confirm" },
  watchlist_hit:    { label: "Watchlist hit", cls: "bg-alert/15 text-alert" },
  wrong_way:        { label: "Wrong way",     cls: "bg-alert/15 text-alert" },
  illegal_park:     { label: "Illegal park",  cls: "bg-alert/10 text-alert" },
  gate_open:        { label: "Gate open",     cls: "bg-signal/15 text-signal" },
  helmet_violation: { label: "Helmet",        cls: "bg-alert/10 text-alert" },
  line_cross:       { label: "Line cross",    cls: "bg-steel/15 text-steel" },
  tamper:           { label: "Tamper",        cls: "bg-alert/15 text-alert" },
  congestion:       { label: "Congestion",    cls: "bg-steel/15 text-steel" },
};

export function KindChip({ kind }: { kind: string }) {
  const cfg = KIND_STYLES[kind] ?? { label: kind, cls: "bg-steel/10 text-steel" };
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-medium ${cfg.cls}`}>
      {cfg.label}
    </span>
  );
}
