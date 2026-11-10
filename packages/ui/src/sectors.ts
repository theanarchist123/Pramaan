// GENERATED from tokens.css by scripts/gen-sectors.mjs: do not edit by hand.
export interface Sector { name: string; slug: string; icon: string; light: string; dark: string }
export const SECTORS: readonly Sector[] = [
  { name: "Energy", slug: "energy", icon: "zap", light: "#877500", dark: "#CBB94C" },
  { name: "Agriculture", slug: "agriculture", icon: "sprout", light: "#578429", dark: "#98C96F" },
  { name: "Healthcare", slug: "healthcare", icon: "heart-pulse", light: "#148A53", dark: "#69D094" },
  { name: "Technology", slug: "technology", icon: "cpu", light: "#008C77", dark: "#36D2BA" },
  { name: "Science", slug: "science", icon: "flask-conical", light: "#00889C", dark: "#1FCEE3" },
  { name: "Media", slug: "media", icon: "newspaper", light: "#007EB6", dark: "#58C4FF" },
  { name: "Business", slug: "business", icon: "briefcase", light: "#4972C0", dark: "#89B7FF" },
  { name: "Education", slug: "education", icon: "graduation-cap", light: "#7565BB", dark: "#B6A8FF" },
  { name: "Literature", slug: "literature", icon: "book-open", light: "#9758A1", dark: "#DE9BE9" },
  { name: "Social Work", slug: "social-work", icon: "hand-heart", light: "#AC507C", dark: "#F693C0" },
  { name: "Arts & Culture", slug: "arts-culture", icon: "palette", light: "#B45151", dark: "#FF9492" },
  { name: "Sports", slug: "sports", icon: "trophy", light: "#B05925", dark: "#FA9D6B" },
  { name: "Law", slug: "law", icon: "scale", light: "#9F6700", dark: "#E7AA5B" },
  { name: "Public Service", slug: "public-service", icon: "landmark", light: "#65768C", dark: "#A2BAD8" },
] as const;

export const sectorByName = (name: string): Sector | undefined => SECTORS.find((s) => s.name === name);
