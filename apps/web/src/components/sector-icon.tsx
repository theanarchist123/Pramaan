import { BookOpen, Briefcase, Cpu, FlaskConical, GraduationCap, HandHeart, HeartPulse, Landmark, Newspaper, Palette, Scale, Sprout, Trophy, Zap, type LucideIcon } from "lucide-react";

/** One icon per sector, matching the names in the generated `@pramaan/ui/sectors`. A sector is never shown by colour alone: it also gets this icon and its name. */
const ICONS: Record<string, LucideIcon> = {
  zap: Zap, sprout: Sprout, "heart-pulse": HeartPulse, cpu: Cpu, "flask-conical": FlaskConical, newspaper: Newspaper, briefcase: Briefcase,
  "graduation-cap": GraduationCap, "book-open": BookOpen, "hand-heart": HandHeart, palette: Palette, trophy: Trophy, scale: Scale, landmark: Landmark,
};

export function SectorIcon({ name, className }: { name: string; className?: string }) {
  const Icon = ICONS[name] ?? Landmark;
  return <Icon aria-hidden className={className} />;
}
