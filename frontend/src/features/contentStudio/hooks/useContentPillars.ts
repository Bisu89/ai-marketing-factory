import { useQuery } from "@tanstack/react-query";
import { fetchPillars } from "../../../api/contentStrategy";

export function useContentPillars() {
  return useQuery({
    queryKey: ["content-pillars"],
    queryFn: fetchPillars,
  });
}
