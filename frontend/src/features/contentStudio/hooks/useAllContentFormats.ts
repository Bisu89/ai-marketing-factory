import { useQuery } from "@tanstack/react-query";
import { fetchFormats } from "../../../api/contentStrategy";

// Unfiltered -- used only to resolve a format's display name for any Idea
// in the review list, independent of whichever Pillar the Strategy
// selector or the filter bar currently has picked (see
// useContentFormats.ts for the pillar-scoped dropdown version).
export function useAllContentFormats() {
  return useQuery({
    queryKey: ["content-formats", "all"],
    queryFn: () => fetchFormats(undefined),
  });
}
