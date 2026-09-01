import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

// No React.StrictMode: react-leaflet's MapContainer has a known
// incompatibility with StrictMode's dev-only double-invoked effects (it
// doesn't cleanly tear down and re-initialize a Leaflet map instance the
// second time around) -- verified directly while debugging why the cash-out
// map rendered one stray tile and never recovered, but only after visiting
// a second map instance elsewhere in the app first. StrictMode's double-
// invoke only ever runs in dev mode, never in a production build, so this
// isn't masking a real runtime bug -- it's working around a dev-only tooling
// quirk in a third-party library.
ReactDOM.createRoot(document.getElementById("root")).render(<App />);
