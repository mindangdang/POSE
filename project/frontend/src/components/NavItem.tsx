import * as Tabs from '@radix-ui/react-tabs';
import type { ReactNode } from 'react';

type NavItemProps = {
  expanded?: boolean;
  icon: ReactNode;
  label: string;
  value: string;
};

export function NavItem({ expanded = false, icon, label, value }: NavItemProps) {
  return (
    <Tabs.Trigger
      value={value}
      title={label}
      aria-label={label}
      className={[
        "relative flex h-30 items-center overflow-visible rounded-2xl text-white/45 transition-[width,color,background-color] duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] before:absolute before:left-1/2 before:top-0 before:h-full before:-translate-x-1/2 before:rounded-2xl before:bg-white before:opacity-0 before:shadow-xl before:transition-[width,opacity] before:duration-300 before:ease-[cubic-bezier(0.16,1,0.3,1)] hover:bg-white/10 hover:text-white data-[state=active]:bg-transparent data-[state=active]:text-black data-[state=active]:before:opacity-100",
        expanded ? "w-50 gap-1 data-[state=active]:before:w-60" : "w-20 gap-0 data-[state=active]:before:w-24",
      ].join(" ")}
    >
      <span className="relative z-10 flex h-10 w-20 shrink-0 items-center justify-center">
        {icon}
      </span>
      <span
        className={[
          "relative z-10 block overflow-hidden whitespace-nowrap text-sm font-semibold tracking-widest transition-[max-width,opacity,transform] duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]",
          expanded ? "max-w-28 translate-x-0 opacity-100 delay-75" : "max-w-0 -translate-x-1 opacity-0",
        ].join(" ")}
      >
        {label}
      </span>
    </Tabs.Trigger>
  );
}
