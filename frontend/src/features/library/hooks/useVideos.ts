import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { fetchVideos } from "../../../api/videos";
import type { VideoListParams } from "../types";

export function useVideos(params: VideoListParams) {
  return useQuery({
    queryKey: ["videos", params],
    queryFn: () => fetchVideos(params),
    placeholderData: keepPreviousData,
  });
}
