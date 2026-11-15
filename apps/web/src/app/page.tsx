"use client";

import { Hero } from "@/components/landing/hero";
import { PeopleAndFields } from "@/components/landing/people-and-fields";
import { HowAndDoors } from "@/components/landing/how-and-doors";

// v3 home: people first. Search and the live sample are above the fold; the system's workings (agents, log, proof table) are
// no longer on this page. The old landing components stay in components/landing/ (parked, not deleted).
export default function Home() {
  return (
    <div className="md:-mt-16">
      <Hero />
      <PeopleAndFields />
      <HowAndDoors />
    </div>
  );
}
