import { useEffect } from "react";

/** Sets the browser tab title to "VIGILANCE - <page>" (or just "VIGILANCE"
 * with no page name) for as long as the calling component is mounted --
 * one hook, called once per page/route, instead of each page reaching into
 * `document.title` directly. */
export default function usePageTitle(pageName) {
  useEffect(() => {
    document.title = pageName ? `VIGILANCE - ${pageName}` : "VIGILANCE";
  }, [pageName]);
}
