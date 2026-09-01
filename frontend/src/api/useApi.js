import { useCallback, useEffect, useState } from "react";

/** Minimal fetch-and-track hook -- deliberately no caching/query library,
 * kept simple per the team's own "don't overcomplicate" guidance.
 *
 * `fetcher` receives an AbortSignal that is actually aborted on unmount/
 * dependency change -- not just ignored. Without this, switching tabs
 * quickly (e.g. Investigation -> Graph -> Map) leaves every previous tab's
 * requests running to completion in the browser, which can queue up behind
 * each other since predict/graph do real CPU work (graph build + community
 * detection) per request -- a real, if easy-to-miss, resource-contention bug.
 *
 * Every state update is ALSO guarded by "is this still the active request" --
 * not just the abort itself. React 18 StrictMode double-invokes effects in
 * dev (mount -> cleanup -> mount again); the first invocation's request gets
 * aborted almost immediately, but its `.finally` still fires as a microtask,
 * and without this guard it would call setLoading(false) and clobber the
 * *second* (real) invocation's setLoading(true) -- a genuine race, not a
 * theoretical one, caught while screenshotting this exact hook. */
export function useApi(fetcher, deps = []) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(() => {
    const controller = new AbortController();
    let active = true;

    setLoading(true);
    setError(null);
    fetcher(controller.signal)
      .then((result) => {
        if (active) setData(result);
      })
      .catch((err) => {
        if (active && err.name !== "AbortError") setError(err.message || String(err));
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
      controller.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => reload(), [reload]);

  return { data, error, loading, reload };
}
