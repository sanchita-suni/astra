"use client";

interface Skill {
  name: string;
  count: number;
  max: number;
}

const COLORS = [
  "bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-300",
  "bg-indigo-200 text-indigo-900 dark:bg-indigo-900 dark:text-indigo-200",
  "bg-indigo-300 text-indigo-900 dark:bg-indigo-800 dark:text-indigo-100",
  "bg-indigo-500 text-white dark:bg-indigo-600 dark:text-white",
  "bg-indigo-700 text-white dark:bg-indigo-500 dark:text-white",
];

export default function SkillHeatmap({ skills }: { skills: Skill[] }) {
  return (
    <div className="flex flex-wrap gap-2">
      {skills.map((skill) => {
        const intensity = Math.min(4, Math.floor((skill.count / skill.max) * 4));
        const sizeClass =
          intensity >= 3 ? "text-base px-4 py-2" :
          intensity >= 2 ? "text-sm px-3 py-1.5" :
          "text-xs px-2.5 py-1";
        return (
          <span
            key={skill.name}
            className={`rounded-full font-medium ${COLORS[intensity]} ${sizeClass} transition-all`}
            title={`${skill.count} repo${skill.count !== 1 ? "s" : ""}`}
          >
            {skill.name}
          </span>
        );
      })}
    </div>
  );
}
