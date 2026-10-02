export interface RawJob {
  id: string; // unique across sources, e.g. "adzuna:123"
  title: string;
  company: string;
  location: string;
  url: string;
  source: string;
}
