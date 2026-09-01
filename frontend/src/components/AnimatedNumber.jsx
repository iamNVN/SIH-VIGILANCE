import { animate } from "framer-motion";
import { useEffect, useRef, useState } from "react";

/** Counts up from 0 to `value` once on mount/change -- a small bit of life
 * on the numbers judges look at first, nothing that affects the real value. */
export default function AnimatedNumber({ value, format = (n) => Math.round(n).toLocaleString("en-IN") }) {
  const [display, setDisplay] = useState(0);
  const prev = useRef(0);

  useEffect(() => {
    const controls = animate(prev.current, value, {
      duration: 0.8,
      ease: "easeOut",
      onUpdate: (v) => setDisplay(v),
    });
    prev.current = value;
    return controls.stop;
  }, [value]);

  return <>{format(display)}</>;
}
