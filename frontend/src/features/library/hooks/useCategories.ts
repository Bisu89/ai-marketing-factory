import { useQuery } from "@tanstack/react-query";
import { fetchCategories } from "../../../api/videos";

export function useCategories() {
  return useQuery({
    queryKey: ["categories"],
    queryFn: fetchCategories,
    staleTime: 5 * 60_000,
  });
}
