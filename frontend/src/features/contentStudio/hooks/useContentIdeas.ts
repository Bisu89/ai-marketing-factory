import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { fetchIdeas } from "../../../api/contentStrategy";
import type { IdeaListParams } from "../types";

export function useContentIdeas(params: IdeaListParams) {
  return useQuery({
    queryKey: ["content-ideas", params],
    queryFn: () => fetchIdeas(params),
    placeholderData: keepPreviousData,
  });
}
