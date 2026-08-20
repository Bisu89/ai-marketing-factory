import { useQuery } from "@tanstack/react-query";
import { fetchFormats } from "../../../api/contentStrategy";

// Only fetches once a Pillar is actually selected -- there is no
// "all formats, unfiltered" use in this UI (the Strategy selector always
// needs a Pillar chosen first, and the review filter bar treats "no pillar
// filter" as "don't filter by format either", see ContentStudioPage).
export function useContentFormats(pillarId: number | undefined) {
  return useQuery({
    queryKey: ["content-formats", pillarId],
    queryFn: () => fetchFormats(pillarId),
    enabled: pillarId != null,
  });
}
