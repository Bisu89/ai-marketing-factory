import { useQuery } from "@tanstack/react-query";
import { fetchEmotions } from "../../../api/videos";

export function useEmotions() {
  return useQuery({
    queryKey: ["emotions"],
    queryFn: fetchEmotions,
    staleTime: 5 * 60_000,
  });
}
