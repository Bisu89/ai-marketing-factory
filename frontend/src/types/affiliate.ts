// Mirrors backend/app/modules/affiliate/schemas.py exactly -- see
// docs/features/77-affiliate-engine.md.

export interface AffiliateProduct {
  id: number;
  name: string;
  category: string;
  tags: string[] | null;
  price: number | null;
  commission_rate: number | null;
  affiliate_url: string;
  platform: string;
  rating: number | null;
  review_count: number | null;
  active: boolean;
  notes: string | null;
  product_score: number | null;
  product_score_breakdown: {
    commission_component: number | null;
    price_component: number | null;
    demand_component: number | null;
    review_component: number | null;
    return_risk_component: number | null;
    notes: string[];
  } | null;
  product_score_computed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AffiliateProductCreate {
  name: string;
  category: string;
  affiliate_url: string;
  platform: string;
  tags?: string[] | null;
  price?: number | null;
  commission_rate?: number | null;
  rating?: number | null;
  review_count?: number | null;
  active?: boolean;
  notes?: string | null;
}

export interface AffiliateLink {
  id: number;
  product_id: number;
  link_code: string;
  label: string | null;
  click_count: number;
  last_clicked_at: string | null;
  created_at: string;
}

export interface CategoryRecommendation {
  category: string;
  relevance: number;
  reason: string;
}

export interface ProductMatch {
  product: AffiliateProduct;
  category_relevance: number;
  category_reason: string;
  final_score: number | null;
  reasons: string[];
}

export interface AffiliateKPI {
  total_clicks: number;
  real_tracked_clicks: number;
  manual_clicks: number;
  total_orders: number;
  total_commission_usd: number;
  total_gmv_usd: number;
  gmv_excluded_orders: number;
  revenue_per_1000_views_usd: number | null;
  revenue_per_1000_views_note: string | null;
  revenue_per_video_usd: number | null;
  videos_with_commercial_activity: number;
}
