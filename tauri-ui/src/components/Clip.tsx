import { useRef, useState } from "react";
import type { ClipKind, ClipZone } from "../lib/model";

/**
 * Un clip editable (acord o secció) dins un carril.
 *
 * Zona sensible:
 *   - Vora esquerra (~10 px) → moure inici
 *   - Cos central            → moure el clip (o l'inici, si és acord)
 *   - Vora dreta  (~10 px)   → moure final
 *
 * Click sense moviment → seek (mou el cursor de play).
 * Doble click → editar el nom.
 */
interface Props {
  kind: ClipKind;
  index: number;
  start: number;
  end: number;
  duration: number;
  label: string;
  title: string;
  bg: string;
  border: string;
  selected: boolean;
  onSelect: () => void;
  onSeek: () => void;
  onEdit: (zone: ClipZone, newStart: number, newEnd: number) => void;
  onDoubleClick: () => void;
  /** Si true, el cos arrossega preservant durada (seccions). Si false, mou l'inici (acords). */
  preserveDurationOnBody: boolean;
  snap: (t: number) => number;
}

const HANDLE_PX = 10;
const MOVE_THRESHOLD_PX = 3;

export function Clip(props: Props) {
  const dragRef = useRef<{
    zone: ClipZone;
    x0: number;
    start0: number;
    end0: number;
    moved: boolean;
  } | null>(null);
  const [dragging, setDragging] = useState(false);

  function zoneFromX(el: HTMLElement, clientX: number): ClipZone {
    const r = el.getBoundingClientRect();
    const x = clientX - r.left;
    const H = Math.min(HANDLE_PX, r.width * 0.3);
    if (x <= H) return "left";
    if (x >= r.width - H) return "right";
    return "body";
  }

  function onPointerDown(e: React.PointerEvent) {
    e.stopPropagation();
    e.preventDefault();
    const el = e.currentTarget as HTMLElement;
    el.setPointerCapture(e.pointerId);
    // Alt desactiva temporalment l'snap
    const snapFn = e.altKey ? (t: number) => t : props.snap;
    dragRef.current = {
      zone: zoneFromX(el, e.clientX),
      x0: e.clientX,
      start0: props.start,
      end0: props.end,
      moved: false,
    };
    (dragRef.current as any)._snap = snapFn;
    setDragging(true);
    props.onSelect();
  }

  function onPointerMove(e: React.PointerEvent) {
    const d = dragRef.current;
    if (!d) return;
    const el = e.currentTarget as HTMLElement;
    const lane = el.parentElement;
    if (!lane) return;
    const width = lane.getBoundingClientRect().width;
    if (width <= 0) return;
    const snapFn = (d as any)._snap as (t: number) => number;
    const dt = ((e.clientX - d.x0) / width) * props.duration;
    if (Math.abs(e.clientX - d.x0) > MOVE_THRESHOLD_PX) d.moved = true;

    let ns = d.start0;
    let ne = d.end0;
    if (d.zone === "left") {
      ns = snapFn(d.start0 + dt);
    } else if (d.zone === "right") {
      ne = snapFn(d.end0 + dt);
    } else if (props.preserveDurationOnBody) {
      ns = snapFn(d.start0 + dt);
      ne = ns + (d.end0 - d.start0);
    } else {
      // Acord: el cos mou l'inici (el fi és el següent inici)
      ns = snapFn(d.start0 + dt);
      ne = d.end0;
    }
    props.onEdit(d.zone, ns, ne);
  }

  function onPointerUp() {
    const d = dragRef.current;
    dragRef.current = null;
    setDragging(false);
    if (d && !d.moved) {
      props.onSeek();
    }
  }

  const className = [
    "clip",
    props.selected ? "clip-selected" : "",
    dragging ? "clip-dragging" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div
      className={className}
      style={{
        left: `${(props.start / props.duration) * 100}%`,
        width: `${Math.max((props.end - props.start) / props.duration, 0) * 100}%`,
        background: props.bg,
        borderColor: props.border,
      }}
      title={props.title}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onDoubleClick={(e) => {
        e.stopPropagation();
        props.onDoubleClick();
      }}
    >
      <span className="clip-handle clip-handle-left" />
      <span className="clip-label">{props.label}</span>
      <span className="clip-handle clip-handle-right" />
    </div>
  );
}
